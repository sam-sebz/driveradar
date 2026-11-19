"""Column types that are native on PostgreSQL and fall back to JSON on SQLite.

Production and CI use PostgreSQL (text[], int[], jsonb, timestamptz). The fast local test
suite can run on in-memory SQLite, where the same columns are stored as JSON.
"""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, DateTime, Dialect, Integer, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.types import TypeDecorator

StrList = JSON().with_variant(ARRAY(Text), "postgresql")
IntList = JSON().with_variant(ARRAY(Integer), "postgresql")
JsonDoc = JSON().with_variant(JSONB, "postgresql")


class UTCDateTime(TypeDecorator[datetime]):
    """Always store UTC and always return timezone-aware datetimes (SQLite drops tzinfo)."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("naive datetime given to a UTCDateTime column")
        return value.astimezone(timezone.utc)

    def process_result_value(self, value: Any, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        dt: datetime = value
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
