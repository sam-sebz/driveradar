"""Skill match: match_score = matched / required, using normalised skill names."""

from collections.abc import Sequence
from dataclasses import dataclass

from app.domain.skills.catalog import SkillCatalog, default_catalog, skill_key


@dataclass(frozen=True)
class SkillMatch:
    matched: list[str]
    missing: list[str]
    # None when the notice lists no skills: "0% match" would be misleading.
    score: float | None


def match_skills(
    student_skills: Sequence[str],
    required_skills: Sequence[str],
    catalog: SkillCatalog | None = None,
) -> SkillMatch:
    cat = catalog or default_catalog()
    have = {skill_key(s) for s in cat.normalise_list(student_skills)}
    required = cat.normalise_list(required_skills)
    if not required:
        return SkillMatch(matched=[], missing=[], score=None)
    matched = [s for s in required if skill_key(s) in have]
    missing = [s for s in required if skill_key(s) not in have]
    return SkillMatch(
        matched=matched, missing=missing, score=round(len(matched) / len(required), 4)
    )
