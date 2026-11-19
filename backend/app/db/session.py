from collections.abc import Iterator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


def build_engine(url: str) -> Engine:
    if url.startswith("sqlite"):
        # In-memory SQLite must share one connection across threads (TestClient).
        return create_engine(url, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    return create_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=10)


class Database:
    def __init__(self, url: str) -> None:
        self.engine = build_engine(url)
        self.session_factory = sessionmaker(self.engine, expire_on_commit=False)

    def session(self) -> Iterator[Session]:
        db = self.session_factory()
        try:
            yield db
        finally:
            db.close()
