"""Rule-based extractor (the default `mock` provider). Regex + keyword rules only.

Design rule: if a pattern does not clearly match, the field stays null. We never guess.
"""

import re
from collections.abc import Iterable
from datetime import date, datetime

from dateutil import parser as dateparser

from app.domain.eligibility.branches import BranchCatalog, default_branches
from app.domain.extraction.base import ExtractionResult
from app.domain.extraction.models import IST, DriveInfo
from app.domain.skills.catalog import SkillCatalog
from app.domain.skills.detector import detect_skills

NUM = r"(\d+(?:\.\d+)?)"
DASH = chr(0x2013)  # en dash, common in copied notices
MONEY = r"(?:rs\.?|inr|₹)\s*"

# Section headings we know how to split on. Order does not matter.
SECTION_HEADINGS: dict[str, tuple[str, ...]] = {
    "skills": (
        "skills required",
        "required skills",
        "technical skills",
        "skills",
        "desired skills",
        "skill set",
        "must have",
        "tech stack",
        "requirements",
        "key skills",
        "preferred skills",
    ),
    "selection": (
        "selection process",
        "selection procedure",
        "hiring process",
        "recruitment process",
        "rounds",
        "interview process",
    ),
    "eligibility": ("eligibility criteria", "eligibility", "who can apply"),
}
ALL_HEADINGS = {h for hs in SECTION_HEADINGS.values() for h in hs}

LABELS = {
    "company": r"(?:company(?:\s+name)?|organi[sz]ation|employer|recruiter)",
    "role": r"(?:role|position|designation|job\s+title|job\s+role|profile|post)",
    "location": r"(?:job\s+location|work\s+location|location|place\s+of\s+posting|posting)",
}

DEADLINE_WORDS = (
    r"deadline|last\s+date|apply\s+by|register\s+by|registration\s+closes|"
    r"closes\s+on|apply\s+before|registration\s+deadline|due\s+date"
)
JOINING_WORDS = r"date\s+of\s+joining|joining\s+date|\bdoj\b|joining"

_MONTHS = (
    r"jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|"
    r"aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?"
)
DATE_RE = re.compile(
    rf"(\d{{4}}-\d{{1,2}}-\d{{1,2}}"  # 2026-11-28
    rf"|\d{{1,2}}[/.-]\d{{1,2}}[/.-]\d{{2,4}}"  # 28/11/2026, 28-11-2026
    rf"|\d{{1,2}}(?:st|nd|rd|th)?[\s-]+(?:{_MONTHS})[\s,-]+\d{{4}}"  # 28th Nov 2026, 25-Nov-2026
    rf"|(?:{_MONTHS})\s+\d{{1,2}}(?:st|nd|rd|th)?,?\s+\d{{4}})",  # November 28, 2026
    re.IGNORECASE,
)
TIME_RE = re.compile(
    r"(\d{1,2}(?::\d{2})?\s*(?:am|pm|a\.m\.|p\.m\.)|\b\d{1,2}:\d{2}\b)", re.IGNORECASE
)


def _lines(text: str) -> list[str]:
    return [ln.strip() for ln in text.split("\n") if ln.strip()]


def _labelled(lines: Iterable[str], label_re: str) -> str | None:
    pat = re.compile(rf"^\s*{label_re}\s*[:\-{DASH}]\s*(.+)$", re.IGNORECASE)
    for line in lines:
        m = pat.match(line)
        if m:
            return m.group(1).strip()
    return None


def _heading_of(line: str) -> str | None:
    """Return the section name if this line is a known heading ("Skills Required" or
    "Skills:" with nothing important after it)."""
    head = re.split(rf"[:\-{DASH}]", line, maxsplit=1)[0].strip().lower()
    head = re.sub(r"^[\d.)\s]+", "", head)
    if head not in ALL_HEADINGS:
        return None
    for name, heads in SECTION_HEADINGS.items():
        if head in heads:
            return name
    return None  # pragma: no cover - unreachable, every heading belongs to a section


def split_sections(lines: list[str]) -> dict[str, list[str]]:
    """Group lines under known headings. `Skills: a, b` counts as heading + content."""
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in lines:
        name = _heading_of(line)
        if name is not None:
            current = name
            sections.setdefault(name, [])
            rest = re.split(rf"[:\-{DASH}]", line, maxsplit=1)
            if len(rest) == 2 and rest[1].strip():
                sections[name].append(rest[1].strip())
            continue
        if current is not None:
            # A "Label: value" line for another field ends a list section.
            if re.match(r"^[A-Za-z][A-Za-z /&().]{1,30}:\s", line) and current != "eligibility":
                current = None
                continue
            sections[current].append(line)
    return sections


