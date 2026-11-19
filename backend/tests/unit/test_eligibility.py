import pytest

from app.domain.eligibility.branches import default_branches
from app.domain.eligibility.engine import (
    Eligibility,
    Requirements,
    RuleResult,
    RuleStatus,
    StudentProfile,
    evaluate,
)

STUDENT = StudentProfile(branch="CSE", batch=2026, cgpa=8.2, pct_10=91.0, pct_12=88.5, backlogs=0)


def rule(results: list[RuleResult], name: str) -> RuleResult:
    return next(r for r in results if r.rule == name)


# ---- overall outcomes -------------------------------------------------------


def test_all_rules_pass() -> None:
    req = Requirements(
        min_cgpa=7.0,
        min_percent_10th=60,
        min_percent_12th=60,
        max_active_backlogs=0,
        eligible_branches=["CSE", "IT"],
        eligible_batch=[2026],
    )
    res = evaluate(STUDENT, req)
    assert res.status is Eligibility.ELIGIBLE
    assert all(r.status in (RuleStatus.PASS, RuleStatus.NOT_SPECIFIED) for r in res.rules)


def test_one_failure_makes_not_eligible() -> None:
    res = evaluate(STUDENT, Requirements(min_cgpa=8.5, eligible_branches=["CSE"]))
    assert res.status is Eligibility.NOT_ELIGIBLE
    assert rule(res.rules, "cgpa").status is RuleStatus.FAIL
    assert "8.2 < required 8.5" in rule(res.rules, "cgpa").reason


def test_no_criteria_in_notice_is_unknown() -> None:
    res = evaluate(STUDENT, Requirements())
    assert res.status is Eligibility.UNKNOWN
    assert all(r.status is RuleStatus.NOT_SPECIFIED for r in res.rules)


def test_missing_profile_value_is_unknown() -> None:
    res = evaluate(StudentProfile(branch="CSE"), Requirements(min_cgpa=7.0))
    assert res.status is Eligibility.UNKNOWN
    assert "add it to your profile" in rule(res.rules, "cgpa").reason


def test_fail_beats_unknown() -> None:
    res = evaluate(
        StudentProfile(branch="MECH"), Requirements(min_cgpa=7.0, eligible_branches=["CSE"])
    )
    assert res.status is Eligibility.NOT_ELIGIBLE


def test_unspecified_rules_do_not_restrict() -> None:
    res = evaluate(STUDENT, Requirements(min_cgpa=6.0))
    assert res.status is Eligibility.ELIGIBLE
    assert rule(res.rules, "backlogs").status is RuleStatus.NOT_SPECIFIED


# ---- numeric thresholds ----------------------------------------------------


def test_cgpa_exactly_at_cutoff_passes() -> None:
    res = evaluate(StudentProfile(cgpa=7.0), Requirements(min_cgpa=7.0))
    assert rule(res.rules, "cgpa").status is RuleStatus.PASS


def test_cgpa_float_noise_does_not_fail() -> None:
    res = evaluate(StudentProfile(cgpa=6.999999999), Requirements(min_cgpa=7.0))
    assert rule(res.rules, "cgpa").status is RuleStatus.PASS


def test_ug_percentage_uses_cgpa_conversion_default_x10() -> None:
    res = evaluate(StudentProfile(cgpa=6.5), Requirements(min_ug_percent=60))
    r = rule(res.rules, "ug_percent")
    assert r.status is RuleStatus.PASS
    assert "6.5 x 10 = 65%" in r.reason


def test_ug_percentage_conversion_fails_below() -> None:
    res = evaluate(StudentProfile(cgpa=5.9), Requirements(min_ug_percent=60))
    assert rule(res.rules, "ug_percent").status is RuleStatus.FAIL


def test_ug_percentage_conversion_factor_is_configurable() -> None:
    # Some universities use percentage = CGPA x 9.5
    res = evaluate(
        StudentProfile(cgpa=6.5), Requirements(min_ug_percent=62), cgpa_to_percent_factor=9.5
    )
    assert rule(res.rules, "ug_percent").status is RuleStatus.FAIL  # 61.75 < 62


