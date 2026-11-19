import uuid
from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.drive import Drive
from app.models.user_drive import UserDrive


class DriveRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, drive: Drive) -> Drive:
        self.db.add(drive)
        self.db.flush()
        return drive

    def delete(self, drive: Drive) -> None:
        self.db.delete(drive)
        self.db.flush()

    def count_with_stored_path(self, stored_path: str) -> int:
        stmt = select(func.count()).select_from(Drive).where(Drive.stored_path == stored_path)
        return int(self.db.scalar(stmt) or 0)

    def unique_drives(self) -> list[Drive]:
        """One drive per distinct notice role (same content hash = same notice role).

        Used only for anonymous aggregate analytics; nothing about the uploader is read.
        """
        seen: set[str] = set()
        out: list[Drive] = []
        for drive in self.db.scalars(select(Drive).order_by(Drive.created_at)):
            if drive.content_hash not in seen:
                seen.add(drive.content_hash)
                out.append(drive)
        return out


class UserDriveRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, link: UserDrive) -> UserDrive:
        self.db.add(link)
        self.db.flush()
        return link

    def get(self, user_id: uuid.UUID, drive_id: uuid.UUID) -> UserDrive | None:
        return self.db.get(UserDrive, (user_id, drive_id))

    def list_for_user(self, user_id: uuid.UUID) -> Sequence[UserDrive]:
        stmt = (
            select(UserDrive)
            .join(UserDrive.drive)
            .where(UserDrive.user_id == user_id)
            # Soonest deadline first; drives without a deadline go last.
            .order_by(Drive.deadline.is_(None), Drive.deadline, Drive.created_at.desc())
        )
        return self.db.scalars(stmt).unique().all()
