"""Upload -> parse -> extract -> evaluate -> store. All business logic for drives lives here."""

import hashlib
import logging
import uuid
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import PurePath
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import BadRequestError, NotFoundError
from app.db.types import utcnow
from app.domain.eligibility.engine import Requirements, StudentProfile, evaluate
from app.domain.extraction.base import Extractor
from app.domain.extraction.models import IST, DriveInfo
from app.domain.extraction.postprocess import normalise_drive
from app.domain.parsing.documents import (
    EmptyDocumentError,
    ParsedDocument,
    UnsupportedFileError,
    parse_bytes,
    parse_text,
)
from app.domain.roles import categorise_role
from app.domain.skills.matcher import match_skills
from app.models.drive import Drive
from app.models.user import User
from app.models.user_drive import UserDrive
from app.repositories.drive_repo import DriveRepository, UserDriveRepository
from app.schemas.drive import DriveDetail, RuleOut
from app.services.storage import LocalFileStore

logger = logging.getLogger("driveradar.drives")

INFO_FIELDS = tuple(DriveInfo.model_fields)
MAX_TEXT_CHARS = 200_000


def content_hash(text: str) -> str:
    normalised = " ".join(text.lower().split())
    return hashlib.sha256(normalised.encode("utf-8")).hexdigest()


def drive_to_info(drive: Drive) -> DriveInfo:
    values = {f: getattr(drive, f) for f in INFO_FIELDS}
    if drive.deadline is not None:
        values["deadline"] = drive.deadline.astimezone(IST)  # stored UTC, shown in IST
    return DriveInfo.model_validate(values)


def safe_filename(name: str | None) -> str | None:
    if not name:
        return None
    base = PurePath(name.replace("\\", "/")).name.strip()
    return base[:255] or None


