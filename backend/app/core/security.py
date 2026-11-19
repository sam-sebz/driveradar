"""Password hashing (bcrypt) and tokens (JWT access tokens + opaque refresh tokens)."""

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    # bcrypt only reads the first 72 bytes; the signup schema caps passwords at 72 bytes.
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("ascii"))
    except ValueError:
        return False


# A real bcrypt hash used to spend the same time when the email does not exist,
# so response timing does not reveal which emails are registered.
# (It is the hash of a random throwaway string, not of any account's password.)
DUMMY_HASH = "$2b$12$acEIntQZ1lsdfTmGgt76/uK4QisD.3vc1CN7R6AQ3egk.hhIqzKfy"


@dataclass(frozen=True)
class AccessClaims:
    user_id: uuid.UUID
    role: str


class InvalidTokenError(Exception):
    pass


def create_access_token(
    user_id: uuid.UUID, role: str, secret: str, minutes: int, now: datetime | None = None
) -> str:
    issued = now or datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "role": role,
        "type": "access",
        "iat": issued,
        "exp": issued + timedelta(minutes=minutes),
    }
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


def decode_access_token(token: str, secret: str) -> AccessClaims:
    try:
        payload = jwt.decode(
            token, secret, algorithms=[ALGORITHM], options={"require": ["exp", "sub", "type"]}
        )
    except jwt.PyJWTError as exc:
        raise InvalidTokenError(str(exc)) from exc
    if payload.get("type") != "access":
        raise InvalidTokenError("not an access token")
    try:
        return AccessClaims(user_id=uuid.UUID(payload["sub"]), role=str(payload.get("role")))
    except ValueError as exc:
        raise InvalidTokenError("bad subject") from exc


def new_refresh_token() -> tuple[str, str]:
    """Return (token for the client, sha256 hash to store)."""
    token = secrets.token_urlsafe(32)
    return token, hash_refresh_token(token)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
