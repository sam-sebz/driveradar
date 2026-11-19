from sqlalchemy.orm import Session

from app.domain.skills.catalog import default_catalog
from app.models.user import User
from app.schemas.profile import ProfileUpdate
from app.services.drive_service import DriveService


class ProfileService:
    def __init__(self, db: Session, drives: DriveService) -> None:
        self.db = db
        self.drives = drives

    def update(self, user: User, data: ProfileUpdate) -> User:
        user.name = data.name
        user.branch = data.branch.strip() if data.branch else None
        user.batch = data.batch
        user.cgpa = data.cgpa
        user.pct_10 = data.pct_10
        user.pct_12 = data.pct_12
        user.backlogs = data.backlogs
        user.skills = default_catalog().normalise_list(data.skills)
        # A new CGPA or skill changes eligibility and match for every saved drive.
        self.drives.recompute_for_user(user)
        self.db.commit()
        return user
