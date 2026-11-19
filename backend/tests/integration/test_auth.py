from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.rate_limit import RateLimiter
from app.core.security import create_access_token
from app.main import create_app
from tests.conftest import PASSWORD, _prepare_schema, make_settings

SECRET = "test-secret-not-for-production-0123456789"


def _signup(client: TestClient, email: str = "a@example.com") -> dict[str, Any]:
    res = client.post("/auth/signup", json={"email": email, "password": PASSWORD})
    assert res.status_code == 201, res.text
    body: dict[str, Any] = res.json()
    return body


def test_signup_login_and_profile_flow(client: TestClient) -> None:
    tokens = _signup(client, "Asha@Example.com")
    assert tokens["role"] == "student"
    assert tokens["expires_in"] == 15 * 60

    res = client.post("/auth/login", json={"email": "asha@example.com", "password": PASSWORD})
    assert res.status_code == 200
    headers = {"Authorization": f"Bearer {res.json()['access_token']}"}

    me = client.get("/me/profile", headers=headers)
    assert me.status_code == 200
    assert me.json()["email"] == "asha@example.com"
    assert "password_hash" not in me.json()


def test_duplicate_signup_conflicts(client: TestClient) -> None:
    _signup(client)
    res = client.post("/auth/signup", json={"email": "A@example.com", "password": PASSWORD})
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "CONFLICT"


def test_weak_password_and_bad_email_rejected(client: TestClient) -> None:
    res = client.post("/auth/signup", json={"email": "x@example.com", "password": "short"})
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "VALIDATION_ERROR"
    res = client.post("/auth/signup", json={"email": "x@example.com", "password": "lettersonly"})
    assert res.status_code == 422
    res = client.post("/auth/signup", json={"email": "not-an-email", "password": PASSWORD})
    assert res.status_code == 422


def test_wrong_password_and_unknown_user_look_the_same(client: TestClient) -> None:
    _signup(client)
    wrong = client.post("/auth/login", json={"email": "a@example.com", "password": "Nope12345"})
    unknown = client.post("/auth/login", json={"email": "z@example.com", "password": PASSWORD})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


def test_protected_routes_need_a_valid_token(client: TestClient) -> None:
    assert client.get("/me/profile").status_code == 401
    bad = client.get("/me/profile", headers={"Authorization": "Bearer nonsense"})
    assert bad.status_code == 401
    assert bad.json()["error"]["code"] == "UNAUTHORIZED"
    basic = client.get("/me/profile", headers={"Authorization": "Basic abc"})
    assert basic.status_code == 401


def test_expired_and_wrongly_signed_tokens_rejected(client: TestClient) -> None:
    tokens = _signup(client)
    me = client.get("/me/profile", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    user_id = me.json()["id"]
    import uuid

    old = datetime.now(timezone.utc) - timedelta(minutes=30)
    expired = create_access_token(uuid.UUID(user_id), "student", SECRET, 15, now=old)
    assert (
        client.get("/me/profile", headers={"Authorization": f"Bearer {expired}"}).status_code == 401
    )
    forged = create_access_token(uuid.UUID(user_id), "coordinator", "other-secret-xxxxxxxxxx", 15)
    assert (
        client.get("/me/profile", headers={"Authorization": f"Bearer {forged}"}).status_code == 401
    )


def test_refresh_rotates_and_detects_reuse(client: TestClient) -> None:
    tokens = _signup(client)
    first = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert first.status_code == 200
    new_refresh = first.json()["refresh_token"]
    assert new_refresh != tokens["refresh_token"]

    # Re-using the old (rotated) token is treated as theft: every session is revoked.
    reuse = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert reuse.status_code == 401
    after = client.post("/auth/refresh", json={"refresh_token": new_refresh})
    assert after.status_code == 401


def test_unknown_refresh_token(client: TestClient) -> None:
    res = client.post("/auth/refresh", json={"refresh_token": "x" * 43})
    assert res.status_code == 401


def test_expired_refresh_token(tmp_path: Path) -> None:
    app = create_app(make_settings(tmp_path, refresh_token_days=-1))
    _prepare_schema(app)
    with TestClient(app) as client:
        tokens = _signup(client)
        res = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    app.state.db.engine.dispose()
    assert res.status_code == 401
    assert "expired" in res.json()["error"]["message"]


def test_login_is_rate_limited(app: FastAPI, client: TestClient) -> None:
    app.state.login_limiter = RateLimiter(limit=3, window_seconds=60)
    _signup(client)
    body = {"email": "a@example.com", "password": "Wrong1234"}
    codes = [client.post("/auth/login", json=body).status_code for _ in range(4)]
    assert codes == [401, 401, 401, 429]
    res = client.post("/auth/login", json=body)
    assert res.json()["error"]["code"] == "RATE_LIMITED"


def test_rate_limiter_window_slides() -> None:
    now = [0.0]
    limiter = RateLimiter(limit=2, window_seconds=10, clock=lambda: now[0])
    assert limiter.allow("k") and limiter.allow("k")
    assert not limiter.allow("k")
    assert limiter.retry_after("k") > 0
    now[0] = 10.5
    assert limiter.allow("k")
    assert limiter.retry_after("unused") == 0
