"""Eligibility engine: pure, deterministic rules. No LLM is involved in this decision.

Each rule returns pass / fail / unknown / not_specified with a human-readable reason.
- not_specified: the notice does not state this rule, so it does not restrict anyone.
- unknown: the notice states the rule but the student's profile lacks the value.
Overall: any fail -> not_eligible; else any unknown -> unknown; else eligible.
If the notice states no rule at all, the overall result is unknown (extraction may have
missed the criteria, and we never guess).
"""

from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from enum import Enum

from app.domain.eligibility.branches import BranchCatalog, default_branches


class Eligibility(str, Enum):
    ELIGIBLE = "eligible"
    NOT_ELIGIBLE = "not_eligible"
    UNKNOWN = "unknown"


class RuleStatus(str, Enum):
    PASS = "pass"  # noqa: S105 - rule outcome, not a password
    FAIL = "fail"
    UNKNOWN = "unknown"
    NOT_SPECIFIED = "not_specified"


@dataclass(frozen=True)
class StudentProfile:
    branch: str | None = None
    batch: int | None = None
    cgpa: float | None = None
    pct_10: float | None = None
    pct_12: float | None = None
    backlogs: int | None = None


@dataclass(frozen=True)
class Requirements:
    min_cgpa: float | None = None
    min_ug_percent: float | None = None
    min_percent_10th: float | None = None
    min_percent_12th: float | None = None
    max_active_backlogs: int | None = None
    eligible_branches: Sequence[str] | None = None
    eligible_batch: Sequence[int] | None = None


@dataclass(frozen=True)
class RuleResult:
    rule: str
    status: RuleStatus
    reason: str

    def to_dict(self) -> dict[str, str]:
        d = asdict(self)
        d["status"] = self.status.value
        return d


@dataclass(frozen=True)
class EligibilityResult:
    status: Eligibility
    rules: list[RuleResult] = field(default_factory=list)


def _n(x: float) -> str:
    return f"{x:g}"


def _not_specified(rule: str, label: str) -> RuleResult:
    return RuleResult(rule, RuleStatus.NOT_SPECIFIED, f"Notice does not state a {label}")


def _check_minimum(
    rule: str, label: str, required: float | None, have: float | None, unit: str = ""
) -> RuleResult:
    if required is None:
        return _not_specified(rule, f"minimum {label}")
    if have is None:
        return RuleResult(
            rule,
            RuleStatus.UNKNOWN,
            f"Notice needs {label} >= {_n(required)}{unit}; add it to your profile",
        )
    ok = round(have, 2) >= round(required, 2)
    sign = ">=" if ok else "<"
    return RuleResult(
        rule,
        RuleStatus.PASS if ok else RuleStatus.FAIL,
        f"Your {label} {_n(have)}{unit} {sign} required {_n(required)}{unit}",
    )


def _check_ug_percent(required: float | None, cgpa: float | None, factor: float) -> RuleResult:
    rule = "ug_percent"
    if required is None:
        return _not_specified(rule, "minimum UG percentage")
    if cgpa is None:
        return RuleResult(
            rule,
            RuleStatus.UNKNOWN,
            f"Notice needs UG >= {_n(required)}%; add your CGPA to your profile",
        )
    have = round(cgpa * factor, 2)
    ok = have >= round(required, 2)
    sign = ">=" if ok else "<"
    return RuleResult(
        rule,
        RuleStatus.PASS if ok else RuleStatus.FAIL,
        f"CGPA {_n(cgpa)} x {_n(factor)} = {_n(have)}% {sign} required " f"{_n(required)}%",
    )


def _check_backlogs(max_allowed: int | None, have: int | None) -> RuleResult:
    rule = "backlogs"
    if max_allowed is None:
        return _not_specified(rule, "backlog limit")
    if have is None:
        return RuleResult(
            rule,
            RuleStatus.UNKNOWN,
            f"Notice allows at most {max_allowed} active backlogs; "
            "add your backlog count to your profile",
        )
    ok = have <= max_allowed
    sign = "<=" if ok else ">"
    return RuleResult(
        rule,
        RuleStatus.PASS if ok else RuleStatus.FAIL,
        f"Your active backlogs {have} {sign} allowed {max_allowed}",
    )


def _check_branch(
    allowed: Sequence[str] | None, student: str | None, catalog: BranchCatalog
) -> RuleResult:
    rule = "branch"
    if not allowed:
        return _not_specified(rule, "branch restriction")
    listed = ", ".join(allowed)
    if not student:
        return RuleResult(
            rule, RuleStatus.UNKNOWN, f"Notice is open to {listed}; add your branch to your profile"
        )
    student_code = catalog.normalise(student)
    allowed_codes = [catalog.normalise(a) or a.strip().upper() for a in allowed]
    if student_code is None:
        if student.strip().upper() in allowed_codes:
            return RuleResult(rule, RuleStatus.PASS, f"Your branch {student} is listed")
        return RuleResult(
            rule,
            RuleStatus.UNKNOWN,
            f"Could not recognise your branch {student!r}; notice is open to " f"{listed}",
        )
    for code in allowed_codes:
        ok, why = catalog.accepts(code, student_code)
        if ok:
            extra = f" ({why})" if why else ""
            return RuleResult(
                rule, RuleStatus.PASS, f"Your branch {student_code} is eligible{extra}"
            )
    return RuleResult(rule, RuleStatus.FAIL, f"Your branch {student_code} is not in: {listed}")


def _check_batch(allowed: Sequence[int] | None, student: int | None) -> RuleResult:
    rule = "batch"
    if not allowed:
        return _not_specified(rule, "batch")
    listed = ", ".join(str(b) for b in allowed)
    if student is None:
        return RuleResult(
            rule,
            RuleStatus.UNKNOWN,
            f"Notice is for batch {listed}; add your batch year to your profile",
        )
    ok = student in allowed
    verb = "is" if ok else "is not"
    return RuleResult(
        rule, RuleStatus.PASS if ok else RuleStatus.FAIL, f"Your batch {student} {verb} in {listed}"
    )


def evaluate(
    student: StudentProfile,
    req: Requirements,
    cgpa_to_percent_factor: float = 10.0,
    branches: BranchCatalog | None = None,
) -> EligibilityResult:
    catalog = branches or default_branches()
    rules = [
        _check_minimum("cgpa", "CGPA", req.min_cgpa, student.cgpa),
        _check_ug_percent(req.min_ug_percent, student.cgpa, cgpa_to_percent_factor),
        _check_minimum("pct_10", "Class X %", req.min_percent_10th, student.pct_10, "%"),
        _check_minimum("pct_12", "Class XII %", req.min_percent_12th, student.pct_12, "%"),
        _check_backlogs(req.max_active_backlogs, student.backlogs),
        _check_branch(req.eligible_branches, student.branch, catalog),
        _check_batch(req.eligible_batch, student.batch),
    ]
    statuses = {r.status for r in rules}
    if RuleStatus.FAIL in statuses:
        overall = Eligibility.NOT_ELIGIBLE
    elif RuleStatus.UNKNOWN in statuses or statuses == {RuleStatus.NOT_SPECIFIED}:
        overall = Eligibility.UNKNOWN
    else:
        overall = Eligibility.ELIGIBLE
    return EligibilityResult(status=overall, rules=rules)
