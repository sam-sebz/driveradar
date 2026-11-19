import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProfileUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    branch: str | None = Field(default=None, max_length=80)
    batch: int | None = Field(default=None, ge=2000, le=2100)
    cgpa: float | None = Field(default=None, ge=0, le=10)
    pct_10: float | None = Field(default=None, ge=0, le=100)
    pct_12: float | None = Field(default=None, ge=0, le=100)
    backlogs: int | None = Field(default=None, ge=0, le=50)
    skills: list[str] = Field(default_factory=list, max_length=100)

    @field_validator("skills")
    @classmethod
    def _skill_length(cls, v: list[str]) -> list[str]:
        if any(len(s) > 60 for s in v):
            raise ValueError("each skill must be at most 60 characters")
        return v


class ProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    role: str
    name: str | None
    branch: str | None
    batch: int | None
    cgpa: float | None
    pct_10: float | None
    pct_12: float | None
    backlogs: int | None
    skills: list[str]
