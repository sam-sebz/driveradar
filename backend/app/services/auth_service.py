from collections.abc import Callable
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import ConflictError, UnauthorizedError
from app.core.security import (
    DUMMY_HASH,
    InvalidTokenError,
    create_access_token,
    decode_access_token,
    hash_password,
    hash_refresh_token,
    new_refresh_token,
    verify_password,
)
from app.db.types import utcnow
from app.models.user import ROLE_STUDENT, User
from app.repositories.token_repo import RefreshTokenRepository
from app.repositories.user_repo import UserRepository
from app.schemas.auth import LoginRequest, SignupRequest, TokenResponse

INVALID_LOGIN = "Invalid email or password"


class AuthService:
    def __init__(
        self, db: Session, settings: Settings, clock: Callable[[], datetime] = utcnow
    ) -> None:
        self.db = db
        self.settings = settings
        self.clock = clock
        self.users = UserRepository(db)
        self.tokens = RefreshTokenRepository(db)

    @property
    def _secret(self) -> str:
        return self.settings.jwt_secret.get_secret_value()

    def signup(self, req: SignupRequest) -> TokenResponse:
        if self.users.get_by_email(req.email) is not None:
            raise ConflictError("An account with this email already exists")
        user = self.users.add(
            User(
                email=req.email,
                password_hash=hash_password(req.password),
                name=req.name,
                role=ROLE_STUDENT,
                skills=[],
            )
        )
        tokens = self._issue(user)
        self.db.commit()
        return tokens

    def login(self, req: LoginRequest) -> TokenResponse:
        user = self.users.get_by_email(req.email)
        if user is None:
            verify_password(req.password, DUMMY_HASH)  # same work as a real check
            raise UnauthorizedError(INVALID_LOGIN)
        if not verify_password(req.password, user.password_hash):
            raise UnauthorizedError(INVALID_LOGIN)
        tokens = self._issue(user)
        self.db.commit()
        return tokens

    def refresh(self, refresh_token: str) -> TokenResponse:
        now = self.clock()
        record = self.tokens.get_by_hash(hash_refresh_token(refresh_token))
        if record is None:
            raise UnauthorizedError("Invalid refresh token")
        if record.revoked_at is not None:
            # A rotated token was used again: someone may have stolen it. Log out everywhere.
            self.tokens.revoke_all_for_user(record.user_id, now)
            self.db.commit()
            raise UnauthorizedError("Refresh token was already used; please log in again")
        if record.expires_at <= now:
            raise UnauthorizedError("Refresh token expired; please log in again")
        user = self.users.get(record.user_id)
        if user is None:  # pragma: no cover - FK cascade deletes tokens with the user
            raise UnauthorizedError("Invalid refresh token")
        record.revoked_at = now
        tokens = self._issue(user)
        self.db.commit()
        return tokens

    def user_from_access_token(self, token: str) -> User:
        try:
            claims = decode_access_token(token, self._secret)
        except InvalidTokenError as exc:
            raise UnauthorizedError("Invalid or expired access token") from exc
        user = self.users.get(claims.user_id)
        if user is None:
            raise UnauthorizedError("User no longer exists")
        return user

    def _issue(self, user: User) -> TokenResponse:
        now = self.clock()
        minutes = self.settings.access_token_minutes
        access = create_access_token(user.id, user.role, self._secret, minutes, now)
        refresh, refresh_hash = new_refresh_token()
        self.tokens.add(
            user.id, refresh_hash, now + timedelta(days=self.settings.refresh_token_days)
        )
        return TokenResponse(
            access_token=access, refresh_token=refresh, expires_in=minutes * 60, role=user.role
        )
