"""Shared fixtures.

By default the API tests run on in-memory SQLite so they need nothing installed.
Set TEST_DATABASE_URL=postgresql+psycopg://... (CI does) to run the same tests against
real PostgreSQL with the Alembic migrations applied.
"""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app

TEST_DB_URL = os.environ.get("TEST_DATABASE_URL", "sqlite+pysqlite:///:memory:")


def make_settings(tmp_path: Path, **overrides: object) -> Settings:
    values: dict[str, object] = {
        "jwt_secret": "test-secret-not-for-production-0123456789",
        "database_url": TEST_DB_URL,
        "upload_dir": str(tmp_path / "uploads"),
        "llm_provider": "mock",
        "log_level": "WARNING",
        "login_rate_limit_per_minute": 1000,
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return make_settings(tmp_path)


@pytest.fixture
def app(settings: Settings) -> Iterator[FastAPI]:
    application = create_app(settings)
    yield application
    application.state.db.engine.dispose()


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c
