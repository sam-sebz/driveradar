from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.seed import DEMO_PASSWORD, DEMO_STUDENT, seed
from tests.conftest import SAMPLES


def test_seed_is_idempotent_and_demo_login_works(
    app: FastAPI, client: TestClient, settings: Settings
) -> None:
    with app.state.db.session_factory() as db:
        first = seed(db, settings, SAMPLES)
    with app.state.db.session_factory() as db:
        second = seed(db, settings, SAMPLES)
    assert first == {"users_created": 2, "drives_created": 5}
    assert second == {"users_created": 0, "drives_created": 0}

    res = client.post("/auth/login", json={"email": DEMO_STUDENT, "password": DEMO_PASSWORD})
    headers = {"Authorization": f"Bearer {res.json()['access_token']}"}
    drives = client.get("/drives", headers=headers).json()["drives"]
    assert len(drives) == 5
