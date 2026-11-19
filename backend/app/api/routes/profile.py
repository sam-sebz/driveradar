from fastapi import APIRouter, Depends

from app.api.deps import get_current_user, get_profile_service
from app.models.user import User
from app.schemas.profile import ProfileOut, ProfileUpdate
from app.services.profile_service import ProfileService

router = APIRouter(prefix="/me", tags=["profile"])


@router.get("/profile", response_model=ProfileOut)
def get_profile(user: User = Depends(get_current_user)) -> User:
    return user


@router.put("/profile", response_model=ProfileOut)
def update_profile(
    body: ProfileUpdate,
    user: User = Depends(get_current_user),
    profiles: ProfileService = Depends(get_profile_service),
) -> User:
    return profiles.update(user, body)
