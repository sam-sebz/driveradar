from collections.abc import Iterator

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import ForbiddenError, UnauthorizedError
from app.domain.extraction.base import Extractor
from app.models.user import ROLE_COORDINATOR, ROLE_STUDENT, User
from app.services.analytics_service import AnalyticsService
from app.services.auth_service import AuthService
from app.services.drive_service import DriveService
from app.services.profile_service import ProfileService
from app.services.storage import LocalFileStore


def get_settings_dep(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_db(request: Request) -> Iterator[Session]:
    yield from request.app.state.db.session()


def get_auth_service(
    db: Session = Depends(get_db), settings: Settings = Depends(get_settings_dep)
) -> AuthService:
    return AuthService(db, settings)


def get_drive_service(
    request: Request, db: Session = Depends(get_db), settings: Settings = Depends(get_settings_dep)
) -> DriveService:
    extractor: Extractor = request.app.state.extractor
    storage: LocalFileStore = request.app.state.storage
    return DriveService(db, settings, extractor, storage)


def get_profile_service(
    db: Session = Depends(get_db), drives: DriveService = Depends(get_drive_service)
) -> ProfileService:
    return ProfileService(db, drives)


def get_analytics_service(db: Session = Depends(get_db)) -> AnalyticsService:
    return AnalyticsService(db)


def get_current_user(request: Request, auth: AuthService = Depends(get_auth_service)) -> User:
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise UnauthorizedError("Missing bearer token")
    return auth.user_from_access_token(token.strip())


def require_student(user: User = Depends(get_current_user)) -> User:
    if user.role != ROLE_STUDENT:
        raise ForbiddenError("Only students can do this")
    return user


def require_coordinator(user: User = Depends(get_current_user)) -> User:
    if user.role != ROLE_COORDINATOR:
        raise ForbiddenError("Only placement coordinators can see analytics")
    return user