def _parse_date(raw: str) -> date | None:
    try:
        return dateparser.parse(raw, dayfirst=not re.match(r"\d{4}-", raw)).date()
    except (ValueError, OverflowError):
        return None


def _date_in(line: str) -> tuple[date | None, re.Match[str] | None]:
    m = DATE_RE.search(line)
    if not m:
        return None, None
    return _parse_date(m.group(1)), m


def extract_deadline(lines: list[str]) -> datetime | None:
    for line in lines:
        if not re.search(DEADLINE_WORDS, line, re.IGNORECASE):
            continue
        d, m = _date_in(line)
        if d is None or m is None:
            continue
        hour, minute = 23, 59  # a date without a time closes at end of day
        t = TIME_RE.search(line[m.end() :]) or TIME_RE.search(line[: m.start()])
        if t:
            try:
                parsed = dateparser.parse(t.group(1).replace(".", ""))
                hour, minute = parsed.hour, parsed.minute
            except (ValueError, OverflowError):
                pass
        return datetime(d.year, d.month, d.day, hour, minute, tzinfo=IST)
    return None


def extract_joining(lines: list[str]) -> date | None:
    for line in lines:
        if re.search(JOINING_WORDS, line, re.IGNORECASE):
            d, _ = _date_in(line)
            if d:
                return d
    return None


def extract_ctc(lines: list[str]) -> tuple[float | None, float | None]:
    for line in lines:
        if not re.search(r"\b(ctc|package|salary|compensation|lpa)\b", line, re.IGNORECASE):
            continue
        if re.search(r"stipend", line, re.IGNORECASE) and not re.search(r"ctc", line, re.I):
            continue
        rng = re.search(rf"{NUM}\s*(?:-|to|{DASH})\s*{NUM}\s*(lpa|lakhs?|lacs?)\b", line, re.I)
        if rng:
            return float(rng.group(1)), float(rng.group(2))
        one = re.search(rf"{NUM}\s*(lpa|lakhs?|lacs?)\b", line, re.I)
        if one:
            v = float(one.group(1))
            return v, v
        rupees = re.search(
            rf"{MONEY}([\d,]{{6,}})\s*(?:per\s+annum|p\.?a\.?|/\s*annum)", line, re.I
        )
        if rupees:
            v = round(int(rupees.group(1).replace(",", "")) / 100000, 2)
            return v, v
    return None, None


def _rupees(text: str) -> int | None:
    lakh = re.search(rf"(?:{MONEY})?{NUM}\s*(?:lakhs?|lacs?|l)\b", text, re.I)
    if lakh:
        return round(float(lakh.group(1)) * 100000)
    amt = re.search(rf"{MONEY}([\d,]+(?:\.\d+)?)\s*(k\b)?", text, re.I)
    if amt:
        value = float(amt.group(1).replace(",", ""))
        return round(value * 1000) if amt.group(2) else round(value)
    return None


def extract_stipend(lines: list[str]) -> int | None:
    for line in lines:
        if re.search(r"stipend", line, re.I):
            return _rupees(line)
    return None


def extract_bond(lines: list[str]) -> tuple[float | None, int | None]:
    years: float | None = None
    penalty: int | None = None
    for line in lines:
        low = line.lower()
        if not re.search(r"bond|service\s+agreement|penalty|liquidated\s+damages", low):
            continue
        if re.search(r"\bno\s+(service\s+)?bond\b|bond\s*:\s*(nil|none|no)\b", low):
            years = 0.0
            continue
        y = re.search(rf"{NUM}\s*(years?|yrs?|months?)\b", low)
        if y and years is None and re.search(r"bond|service\s+agreement", low):
            v = float(y.group(1))
            years = round(v / 12, 2) if y.group(2).startswith("month") else v
        if re.search(r"penalty|liquidated|breakage|amount", low):
            after = re.split(
                r"penalty|liquidated damages|breakage|amount", line, maxsplit=1, flags=re.I
            )[-1]
            penalty = _rupees(after) if penalty is None else penalty
    return years, penalty


