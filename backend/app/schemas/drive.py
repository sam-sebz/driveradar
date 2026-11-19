import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.domain.extraction.models import DriveInfo

DriveStatus = Literal["saved", "applied", "shortlisted", "rejected", "selected"]
EligibilityStatus = Literal["eligible", "not_eligible", "unknown"]


class RuleOut(BaseModel):
    rule: str
    status: Literal["pass", "fail", "unknown", "not_specified"]
    reason: str


class DriveDetail(BaseModel):
    id: uuid.UUID
    info: DriveInfo
    role_category: str | None
    source_filename: str | None
    extraction_provider: str
    created_at: datetime
    eligibility: EligibilityStatus
    eligibility_reasons: list[RuleOut]
    match_score: float | None
    matched_skills: list[str]
    missing_skills: list[str]
    status: DriveStatus
    closes_within_24h: bool
    is_closed: bool


class UploadResponse(BaseModel):
    drives: list[DriveDetail]


class DriveList(BaseModel):
    drives: list[DriveDetail]


class StatusUpdate(BaseModel):
    status: DriveStatus
