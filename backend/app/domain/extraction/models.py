"""DriveInfo: the structured view of one role in a placement notice.

Every field is optional. Unknown means null; extractors must never guess a value.
"""

from datetime import date, datetime, timedelta, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

IST = timezone(timedelta(hours=5, minutes=30), name="IST")


class DriveInfo(BaseModel):
    model_config = ConfigDict(extra="ignore")

    company: str | None = None
    role: str | None = None
    location: str | None = None
    ctc_lpa_min: float | None = Field(default=None, ge=0, le=500)
    ctc_lpa_max: float | None = Field(default=None, ge=0, le=500)
    stipend_per_month: int | None = Field(default=None, ge=0)
    deadline: datetime | None = None
    joining_date: date | None = None
    bond_years: float | None = Field(default=None, ge=0, le=10)
    bond_penalty_inr: int | None = Field(default=None, ge=0)
    min_cgpa: float | None = Field(default=None, ge=0, le=10)
    # Added beyond the original spec: notices often say "60% in UG" instead of a CGPA.
    min_ug_percent: float | None = Field(default=None, ge=0, le=100)
    min_percent_10th: float | None = Field(default=None, ge=0, le=100)
    min_percent_12th: float | None = Field(default=None, ge=0, le=100)
    max_active_backlogs: int | None = Field(default=None, ge=0)
    eligible_branches: list[str] | None = None
    eligible_batch: list[int] | None = None
    required_skills: list[str] | None = None
    selection_process: list[str] | None = None
    notes: str | None = None

    @field_validator("deadline")
    @classmethod
    def _assume_ist(cls, v: datetime | None) -> datetime | None:
        """Notices are written in Indian time; a deadline without a zone is IST."""
        if v is not None and v.tzinfo is None:
            return v.replace(tzinfo=IST)
        return v

    @field_validator("company", "role", "location", "notes")
    @classmethod
    def _blank_to_none(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        return v or None

    @field_validator("eligible_batch")
    @classmethod
    def _sane_years(cls, v: list[int] | None) -> list[int] | None:
        if v is not None and any(not 2000 <= y <= 2100 for y in v):
            raise ValueError("batch years must be between 2000 and 2100")
        return v

    @model_validator(mode="after")
    def _ctc_order(self) -> "DriveInfo":
        if (
            self.ctc_lpa_min is not None
            and self.ctc_lpa_max is not None
            and self.ctc_lpa_min > self.ctc_lpa_max
        ):
            raise ValueError("ctc_lpa_min must not exceed ctc_lpa_max")
        return self


def llm_json_schema() -> dict[str, Any]:
    """A flat JSON schema for LLM structured output.

    Every key is required and nullable, with no extra keys allowed. This shape is accepted
    by the strict structured-output modes of Anthropic and OpenAI. Pydantic still
    validates the result afterwards.
    """

    def nullable(t: str, desc: str, **extra: Any) -> dict[str, Any]:
        return {"type": [t, "null"], "description": desc, **extra}

    def nullable_list(item: str, desc: str) -> dict[str, Any]:
        return {"type": ["array", "null"], "items": {"type": item}, "description": desc}

    props: dict[str, dict[str, Any]] = {
        "company": nullable("string", "Hiring company name"),
        "role": nullable("string", "Job title for this role"),
        "location": nullable("string", "Work location(s)"),
        "ctc_lpa_min": nullable("number", "Lowest CTC in lakhs per annum"),
        "ctc_lpa_max": nullable("number", "Highest CTC in LPA (same as min if one value)"),
        "stipend_per_month": nullable("integer", "Internship stipend in INR per month"),
        "deadline": nullable("string", "Application deadline, ISO 8601 with +05:30 offset"),
        "joining_date": nullable("string", "Joining date, ISO 8601 date YYYY-MM-DD"),
        "bond_years": nullable("number", "Service bond length in years; 0 if notice says no bond"),
        "bond_penalty_inr": nullable("integer", "Bond breakage penalty in INR"),
        "min_cgpa": nullable("number", "Minimum UG CGPA on a 10-point scale"),
        "min_ug_percent": nullable("number", "Minimum UG percentage, if stated as a percentage"),
        "min_percent_10th": nullable("number", "Minimum Class X percentage"),
        "min_percent_12th": nullable("number", "Minimum Class XII / diploma percentage"),
        "max_active_backlogs": nullable("integer", "Maximum active backlogs/arrears allowed"),
        "eligible_branches": nullable_list("string", "Eligible branches, e.g. CSE, IT, ECE"),
        "eligible_batch": nullable_list("integer", "Eligible graduation years, e.g. [2026]"),
        "required_skills": nullable_list("string", "Technical skills required or preferred"),
        "selection_process": nullable_list("string", "Selection rounds in order"),
        "notes": nullable("string", "Other important conditions, verbatim and short"),
    }
    return {
        "type": "object",
        "properties": props,
        "required": list(props),
        "additionalProperties": False,
    }