def _cgpa(lines: list[str]) -> float | None:
    for line in lines:
        if not re.search(r"\bc\.?g\.?p\.?a\b", line, re.I):
            continue
        for m in re.finditer(NUM, line):
            v = float(m.group(1))
            window = line[max(0, m.start() - 25) : m.end() + 25].lower()
            if (
                v <= 10
                and "cgpa" in window.replace(".", "")
                and "%" not in line[m.end() : m.end() + 2]
            ):
                return v
    return None


_X = r"(?:10th|class\s*x\b|class\s*10|\bx\b|sslc|secondary|matric)"
_XII = r"(?:12th|class\s*xii|class\s*12|\bxii\b|hsc|higher\s+secondary|diploma|puc)"
_UG = r"(?:ug|b\.?\s?tech|b\.?\s?e\.?|graduation|degree|aggregate|engineering)"


def extract_percentages(lines: list[str]) -> tuple[float | None, float | None, float | None]:
    """(class X %, class XII %, UG %)."""
    pct10 = pct12 = ug = None
    for line in lines:
        if "%" not in line:
            continue
        low = line.lower()
        if re.search(r"throughout|in\s+all|all\s+(academics|semesters)", low):
            m = re.search(rf"{NUM}\s*%", low)
            if m:
                v = float(m.group(1))
                pct10 = pct10 if pct10 is not None else v
                pct12 = pct12 if pct12 is not None else v
                ug = ug if ug is not None else v
            continue
        for m in re.finditer(rf"{NUM}\s*%", low):
            v = float(m.group(1))
            # Look at the words right after (or before) the number.
            # Stop at the next percentage so "70% in X and 75% in XII" reads as two cut-offs.
            after = re.split(rf"{NUM}\s*%", low[m.end() : m.end() + 40], maxsplit=1)[0]
            before = low[max(0, m.start() - 40) : m.start()]
            near = after if re.search(rf"{_X}|{_XII}|{_UG}", after) else before
            has_x = re.search(_X, near) is not None
            has_xii = re.search(_XII, near) is not None
            if has_x and pct10 is None:
                pct10 = v
            if has_xii and pct12 is None:
                pct12 = v
            if not has_x and not has_xii and re.search(_UG, near) and ug is None:
                ug = v
    return pct10, pct12, ug


def extract_backlogs(lines: list[str]) -> int | None:
    for line in lines:
        low = line.lower()
        if not re.search(r"backlog|arrear", low):
            continue
        if re.search(
            r"\b(no|zero|nil|without)\s+(active\s+|standing\s+|current\s+)?"
            r"(backlogs?|arrears?)",
            low,
        ) or re.search(r"backlogs?\s*:\s*(nil|none|no)", low):
            return 0
        m = re.search(
            r"(?:max(?:imum)?|up\s*to|not\s+more\s+than|at\s+most|<=?)\s*(?:of\s+)?" r"(\d+)", low
        ) or re.search(r"(\d+)\s*(?:active\s+)?(?:backlogs?|arrears?)", low)
        if m:
            return int(m.group(1))
    return None


def extract_batch(lines: list[str]) -> list[int] | None:
    for line in lines:
        if not re.search(
            r"batch|pass[\s-]?outs?|passing\s+out|graduat|year\s+of\s+passing", line, re.I
        ):
            continue
        years = sorted({int(y) for y in re.findall(r"\b(20\d{2})\b", line)})
        if years:
            return years
    return None


def _branch_patterns(catalog: BranchCatalog) -> list[tuple[re.Pattern[str], str]]:
    pats: list[tuple[re.Pattern[str], str]] = []
    for phrase, code in catalog.phrases():
        body = re.escape(phrase).replace(r"\ and\ ", r"\s*(?:and|&)\s*").replace(r"\ ", r"[\s.]+")
        if len(phrase) <= 4 and phrase.replace("-", "").isalpha():
            # Short codes ("it", "me", "ece") only count when written in capitals.
            pats.append((re.compile(rf"(?<![A-Za-z]){body.upper()}(?![A-Za-z])"), code))
        else:
            pats.append((re.compile(rf"(?<![A-Za-z]){body}(?![A-Za-z])", re.I), code))
    return pats


_BRANCH_PATTERNS: dict[int, list[tuple[re.Pattern[str], str]]] = {}


