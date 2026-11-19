"""End-to-end API tests for upload -> extraction -> eligibility -> dashboard (mock provider)."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.conftest import SAMPLES, Signup

PROFILE: dict[str, Any] = {
    "name": "Demo Student",
    "branch": "CSE",
    "batch": 2026,
    "cgpa": 8.2,
    "pct_10": 91,
    "pct_12": 88.5,
    "backlogs": 0,
    "skills": ["java", "Postgres", "Python", "Git", "Docker"],
}


def _upload(client: TestClient, headers: dict[str, str], name: str) -> list[dict]:  # type: ignore[type-arg]
    path = SAMPLES / name
    res = client.post(
        "/drives/upload", headers=headers, files={"file": (path.name, path.read_bytes())}
    )
    assert res.status_code == 201, res.text
    drives: list[dict] = res.json()["drives"]  # type: ignore[type-arg]
    return drives


def test_upload_pdf_end_to_end(client: TestClient, signup: Signup) -> None:
    headers = signup(**PROFILE)
    [drive] = _upload(client, headers, "kaveri_analytics_notice.pdf")
    info = drive["info"]
    assert info["company"] == "Kaveri Analytics Pvt. Ltd."
    assert info["deadline"] == "2026-11-28T23:59:00+05:30"
    assert drive["extraction_provider"] == "mock"
    assert drive["eligibility"] == "eligible"
    assert drive["matched_skills"] == ["Java", "Python", "Git"]
    assert drive["missing_skills"] == ["SQL", "Data Structures"]
    assert drive["match_score"] == 0.6
    assert drive["status"] == "saved"
    rules = {r["rule"]: r["status"] for r in drive["eligibility_reasons"]}
    assert rules["cgpa"] == "pass" and rules["ug_percent"] == "not_specified"


def test_xlsx_with_three_roles_creates_three_drives(client: TestClient, signup: Signup) -> None:
    headers = signup(**PROFILE)
    drives = _upload(client, headers, "thamirabarani_systems_3roles.xlsx")
    by_role = {d["info"]["role"]: d for d in drives}
    assert set(by_role) == {"Graduate Engineer Trainee", "Data Analyst", "Embedded Engineer"}
    assert by_role["Embedded Engineer"]["eligibility"] == "not_eligible"  # CSE not in ECE/EEE/EIE
    assert by_role["Data Analyst"]["eligibility"] == "eligible"


def test_docx_and_pasted_text(client: TestClient, signup: Signup) -> None:
    headers = signup(**PROFILE)
    [docx] = _upload(client, headers, "nilgiri_cloudworks_notice.docx")
    assert docx["info"]["stipend_per_month"] == 30000
    assert docx["eligibility"] == "eligible"  # CSE is within "Computer Science or equivalent"

    res = client.post(
        "/drives/upload",
        headers=headers,
        data={"text": "Company: Paste Co\nRole: SDE\nCGPA: 9.0 minimum"},
    )
    assert res.status_code == 201
    [pasted] = res.json()["drives"]
    assert pasted["eligibility"] == "not_eligible"
    assert pasted["source_filename"] is None


def test_profile_change_recomputes_eligibility(client: TestClient, signup: Signup) -> None:
    headers = signup(**PROFILE)
    [drive] = _upload(client, headers, "kaveri_analytics_notice.pdf")
    assert drive["eligibility"] == "eligible"
    client.put(
        "/me/profile",
        headers=headers,
        json={**PROFILE, "cgpa": 6.5, "skills": PROFILE["skills"] + ["SQL"]},
    )
    after = client.get(f"/drives/{drive['id']}", headers=headers).json()
    assert after["eligibility"] == "not_eligible"
    assert "SQL" in after["matched_skills"]


def test_dashboard_sorted_by_deadline_and_filters(client: TestClient, signup: Signup) -> None:
    headers = signup(**PROFILE)
    _upload(client, headers, "kaveri_analytics_notice.pdf")  # 28 Nov
    _upload(client, headers, "nilgiri_cloudworks_notice.docx")  # 2 Dec
    _upload(client, headers, "thamirabarani_systems_3roles.xlsx")  # 25 Nov x3
    res = client.post("/drives/upload", headers=headers, data={"text": "Role: No deadline"})
    assert res.status_code == 201

    drives = client.get("/drives", headers=headers).json()["drives"]
    deadlines = [d["info"]["deadline"] for d in drives]
    assert deadlines[-1] is None
    dated = [datetime.fromisoformat(x) for x in deadlines[:-1]]
    assert dated == sorted(dated)

    eligible = client.get("/drives?eligibility=not_eligible", headers=headers).json()["drives"]
    assert {d["info"]["role"] for d in eligible} == {"Embedded Engineer"}


def test_status_edit_and_delete(client: TestClient, signup: Signup, app: FastAPI) -> None:
    headers = signup(**PROFILE)
    drives = _upload(client, headers, "thamirabarani_systems_3roles.xlsx")
    first = drives[0]

    res = client.patch(f"/drives/{first['id']}/status", headers=headers, json={"status": "applied"})
    assert res.json()["status"] == "applied"
    bad = client.patch(f"/drives/{first['id']}/status", headers=headers, json={"status": "hired"})
    assert bad.status_code == 422

    # "Edit if wrong": student fixes the CGPA cut-off; eligibility is recomputed.
    info = {**first["info"], "min_cgpa": 9.5}
    edited = client.patch(f"/drives/{first['id']}", headers=headers, json=info)
    assert edited.status_code == 200
    assert edited.json()["eligibility"] == "not_eligible"
    assert edited.json()["info"]["min_cgpa"] == 9.5

    storage = app.state.storage
    stored = list(storage.root.iterdir())
    assert len(stored) == 1  # three roles share one stored file
    for d in drives[:2]:
        assert client.delete(f"/drives/{d['id']}", headers=headers).status_code == 204
    assert storage.exists(stored[0].name)
    assert client.delete(f"/drives/{drives[2]['id']}", headers=headers).status_code == 204
    assert not storage.exists(stored[0].name)
    assert client.get(f"/drives/{first['id']}", headers=headers).status_code == 404


def test_students_cannot_see_each_others_drives(client: TestClient, signup: Signup) -> None:
    alice = signup(**PROFILE)
    bob = signup(**PROFILE)
    [drive] = _upload(client, alice, "kaveri_analytics_notice.pdf")
    assert client.get(f"/drives/{drive['id']}", headers=bob).status_code == 404
    assert client.delete(f"/drives/{drive['id']}", headers=bob).status_code == 404
    assert client.get("/drives", headers=bob).json()["drives"] == []


def test_upload_errors(client: TestClient, signup: Signup, tmp_path: Path) -> None:
    headers = signup()
    exe = client.post(
        "/drives/upload", headers=headers, files={"file": ("virus.pdf", b"MZ\x90\x00binary")}
    )
    assert exe.status_code == 415
    assert exe.json()["error"]["code"] == "UNSUPPORTED_FILE"

    big = client.post(
        "/drives/upload",
        headers=headers,
        files={"file": ("big.pdf", b"%PDF" + b"0" * (10 * 1024 * 1024))},
    )
    assert big.status_code == 413
    assert big.json()["error"]["code"] == "FILE_TOO_LARGE"

    nothing = client.post("/drives/upload", headers=headers, data={"text": "   "})
    assert nothing.status_code == 422

    corrupt = client.post(
        "/drives/upload",
        headers=headers,
        files={"file": ("broken.pdf", b"%PDF-1.4 not really a pdf")},
    )
    assert corrupt.status_code == 422
    assert corrupt.json()["error"]["code"] == "UNREADABLE_FILE"

    empty = client.post("/drives/upload", headers=headers, files={"file": ("e.pdf", b"")})
    assert empty.status_code == 422


def test_coordinator_cannot_upload_and_student_cannot_see_analytics(
    client: TestClient, signup: Signup, coordinator: dict[str, str]
) -> None:
    student = signup()
    assert client.get("/analytics/summary", headers=student).status_code == 403
    res = client.post("/drives/upload", headers=coordinator, data={"text": "Role: SDE"})
    assert res.status_code == 403


def test_analytics_are_aggregated_and_deduplicated(
    client: TestClient, signup: Signup, coordinator: dict[str, str]
) -> None:
    a = signup(**PROFILE)
    b = signup(**PROFILE)
    _upload(client, a, "kaveri_analytics_notice.pdf")
    _upload(client, b, "kaveri_analytics_notice.pdf")  # same notice, second student
    _upload(client, a, "thamirabarani_systems_3roles.xlsx")

    summary = client.get("/analytics/summary", headers=coordinator).json()
    assert summary["total_drives"] == 4  # the duplicate PDF is counted once
    assert summary["total_companies"] == 2
    # CTC midpoints: 7.25 (6.5-8), 4.5, 6.0, 6.25 (5.5-7) -> median 6.125 -> 6.12 or 6.13
    assert summary["median_ctc_lpa"] in (6.12, 6.13)
    assert summary["drives_with_bond"] == 4

    skills = client.get("/analytics/skills", headers=coordinator).json()
    assert skills["total_drives"] == 4
    top = {s["skill"]: s["count"] for s in skills["top_skills"]}
    assert top["Python"] == 2 and top["C"] == 2
    assert "email" not in str(summary) and "@" not in str(skills)


def test_closing_soon_badge(client: TestClient, signup: Signup) -> None:
    headers = signup(**PROFILE)
    soon = (datetime.now(timezone.utc) + timedelta(hours=5)).astimezone(
        timezone(timedelta(hours=5, minutes=30))
    )
    text = f"Company: Soon Ltd\nDeadline: {soon:%d %B %Y %I:%M %p}"
    res = client.post("/drives/upload", headers=headers, data={"text": text})
    [drive] = res.json()["drives"]
    assert drive["closes_within_24h"] is True
    assert drive["is_closed"] is False
    listed = client.get("/drives?closing_soon=true", headers=headers).json()["drives"]
    assert [d["id"] for d in listed] == [drive["id"]]
