"""Shared fixtures.

By default the API tests run on in-memory SQLite so they need nothing installed.
Set TEST_DATABASE_URL=postgresql+psycopg://... (CI does) to run the same tests against
real PostgreSQL with the Alembic migrations applied.
"""

import os
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.config import Settings
from app.db.base import Base
from app.main import create_app
from app.models import User

TEST_DB_URL = os.environ.get("TEST_DATABASE_URL", "sqlite+pysqlite:///:memory:")
BACKEND_DIR = Path(__file__).resolve().parents[1]
SAMPLES = BACKEND_DIR.parent / "samples" / "synthetic"
PASSWORD = "Passw0rd!"


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


def _prepare_schema(app: FastAPI) -> None:
    engine = app.state.db.engine
    if engine.dialect.name == "sqlite":
        Base.metadata.create_all(engine)
        return
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", TEST_DB_URL)
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public"))
    command.upgrade(cfg, "head")


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return make_settings(tmp_path)


@pytest.fixture
def app(settings: Settings) -> Iterator[FastAPI]:
    application = create_app(settings)
    _prepare_schema(application)
    yield application
    application.state.db.engine.dispose()


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c


Signup = Callable[..., dict[str, str]]


@pytest.fixture
def signup(client: TestClient) -> Signup:
    """Create a user and return Authorization headers for them."""
    counter = {"n": 0}

    def _signup(email: str | None = None, **profile: Any) -> dict[str, str]:
        counter["n"] += 1
        email = email or f"student{counter['n']}@example.com"
        res = client.post("/auth/signup", json={"email": email, "password": PASSWORD})
        assert res.status_code == 201, res.text
        headers = {"Authorization": f"Bearer {res.json()['access_token']}"}
        if profile:
            body = {"skills": [], **profile}
            put = client.put("/me/profile", json=body, headers=headers)
            assert put.status_code == 200, put.text
        return headers

    return _signup


@pytest.fixture
def coordinator(app: FastAPI, client: TestClient) -> dict[str, str]:
    from app.core.security import hash_password

    with app.state.db.session_factory() as db:
        db.add(
            User(
                email="coord@example.com",
                password_hash=hash_password(PASSWORD),
                role="coordinator",
                skills=[],
            )
        )
        db.commit()
    res = client.post("/auth/login", json={"email": "coord@example.com", "password": PASSWORD})
    return {"Authorization": f"Bearer {res.json()['access_token']}"}