def extract_branches(lines: list[str], catalog: BranchCatalog | None = None) -> list[str] | None:
    cat = catalog or default_branches()
    patterns = _BRANCH_PATTERNS.setdefault(id(cat), _branch_patterns(cat))
    for line in lines:
        if not re.search(
            r"branch|stream|discipline|degree|course|eligible|b\.?\s?tech|\bb\.?e\b", line, re.I
        ):
            continue
        spans: list[tuple[int, int, str]] = []
        for pat, code in patterns:
            spans.extend((m.start(), m.end(), code) for m in pat.finditer(line))
        kept = [
            s
            for s in spans
            if not any(
                o[0] <= s[0] and s[1] <= o[1] and (o[1] - o[0]) > (s[1] - s[0]) for o in spans
            )
        ]
        codes: list[str] = []
        for _, _, code in sorted(kept):
            if code not in codes:
                codes.append(code)
        if codes:
            return codes
    return None


def extract_selection(sections: dict[str, list[str]]) -> list[str] | None:
    lines = sections.get("selection")
    if not lines:
        return None
    steps: list[str] = []
    for line in lines:
        for part in re.split(r"\s*(?:->|→|=>|,|;|\|)\s*", line):
            part = re.sub(
                r"^\s*(?:\d+[.)]|[-*•]|round\s*\d+\s*[:\-])\s*", "", part, flags=re.I
            ).strip(" .")
            if part and len(part) <= 60:
                steps.append(part)
    return steps or None


def extract_skills(
    text: str, sections: dict[str, list[str]], catalog: SkillCatalog | None = None
) -> list[str] | None:
    source = "\n".join(sections["skills"]) if sections.get("skills") else None
    if source is None:
        # No skills heading: scan the whole notice except the selection rounds.
        excluded = set(sections.get("selection", []))
        source = "\n".join(
            ln for ln in _lines(text) if ln not in excluded and _heading_of(ln) != "selection"
        )
    found = detect_skills(source, catalog)
    return found or None


def extract_company(lines: list[str]) -> str | None:
    value = _labelled(lines, LABELS["company"])
    if value:
        return value
    for line in lines[:8]:
        m = re.search(
            r"([A-Z][\w&.\- ]{2,60}?\s(?:Pvt\.?\s?Ltd\.?|Private Limited|Ltd\.?|"
            r"Limited|LLP|Inc\.?|Technologies|Solutions))\b",
            line,
        )
        if m:
            return m.group(1).strip()
    return None


def extract_notes(lines: list[str]) -> str | None:
    notes = [
        re.sub(r"^(note|important|n\.b\.)\s*[:\-]\s*", "", ln, flags=re.I)
        for ln in lines
        if re.match(r"^(note|important|n\.b\.)\s*[:\-]", ln, re.I)
    ]
    notes = [n for n in notes if "synthetic sample" not in n.lower()]
    return " ".join(notes) or None


class RuleBasedExtractor:
    name = "mock"

    def __init__(
        self, skills: SkillCatalog | None = None, branches: BranchCatalog | None = None
    ) -> None:
        self.skills = skills
        self.branches = branches

    def run(self, text: str) -> ExtractionResult:
        return ExtractionResult(self.extract(text), self.name)

    def extract(self, text: str) -> DriveInfo:
        lines = _lines(text)
        sections = split_sections(lines)
        ctc_min, ctc_max = extract_ctc(lines)
        bond_years, bond_penalty = extract_bond(lines)
        pct10, pct12, ug = extract_percentages(lines)
        return DriveInfo(
            company=extract_company(lines),
            role=_labelled(lines, LABELS["role"]),
            location=_labelled(lines, LABELS["location"]),
            ctc_lpa_min=ctc_min,
            ctc_lpa_max=ctc_max,
            stipend_per_month=extract_stipend(lines),
            deadline=extract_deadline(lines),
            joining_date=extract_joining(lines),
            bond_years=bond_years,
            bond_penalty_inr=bond_penalty,
            min_cgpa=_cgpa(lines),
            min_ug_percent=ug,
            min_percent_10th=pct10,
            min_percent_12th=pct12,
            max_active_backlogs=extract_backlogs(lines),
            eligible_branches=extract_branches(lines, self.branches),
            eligible_batch=extract_batch(lines),
            required_skills=extract_skills(text, sections, self.skills),
            selection_process=extract_selection(sections),
            notes=extract_notes(lines),
        )
