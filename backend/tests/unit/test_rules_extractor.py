from datetime import date, datetime

import pytest

from app.domain.extraction.models import IST, DriveInfo
from app.domain.extraction.postprocess import normalise_drive
from app.domain.extraction.rules import RuleBasedExtractor
from app.domain.roles import categorise_role

X = RuleBasedExtractor()


def ex(text: str) -> DriveInfo:
    return X.extract(text)


def test_empty_text_gives_all_nulls() -> None:
    assert ex("Hello world") == DriveInfo()


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("Last date: 28 November 2026, 11:59 PM", datetime(2026, 11, 28, 23, 59, tzinfo=IST)),
        ("Apply by: 02/12/2026 5:00 PM", datetime(2026, 12, 2, 17, 0, tzinfo=IST)),
        ("Registration Deadline: 25-Nov-2026 6:00 PM", datetime(2026, 11, 25, 18, 0, tzinfo=IST)),
        ("Deadline: 2026-12-05", datetime(2026, 12, 5, 23, 59, tzinfo=IST)),
        ("Register by December 3, 2026 at 10:30 am", datetime(2026, 12, 3, 10, 30, tzinfo=IST)),
        ("Last date to apply is 1st Dec 2026 (17:00)", datetime(2026, 12, 1, 17, 0, tzinfo=IST)),
    ],
)
def test_deadline_formats(line: str, expected: datetime) -> None:
    assert ex(line).deadline == expected


def test_date_without_deadline_word_is_ignored() -> None:
    assert ex("Pre-placement talk on 20 Nov 2026").deadline is None


@pytest.mark.parametrize(
    ("line", "lo", "hi"),
    [
        ("CTC: Rs. 6.5 - 8 LPA", 6.5, 8.0),
        ("Package: 12 LPA", 12.0, 12.0),
        ("CTC: 4 to 5.5 lakhs per annum", 4.0, 5.5),
        ("CTC: ₹ 6,00,000 per annum", 6.0, 6.0),
        ("Salary: 7 lacs", 7.0, 7.0),
    ],
)
def test_ctc(line: str, lo: float, hi: float) -> None:
    info = ex(line)
    assert (info.ctc_lpa_min, info.ctc_lpa_max) == (lo, hi)


def test_stipend_variants() -> None:
    assert ex("Stipend: ₹25,000 per month").stipend_per_month == 25000
    assert ex("Stipend: INR 30k/month").stipend_per_month == 30000
    assert ex("Stipend: Rs. 1.2 lakh per month").stipend_per_month == 120000


def test_bond() -> None:
    info = ex("Service Agreement: 2 years. Bond penalty of Rs. 1,50,000 if you leave early.")
    assert (info.bond_years, info.bond_penalty_inr) == (2.0, 150000)
    assert ex("Bond: 18 months").bond_years == 1.5
    assert ex("Bond: No bond").bond_years == 0.0
    assert ex("There is no bond for this role").bond_years == 0.0
    assert ex("Bond: 1 year, penalty 2 lakhs").bond_penalty_inr == 200000


def test_academic_cutoffs() -> None:
    info = ex("Minimum 7.0 CGPA in B.Tech\n60% in 10th and 12th")
    assert info.min_cgpa == 7.0
    assert (info.min_percent_10th, info.min_percent_12th) == (60.0, 60.0)


def test_cgpa_label_first() -> None:
    assert ex("CGPA: 7.5 and above").min_cgpa == 7.5
    assert ex("CGPA cut-off 6.75").min_cgpa == 6.75


def test_ug_percentage_goes_to_ug_field_not_cgpa() -> None:
    info = ex("65% aggregate in B.Tech")
    assert info.min_ug_percent == 65.0
    assert info.min_cgpa is None


def test_throughout_applies_to_all_levels() -> None:
    info = ex("Minimum 60% throughout academics")
    assert (info.min_percent_10th, info.min_percent_12th, info.min_ug_percent) == (60, 60, 60)


