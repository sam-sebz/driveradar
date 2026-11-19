from fastapi import APIRouter, Depends, Request, status

from app.api.deps import get_auth_service
from app.core.errors import AppError
from app.core.rate_limit import RateLimiter
from app.schemas.auth import LoginRequest, RefreshRequest, SignupRequest, TokenResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def signup(body: SignupRequest, auth: AuthService = Depends(get_auth_service)) -> TokenResponse:
    return auth.signup(body)


@router.post("/login", response_model=TokenResponse)
def login(
    body: LoginRequest, request: Request, auth: AuthService = Depends(get_auth_service)
) -> TokenResponse:
    limiter: RateLimiter = request.app.state.login_limiter
    client = request.client.host if request.client else "unknown"
    key = f"{client}:{body.email.lower()}"
    if not limiter.allow(key):
        raise AppError(
            429,
            "RATE_LIMITED",
            f"Too many login attempts. Try again in {limiter.retry_after(key)} s.",
        )
    return auth.login(body)


@router.post("/refresh", response_model=TokenResponse)
def refresh(body: RefreshRequest, auth: AuthService = Depends(get_auth_service)) -> TokenResponse:
    return auth.refresh(body.refresh_token)
