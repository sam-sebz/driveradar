import json

import pytest

from app.domain.skills.catalog import DATA_DIR, SkillCatalog, SkillEntry, default_catalog
from app.domain.skills.detector import detect_skills
from app.domain.skills.matcher import match_skills


def test_catalog_has_about_300_unique_skills() -> None:
    raw = json.loads((DATA_DIR / "skills.json").read_text(encoding="utf-8"))
    names = [item["name"] for item in raw]
    assert len(names) >= 300
    assert len(set(names)) == len(names)
    default_catalog()  # raises if two skills share a synonym


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("JS", "JavaScript"),
        ("javascript", "JavaScript"),
        ("Postgres", "PostgreSQL"),
        ("postgresql", "PostgreSQL"),
        ("ReactJS", "React"),
        ("react.js", "React"),
        ("Node JS", "Node.js"),
        ("nodejs", "Node.js"),
        ("  python  ", "Python"),
        ("k8s", "Kubernetes"),
        ("OOPS", "Object-Oriented Programming"),
        ("DSA", "Data Structures"),
        ("c++", "C++"),
        ("C#", "C#"),
        ("golang", "Go"),
        ("sklearn", "scikit-learn"),
        ("ML", "Machine Learning"),
    ],
)
def test_normalise_synonyms(raw: str, expected: str) -> None:
    assert default_catalog().normalise(raw) == expected


def test_unknown_skill_is_kept_cleaned() -> None:
    assert default_catalog().normalise("  Quantum   Basket Weaving. ") == "Quantum Basket Weaving"


def test_normalise_list_dedupes_across_synonyms() -> None:
    assert default_catalog().normalise_list(["JS", "JavaScript", "js", "Python"]) == [
        "JavaScript",
        "Python",
    ]


def test_duplicate_synonym_is_rejected() -> None:
    with pytest.raises(ValueError, match="maps to"):
        SkillCatalog([SkillEntry("A", ("x",)), SkillEntry("B", ("x",))])


def test_match_score_and_missing() -> None:
    m = match_skills(["js", "Postgres", "Python"], ["JavaScript", "PostgreSQL", "Docker", "AWS"])
    assert m.matched == ["JavaScript", "PostgreSQL"]
    assert m.missing == ["Docker", "AWS"]
    assert m.score == 0.5


def test_match_with_no_required_skills_is_none_not_zero() -> None:
    assert match_skills(["Python"], []).score is None


def test_match_with_no_student_skills() -> None:
    m = match_skills([], ["Java", "SQL"])
    assert m.score == 0.0
    assert m.missing == ["Java", "SQL"]


def test_match_full() -> None:
    assert match_skills(["java", "sql"], ["Java", "SQL"]).score == 1.0


def test_detect_basic_list() -> None:
    text = "Skills required: Java, Spring Boot, MySQL, REST APIs and Git."
    assert detect_skills(text) == ["Java", "Spring Boot", "MySQL", "REST API", "Git"]


def test_detect_does_not_confuse_java_and_javascript() -> None:
    assert detect_skills("Strong JavaScript skills") == ["JavaScript"]


def test_detect_longer_match_wins() -> None:
    assert detect_skills("Experience with React Native and PL/SQL") == ["React Native", "PL/SQL"]


def test_detect_strict_short_names_only_in_lists() -> None:
    assert detect_skills("Languages: C, C++, Go, R") == ["C", "C++", "Go", "R"]
    assert detect_skills("Go through the attached rules. Candidates may apply.") == []


def test_detect_ignores_ambiguous_aliases() -> None:
    assert detect_skills("Send your updated CV. The rest of the process is online.") == []
