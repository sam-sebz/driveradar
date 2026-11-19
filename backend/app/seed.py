"""Demo data loader. Runs on container start when SEED_DEMO_DATA=true. Safe to re-run.

Creates:
- demo@driveradar.dev / Demo@1234 (student, with a profile)
- coordinator@driveradar.dev / Demo@1234 (coordinator, for the analytics page)
and uploads the three SYNTHETIC notices from samples/synthetic/ for the demo student.
"""

import logging
import os
import sys
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.core.security import hash_password
from app.db.session import Database
from app.domain.skills.catalog import default_catalog
from app.models.user import ROLE_COORDINATOR, ROLE_STUDENT, User
from app.repositories.drive_repo import UserDriveRepository
from app.repositories.user_repo import UserRepository
from app.services.drive_service import DriveService
from app.services.extractor_factory import build_extractor
from app.services.storage import LocalFileStore

logger = logging.getLogger("driveradar.seed")

DEMO_PASSWORD = "Demo@1234"  # noqa: S105 - documented public demo account
DEMO_STUDENT = "demo@driveradar.dev"
DEMO_COORDINATOR = "coordinator@driveradar.dev"
DEFAULT_SAMPLES = Path(__file__).resolve().parents[2] / "samples" / "synthetic"


def _get_or_create(db: Session, email: str, role: str, **profile: object) -> tuple[User, bool]:
    users = UserRepository(db)
    existing = users.get_by_email(email)
    if existing is not None:
        return existing, False
    user = User(
        email=email, password_hash=hash_password(DEMO_PASSWORD), role=role, skills=[], **profile
    )
    return users.add(user), True


def seed(db: Session, settings: Settings, samples_dir: Path) -> dict[str, int]:
    student, created_student = _get_or_create(
        db,
        DEMO_STUDENT,
        ROLE_STUDENT,
        name="Demo Student",
        branch="CSE",
        batch=2026,
        cgpa=8.2,
        pct_10=91.0,
        pct_12=88.5,
        backlogs=0,
    )
    if created_student:
        student.skills = default_catalog().normalise_list(
            ["Java", "Python", "SQL", "Git", "React", "Docker", "Linux"]
        )
    _, created_coord = _get_or_create(
        db, DEMO_COORDINATOR, ROLE_COORDINATOR, name="Demo Coordinator"
    )
    db.commit()

    uploaded = 0
    if not UserDriveRepository(db).list_for_user(student.id):
        service = DriveService(
            db, settings, build_extractor(settings), LocalFileStore(settings.upload_dir)
        )
        for path in sorted(samples_dir.glob("*")):
            if path.suffix.lower() in {".pdf", ".docx", ".xlsx"}:
                uploaded += len(service.upload_file(student, path.name, path.read_bytes()))
    return {"users_created": int(created_student) + int(created_coord), "drives_created": uploaded}


def main() -> int:
    settings = get_settings()
    configure_logging(settings.log_level)
    if not settings.seed_demo_data:
        logger.info("seed_skipped", extra={"reason": "SEED_DEMO_DATA is not true"})
        return 0
    samples = Path(os.environ.get("SAMPLES_DIR", str(DEFAULT_SAMPLES)))
    database = Database(settings.database_url)
    with database.session_factory() as db:
        result = seed(db, settings, samples)
    database.engine.dispose()
    logger.info("seed_done", extra=result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