def test_class_10_and_12_percent() -> None:
    res = evaluate(
        StudentProfile(pct_10=59.9, pct_12=75),
        Requirements(min_percent_10th=60, min_percent_12th=60),
    )
    assert rule(res.rules, "pct_10").status is RuleStatus.FAIL
    assert rule(res.rules, "pct_12").status is RuleStatus.PASS


def test_missing_class_12_is_unknown_for_diploma_students() -> None:
    res = evaluate(StudentProfile(pct_10=90, pct_12=None), Requirements(min_percent_12th=60))
    assert rule(res.rules, "pct_12").status is RuleStatus.UNKNOWN


# ---- backlogs ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("allowed", "have", "expected"),
    [
        (0, 0, RuleStatus.PASS),
        (0, 1, RuleStatus.FAIL),
        (2, 2, RuleStatus.PASS),
        (2, 3, RuleStatus.FAIL),
        (0, None, RuleStatus.UNKNOWN),
    ],
)
def test_backlogs(allowed: int, have: int | None, expected: RuleStatus) -> None:
    res = evaluate(StudentProfile(backlogs=have), Requirements(max_active_backlogs=allowed))
    assert rule(res.rules, "backlogs").status is expected


# ---- branches -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("student_branch", "allowed", "expected"),
    [
        ("CSE", ["CSE"], RuleStatus.PASS),
        ("Computer Science and Engineering", ["CSE"], RuleStatus.PASS),
        ("cse", ["Computer Science"], RuleStatus.PASS),
        ("IT", ["CSE", "IT"], RuleStatus.PASS),
        ("Information Technology", ["it"], RuleStatus.PASS),
        ("CSE-IT", ["CSE"], RuleStatus.PASS),  # specialisation counts as parent
        ("CSE-IT", ["IT"], RuleStatus.FAIL),
        ("IT", ["Computer Science or equivalent"], RuleStatus.PASS),
        ("MCA", ["CS_EQUIV"], RuleStatus.PASS),
        ("ECE", ["Computer Science or equivalent"], RuleStatus.FAIL),
        ("ECE", ["circuit branches"], RuleStatus.PASS),
        ("MECH", ["Circuit branches"], RuleStatus.FAIL),
        ("CIVIL", ["All branches"], RuleStatus.PASS),
        ("MECH", ["CSE", "IT", "ECE"], RuleStatus.FAIL),
        ("Marine Engineering", ["CSE"], RuleStatus.UNKNOWN),  # unrecognised branch
        ("Marine Engineering", ["Marine Engineering"], RuleStatus.PASS),
        (None, ["CSE"], RuleStatus.UNKNOWN),
    ],
)
def test_branch_rules(student_branch: str | None, allowed: list[str], expected: RuleStatus) -> None:
    res = evaluate(StudentProfile(branch=student_branch), Requirements(eligible_branches=allowed))
    assert rule(res.rules, "branch").status is expected


def test_specialisation_reason_is_explained() -> None:
    res = evaluate(StudentProfile(branch="CSE-IT"), Requirements(eligible_branches=["CSE"]))
    assert "specialisation of CSE" in rule(res.rules, "branch").reason


def test_branch_normalise_unknown_returns_none() -> None:
    assert default_branches().normalise("Underwater Basket Weaving") is None


# ---- batch -------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("batch", "allowed", "expected"),
    [
        (2026, [2026], RuleStatus.PASS),
        (2025, [2026], RuleStatus.FAIL),
        (2025, [2025, 2026], RuleStatus.PASS),
        (None, [2026], RuleStatus.UNKNOWN),
        (2026, [], RuleStatus.NOT_SPECIFIED),
    ],
)
def test_batch(batch: int | None, allowed: list[int], expected: RuleStatus) -> None:
    res = evaluate(StudentProfile(batch=batch), Requirements(eligible_batch=allowed))
    assert rule(res.rules, "batch").status is expected


def test_rule_result_serialises_to_plain_dict() -> None:
    res = evaluate(STUDENT, Requirements(min_cgpa=7))
    d = rule(res.rules, "cgpa").to_dict()
    assert d == {"rule": "cgpa", "status": "pass", "reason": "Your CGPA 8.2 >= required 7"}
