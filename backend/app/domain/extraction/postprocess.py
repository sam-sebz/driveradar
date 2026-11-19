"""Clean-up applied to every extractor's output, so mock and LLM results look the same."""

from app.domain.eligibility.branches import BranchCatalog, default_branches
from app.domain.extraction.models import DriveInfo
from app.domain.skills.catalog import SkillCatalog, default_catalog


def normalise_drive(
    info: DriveInfo,
    skills: SkillCatalog | None = None,
    branches: BranchCatalog | None = None,
) -> DriveInfo:
    skill_cat = skills or default_catalog()
    branch_cat = branches or default_branches()
    updates: dict[str, object] = {}
    if info.required_skills is not None:
        updates["required_skills"] = skill_cat.normalise_list(info.required_skills) or None
    if info.eligible_branches is not None:
        codes: list[str] = []
        for raw in info.eligible_branches:
            code = branch_cat.normalise(raw) or raw.strip()
            if code and code not in codes:
                codes.append(code)
        updates["eligible_branches"] = codes or None
    if info.eligible_batch is not None:
        updates["eligible_batch"] = sorted(set(info.eligible_batch)) or None
    if info.selection_process is not None:
        updates["selection_process"] = [
            s.strip() for s in info.selection_process if s.strip()
        ] or None
    return info.model_copy(update=updates)
