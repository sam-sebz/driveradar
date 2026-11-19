import uuid
from datetime import datetime

from sqlalchemy import Float, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import StrList, UTCDateTime, utcnow

ROLE_STUDENT = "student"
ROLE_COORDINATOR = "coordinator"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # Stored lower-cased, so the unique index is case-insensitive in practice.
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(20), default=ROLE_STUDENT)
    name: Mapped[str | None] = mapped_column(String(120))
    branch: Mapped[str | None] = mapped_column(String(80))
    batch: Mapped[int | None] = mapped_column(Integer)
    cgpa: Mapped[float | None] = mapped_column(Float)
    pct_10: Mapped[float | None] = mapped_column(Float)
    pct_12: Mapped[float | None] = mapped_column(Float)
    backlogs: Mapped[int | None] = mapped_column(Integer)
    skills: Mapped[list[str]] = mapped_column(StrList, default=list)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
