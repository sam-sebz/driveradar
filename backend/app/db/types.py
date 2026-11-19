"""Column types that are native on PostgreSQL and fall back to JSON on SQLite.

Production and CI use PostgreSQL (text[], int[], jsonb). The fast local unit/integration
suite can run on in-memory SQLite, where the same columns are stored as JSON.
"""

from sqlalchemy import JSON, Integer, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

StrList = JSON().with_variant(ARRAY(Text), "postgresql")
IntList = JSON().with_variant(ARRAY(Integer), "postgresql")
JsonDoc = JSON().with_variant(JSONB(), "postgresql")
