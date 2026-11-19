"""Find dictionary skills mentioned in free text (used by the rule-based extractor)."""

import re
from functools import lru_cache

from app.domain.skills.catalog import SkillCatalog, SkillEntry, default_catalog

# A skill name must not be glued to other word characters: "Java" must not match "JavaScript".
_BEFORE = r"(?<![A-Za-z0-9_])"
_AFTER = r"(?![A-Za-z0-9_+#])"
# Short/ambiguous names (C, R, Go, Spring) only count inside a list: "Python, Go, Rust".
_STRICT_BEFORE = r"(?:^|(?<=[\s,/(;|:•\-]))"
_STRICT_AFTER = r"(?=[ \t]*(?:$|[,/);|&]|and\b|or\b))"


def _form_pattern(form: str) -> str:
    return re.escape(form).replace(r"\ ", r"\s+")


def _entry_patterns(entry: SkillEntry) -> list[re.Pattern[str]]:
    patterns: list[re.Pattern[str]] = []
    aliases = list(entry.aliases)
    if entry.strict:
        patterns.append(
            re.compile(_STRICT_BEFORE + _form_pattern(entry.name) + _STRICT_AFTER, re.MULTILINE)
        )
    else:
        aliases.insert(0, entry.name)
    if aliases:
        body = "|".join(_form_pattern(a) for a in sorted(aliases, key=len, reverse=True))
        patterns.append(re.compile(f"{_BEFORE}(?:{body}){_AFTER}", re.IGNORECASE))
    return patterns


@lru_cache(maxsize=4)
def _compiled(catalog: SkillCatalog) -> list[tuple[str, list[re.Pattern[str]]]]:
    return [(e.name, _entry_patterns(e)) for e in catalog.entries]


def detect_skills(text: str, catalog: SkillCatalog | None = None) -> list[str]:
    """Canonical skill names found in `text`, ordered by first appearance."""
    cat = catalog or default_catalog()
    spans: list[tuple[int, int, str]] = []
    for name, patterns in _compiled(cat):
        for pattern in patterns:
            spans.extend((m.start(), m.end(), name) for m in pattern.finditer(text))

    # Drop a match that sits inside a longer match of another skill:
    # "React Native" should not also count as "React", "PL/SQL" not also as "SQL".
    def inside_longer(span: tuple[int, int, str]) -> bool:
        s, e, n = span
        return any(s2 <= s and e <= e2 and (e2 - s2) > (e - s) and n2 != n for s2, e2, n2 in spans)

    first_seen: dict[str, int] = {}
    for span in spans:
        if not inside_longer(span):
            first_seen[span[2]] = min(first_seen.get(span[2], span[0]), span[0])
    return sorted(first_seen, key=lambda n: first_seen[n])
