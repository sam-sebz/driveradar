from pydantic import BaseModel


class SkillCount(BaseModel):
    skill: str
    count: int


class SkillsAnalytics(BaseModel):
    total_drives: int
    top_skills: list[SkillCount]


class RoleCount(BaseModel):
    role_category: str
    count: int


class SummaryAnalytics(BaseModel):
    total_drives: int
    total_companies: int
    drives_by_role_category: list[RoleCount]
    median_ctc_lpa: float | None
    drives_with_ctc: int
    drives_with_bond: int