class DriveService:
    def __init__(
        self,
        db: Session,
        settings: Settings,
        extractor: Extractor,
        storage: LocalFileStore,
        clock: Callable[[], datetime] = utcnow,
    ) -> None:
        self.db = db
        self.settings = settings
        self.extractor = extractor
        self.storage = storage
        self.clock = clock
        self.drives = DriveRepository(db)
        self.links = UserDriveRepository(db)

    # ---- uploads ---------------------------------------------------------------------

    def upload_file(self, user: User, filename: str, content: bytes) -> list[UserDrive]:
        if len(content) > self.settings.max_upload_bytes:
            raise BadRequestError(
                "FILE_TOO_LARGE", f"File is larger than {self.settings.max_upload_mb} MB", 413
            )
        if not content:
            raise BadRequestError("EMPTY_FILE", "The uploaded file is empty", 422)
        try:
            parsed = parse_bytes(filename, content)
        except UnsupportedFileError as exc:
            raise BadRequestError("UNSUPPORTED_FILE", str(exc), 415) from exc
        except EmptyDocumentError as exc:
            raise BadRequestError("EMPTY_DOCUMENT", str(exc), 422) from exc
        except Exception as exc:  # a corrupt file must not become a 500
            logger.warning("parse_failed", extra={"file_type": filename.rsplit(".", 1)[-1]})
            raise BadRequestError("UNREADABLE_FILE", "Could not read this file", 422) from exc
        stored = self.storage.save(content, parsed.file_type)
        try:
            return self._create(user, parsed, safe_filename(filename), stored)
        except Exception:
            self.storage.delete(stored)
            raise

    def upload_text(self, user: User, text: str) -> list[UserDrive]:
        if len(text) > MAX_TEXT_CHARS:
            raise BadRequestError("TEXT_TOO_LONG", "Pasted text is too long", 413)
        try:
            parsed = parse_text(text)
        except EmptyDocumentError as exc:
            raise BadRequestError("EMPTY_DOCUMENT", str(exc), 422) from exc
        return self._create(user, parsed, None, None)

    def _create(
        self, user: User, parsed: ParsedDocument, filename: str | None, stored_path: str | None
    ) -> list[UserDrive]:
        links: list[UserDrive] = []
        for block in parsed.role_blocks:
            result = self.extractor.run(block)
            info = normalise_drive(result.info)
            drive = Drive(
                uploaded_by=user.id,
                **info.model_dump(),
                role_category=categorise_role(info.role),
                raw_text=block,
                source_filename=filename,
                stored_path=stored_path,
                content_hash=content_hash(block),
                extraction_provider=result.provider,
                extracted_original=info.model_dump(mode="json"),
            )
            self.drives.add(drive)
            link = UserDrive(user_id=user.id, drive_id=drive.id, status="saved")
            link.drive = drive
            self._evaluate(user, link)
            links.append(self.links.add(link))
        self.db.commit()
        logger.info(
            "drives_created",
            extra={
                "count": len(links),
                "file_type": parsed.file_type,
                "providers": sorted({d.drive.extraction_provider for d in links}),
            },
        )
        return links

    # ---- reads and edits --------------------------------------------------------------

    def list_for(
        self,
        user: User,
        status: str | None = None,
        eligibility: str | None = None,
        closing_soon: bool | None = None,
    ) -> list[UserDrive]:
        now = self.clock()
        out = []
        for link in self.links.list_for_user(user.id):
            if status and link.status != status:
                continue
            if eligibility and link.eligibility != eligibility:
                continue
            if closing_soon and not self._closes_within_24h(link.drive, now):
                continue
            out.append(link)
        return out

    def get(self, user: User, drive_id: uuid.UUID) -> UserDrive:
        link = self.links.get(user.id, drive_id)
        if link is None:  # also covers "belongs to someone else": do not reveal it exists
            raise NotFoundError("Drive not found")
        return link

    def update_status(self, user: User, drive_id: uuid.UUID, status: str) -> UserDrive:
        link = self.get(user, drive_id)
        link.status = status
        self.db.commit()
        return link

    def edit(self, user: User, drive_id: uuid.UUID, info: DriveInfo) -> UserDrive:
        """Student corrects extracted fields; eligibility and match are recomputed."""
        link = self.get(user, drive_id)
        cleaned = normalise_drive(info)
        for field, value in cleaned.model_dump().items():
            setattr(link.drive, field, value)
        link.drive.role_category = categorise_role(cleaned.role)
        self._evaluate(user, link)
        self.db.commit()
        return link

    def delete(self, user: User, drive_id: uuid.UUID) -> None:
        link = self.get(user, drive_id)
        drive = link.drive
        stored = drive.stored_path
        self.drives.delete(drive)
        # An XLSX with 3 roles shares one stored file; delete it with the last role.
        if stored and self.drives.count_with_stored_path(stored) == 0:
            self.storage.delete(stored)
        self.db.commit()

    def recompute_for_user(self, user: User) -> int:
        links = self.links.list_for_user(user.id)
        for link in links:
            self._evaluate(user, link)
        return len(links)

    # ---- helpers ---------------------------------------------------------------------

    def _evaluate(self, user: User, link: UserDrive) -> None:
        d = link.drive
        result = evaluate(
            StudentProfile(
                branch=user.branch,
                batch=user.batch,
                cgpa=user.cgpa,
                pct_10=user.pct_10,
                pct_12=user.pct_12,
                backlogs=user.backlogs,
            ),
            Requirements(
                min_cgpa=d.min_cgpa,
                min_ug_percent=d.min_ug_percent,
                min_percent_10th=d.min_percent_10th,
                min_percent_12th=d.min_percent_12th,
                max_active_backlogs=d.max_active_backlogs,
                eligible_branches=d.eligible_branches,
                eligible_batch=d.eligible_batch,
            ),
            cgpa_to_percent_factor=self.settings.cgpa_to_percent_factor,
        )
        match = match_skills(user.skills or [], d.required_skills or [])
        link.eligibility = result.status.value
        link.eligibility_reasons = [r.to_dict() for r in result.rules]
        link.match_score = match.score
        link.matched_skills = match.matched
        link.missing_skills = match.missing

    @staticmethod
    def _closes_within_24h(drive: Drive, now: datetime) -> bool:
        return drive.deadline is not None and now <= drive.deadline <= now + timedelta(hours=24)

    def to_detail(self, link: UserDrive) -> DriveDetail:
        now = self.clock()
        d = link.drive
        reasons: list[dict[str, Any]] = link.eligibility_reasons or []
        return DriveDetail(
            id=d.id,
            info=drive_to_info(d),
            role_category=d.role_category,
            source_filename=d.source_filename,
            extraction_provider=d.extraction_provider,
            created_at=d.created_at,
            eligibility=link.eligibility,  # DB check constraint keeps it valid
            eligibility_reasons=[RuleOut.model_validate(r) for r in reasons],
            match_score=link.match_score,
            matched_skills=list(link.matched_skills or []),
            missing_skills=list(link.missing_skills or []),
            status=link.status,  # DB check constraint keeps it valid
            closes_within_24h=self._closes_within_24h(d, now),
            is_closed=d.deadline is not None and d.deadline < now,
        )