def test_separate_x_and_xii() -> None:
    info = ex("10th / 12th: 70% in Class X and 75% in Class XII")
    assert (info.min_percent_10th, info.min_percent_12th) == (70.0, 75.0)


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("No active backlogs", 0),
        ("Backlogs: No standing arrears", 0),
        ("Maximum 1 active backlog", 1),
        ("Not more than 2 backlogs allowed", 2),
        ("Backlogs: nil", 0),
        ("Candidates with up to 3 arrears may apply", 3),
    ],
)
def test_backlogs(line: str, expected: int) -> None:
    assert ex(line).max_active_backlogs == expected


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("Eligible Branches: B.Tech CSE, IT, ECE", ["CSE", "IT", "ECE"]),
        ("Branches: Computer Science or equivalent", ["CS_EQUIV"]),
        ("Eligible Branches: All branches", ["ANY"]),
        ("Eligible: CSE-AIML, CSE-DS", ["CSE-AIML", "CSE-DS"]),
        ("Degree: B.E. Computer Science and Engineering", ["CSE"]),
        ("Open to circuit branches", ["CIRCUIT"]),
        # Found during manual UI testing: "Eligibility:" was not seen as a branch line.
        ("Eligibility: CSE, IT", ["CSE", "IT"]),
    ],
)
def test_branches(line: str, expected: list[str]) -> None:
    assert ex(line).eligible_branches == expected


def test_lowercase_it_is_not_a_branch() -> None:
    assert ex("Eligible students: it is mandatory to register").eligible_branches is None


def test_batch() -> None:
    assert ex("Batch: 2026 & 2027").eligible_batch == [2026, 2027]
    assert ex("Only 2026 passouts").eligible_batch == [2026]
    assert ex("Founded in 2019").eligible_batch is None


def test_skills_section_only() -> None:
    text = (
        "Company: Foo Ltd\nAbout: we build Java tools\nSkills Required\nPython, SQL\n"
        "Selection Process\nAptitude, Technical Interview"
    )
    assert ex(text).required_skills == ["Python", "SQL"]


def test_skills_without_heading_scan_whole_text_except_selection() -> None:
    text = "We need React and Node.js developers.\nSelection Process: Aptitude Test"
    assert ex(text).required_skills == ["React", "Node.js"]


def test_selection_process_split() -> None:
    assert ex("Selection Process\n1. Online Assessment\n2. HR Interview").selection_process == [
        "Online Assessment",
        "HR Interview",
    ]
    assert ex("Selection Process: Test -> GD -> HR").selection_process == ["Test", "GD", "HR"]


def test_company_role_location_labels() -> None:
    info = ex("Company Name: Foo Pvt Ltd\nDesignation: SDE 1\nWork Location: Pune")
    assert (info.company, info.role, info.location) == ("Foo Pvt Ltd", "SDE 1", "Pune")


def test_company_from_suffix_without_label() -> None:
    assert ex("Campus drive by Acme Widgets Pvt. Ltd. for 2026 batch").company is not None


def test_joining_date_and_notes() -> None:
    info = ex("Date of Joining: 01-07-2027\nNote: Laptop will be provided.")
    assert info.joining_date == date(2027, 7, 1)
    assert info.notes == "Laptop will be provided."


def test_run_reports_provider() -> None:
    assert X.run("CTC: 5 LPA").provider == "mock"


def test_normalise_drive_cleans_llm_style_output() -> None:
    info = DriveInfo(
        required_skills=["JS", "javascript", "Postgres"],
        eligible_branches=["Computer Science", "CSE", "Marine"],
        eligible_batch=[2027, 2026, 2026],
        selection_process=[" Test ", ""],
    )
    out = normalise_drive(info)
    assert out.required_skills == ["JavaScript", "PostgreSQL"]
    assert out.eligible_branches == ["CSE", "Marine"]
    assert out.eligible_batch == [2026, 2027]
    assert out.selection_process == ["Test"]


@pytest.mark.parametrize(
    ("title", "category"),
    [
        ("Associate Software Engineer", "Software Engineering"),
        ("Data Analyst", "Data & AI"),
        ("Data Engineer", "Data & AI"),
        ("Cloud Engineer Intern (with PPO)", "Cloud & DevOps"),
        ("Embedded Engineer", "Embedded & Hardware"),
        ("Graduate Engineer Trainee", "Software Engineering"),
        ("Management Trainee", "Graduate Trainee"),
        ("QA Automation Engineer", "QA & Testing"),
        ("Chef", "Other"),
        (None, None),
    ],
)
def test_role_categories(title: str | None, category: str | None) -> None:
    assert categorise_role(title) == category


def test_drive_info_validation() -> None:
    with pytest.raises(ValueError, match="ctc_lpa_min"):
        DriveInfo(ctc_lpa_min=9, ctc_lpa_max=5)
    with pytest.raises(ValueError):
        DriveInfo(min_cgpa=11)
    with pytest.raises(ValueError, match="batch"):
        DriveInfo(eligible_batch=[1999])
    naive = DriveInfo(deadline=datetime(2026, 12, 1, 10, 0))
    assert naive.deadline is not None and naive.deadline.utcoffset() == IST.utcoffset(None)
    assert DriveInfo(company="  ").company is None
