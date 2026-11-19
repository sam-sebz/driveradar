import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import BigInteger, Date, Float, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import IntList, JsonDoc, StrList, UTCDateTime, utcnow


class Drive(Base):
    """One role from one uploaded notice (an XLSX with 3 roles gives 3 rows)."""

    __tablename__ = "drives"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    company: Mapped[str | None] = mapped_column(String(200))
    role: Mapped[str | None] = mapped_column(String(200))
    role_category: Mapped[str | None] = mapped_column(String(50))
    location: Mapped[str | None] = mapped_column(String(200))
    ctc_lpa_min: Mapped[float | None] = mapped_column(Float)
    ctc_lpa_max: Mapped[float | None] = mapped_column(Float)
    stipend_per_month: Mapped[int | None] = mapped_column(Integer)
    deadline: Mapped[datetime | None] = mapped_column(UTCDateTime, index=True)
    joining_date: Mapped[date | None] = mapped_column(Date)
    bond_years: Mapped[float | None] = mapped_column(Float)
    bond_penalty_inr: Mapped[int | None] = mapped_column(BigInteger)
    min_cgpa: Mapped[float | None] = mapped_column(Float)
    min_ug_percent: Mapped[float | None] = mapped_column(Float)
    min_percent_10th: Mapped[float | None] = mapped_column(Float)
    min_percent_12th: Mapped[float | None] = mapped_column(Float)
    max_active_backlogs: Mapped[int | None] = mapped_column(Integer)
    eligible_branches: Mapped[list[str] | None] = mapped_column(StrList)
    eligible_batch: Mapped[list[int] | None] = mapped_column(IntList)
    required_skills: Mapped[list[str] | None] = mapped_column(StrList)
    selection_process: Mapped[list[str] | None] = mapped_column(StrList)
    notes: Mapped[str | None] = mapped_column(Text)

    raw_text: Mapped[str] = mapped_column(Text)
    source_filename: Mapped[str | None] = mapped_column(String(255))
    stored_path: Mapped[str | None] = mapped_column(String(500))
    # sha256 of the role text: lets analytics count a notice once even if 40 students upload it.
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    extraction_provider: Mapped[str] = mapped_column(String(30))
    # The extractor's output before any user edits; kept for evaluation.
    extracted_original: Mapped[dict[str, Any]] = mapped_column(JsonDoc)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
