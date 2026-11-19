import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Float, ForeignKey, Index, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import JsonDoc, StrList, UTCDateTime, utcnow
from app.models.drive import Drive

DRIVE_STATUSES = ("saved", "applied", "shortlisted", "rejected", "selected")


class UserDrive(Base):
    """A student's view of a drive: eligibility, skill match and application status."""

    __tablename__ = "user_drives"
    __table_args__ = (Index("ix_user_drives_user_status", "user_id", "status"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    drive_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("drives.id", ondelete="CASCADE"), primary_key=True
    )
    eligibility: Mapped[str] = mapped_column(String(20))
    eligibility_reasons: Mapped[list[dict[str, Any]]] = mapped_column(JsonDoc)
    match_score: Mapped[float | None] = mapped_column(Float)
    matched_skills: Mapped[list[str]] = mapped_column(StrList, default=list)
    missing_skills: Mapped[list[str]] = mapped_column(StrList, default=list)
    status: Mapped[str] = mapped_column(String(20), default="saved")
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)

    drive: Mapped[Drive] = relationship(lazy="joined")
