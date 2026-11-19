"""End-to-end smoke test against a running stack. Standard library only.

    python scripts/smoke.py [--api http://localhost:8000] [--web http://localhost:5173]

Checks: health, sign up, log in, profile update, the main feature (upload a synthetic PDF
and get extraction + eligibility + skill match), dashboard listing, and error cases
(unsupported file -> 415, no token -> 401). Exits non-zero on the first failure.
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "samples" / "synthetic" / "kaveri_analytics_notice.pdf"


class SmokeFailure(Exception):
    pass


def call(method: str, url: str, body: bytes | None = None,
         headers: dict[str, str] | None = None) -> tuple[int, Any]:
    req = urllib.request.Request(url, data=body, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=30) as res:  # noqa: S310 - our own URL
            raw = res.read()
            status = res.status
    except urllib.error.HTTPError as err:
        raw = err.read()
        status = err.code
    try:
        return status, json.loads(raw) if raw else None
    except json.JSONDecodeError:
        return status, raw.decode("utf-8", "replace")


def post_json(url: str, payload: dict[str, Any], token: str | None = None) -> tuple[int, Any]:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return call("POST", url, json.dumps(payload).encode(), headers)


def multipart(field: str, filename: str, content: bytes) -> tuple[bytes, str]:
    boundary = uuid.uuid4().hex
    body = (
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"{field}\"; "
        f"filename=\"{filename}\"\r\nContent-Type: application/octet-stream\r\n\r\n"
    ).encode() + content + f"\r\n--{boundary}--\r\n".encode()
    return body, f"multipart/form-data; boundary={boundary}"


def check(name: str, ok: bool, detail: Any = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" -> {detail}" if not ok else ""))
    if not ok:
        raise SmokeFailure(name)


def wait_for_health(api: str, seconds: int) -> None:
    deadline = time.time() + seconds
    while time.time() < deadline:
        try:
            status, body = call("GET", f"{api}/health")
            if status == 200 and body == {"status": "ok"}:
                return
        except (urllib.error.URLError, ConnectionError, TimeoutError):
            pass
        time.sleep(2)
    raise SmokeFailure(f"{api}/health did not become healthy in {seconds}s")


def run(api: str, web: str | None) -> None:
    wait_for_health(api, 90)
    status, body = call("GET", f"{api}/health")
    check("GET /health returns ok", status == 200 and body == {"status": "ok"}, body)

    email = f"smoke-{uuid.uuid4().hex[:8]}@example.com"
    password = "Smoke1234!"
    status, body = post_json(f"{api}/auth/signup", {"email": email, "password": password})
    check("POST /auth/signup creates a student", status == 201 and body["role"] == "student", body)

    status, body = post_json(f"{api}/auth/login", {"email": email, "password": password})
    check("POST /auth/login returns tokens", status == 200 and "access_token" in body, body)
    token = body["access_token"]
    auth = {"Authorization": f"Bearer {token}"}

    profile = {"name": "Smoke", "branch": "CSE", "batch": 2026, "cgpa": 8.2, "pct_10": 90,
               "pct_12": 88, "backlogs": 0, "skills": ["Java", "Python", "Git"]}
    status, body = call("PUT", f"{api}/me/profile", json.dumps(profile).encode(),
                        {**auth, "Content-Type": "application/json"})
    check("PUT /me/profile saves the profile", status == 200 and body["cgpa"] == 8.2, body)

    data, ctype = multipart("file", SAMPLE.name, SAMPLE.read_bytes())
    status, body = call("POST", f"{api}/drives/upload", data, {**auth, "Content-Type": ctype})
    check("POST /drives/upload accepts the synthetic PDF", status == 201, body)
    drive = body["drives"][0]
    check("extraction found the company",
          drive["info"]["company"] == "Kaveri Analytics Pvt. Ltd.", drive["info"])
    check("eligibility engine says eligible", drive["eligibility"] == "eligible", drive)
    check("skill match lists missing skills",
          drive["missing_skills"] == ["SQL", "Data Structures"], drive["missing_skills"])

    status, body = call("GET", f"{api}/drives", headers=auth)
    check("GET /drives lists the uploaded drive",
          status == 200 and any(d["id"] == drive["id"] for d in body["drives"]), body)

    data, ctype = multipart("file", "malware.pdf", b"MZ\x90\x00 not a pdf")
    status, body = call("POST", f"{api}/drives/upload", data, {**auth, "Content-Type": ctype})
    check("unsupported file is rejected with 415 + error shape",
          status == 415 and body["error"]["code"] == "UNSUPPORTED_FILE", body)

    status, body = call("GET", f"{api}/drives")
    check("missing token is rejected with 401", status == 401, body)

    status, _ = call("DELETE", f"{api}/drives/{drive['id']}", headers=auth)
    check("DELETE /drives/{id} cleans up", status == 204)

    if web:
        status, body = call("GET", web)
        check("frontend serves the app", status == 200 and "DriveRadar" in str(body), status)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default="http://localhost:8000")
    parser.add_argument("--web", default="http://localhost:5173",
                        help="frontend URL; pass '' to skip")
    args = parser.parse_args()
    try:
        run(args.api.rstrip("/"), args.web or None)
    except SmokeFailure as exc:
        print(f"SMOKE TEST FAILED: {exc}")
        return 1
    print("SMOKE TEST PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
