from fastapi import APIRouter, Depends

from app.api.deps import get_analytics_service, require_coordinator
from app.models.user import User
from app.schemas.analytics import SkillsAnalytics, SummaryAnalytics
from app.services.analytics_service import AnalyticsService

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/skills", response_model=SkillsAnalytics)
def top_skills(
    _: User = Depends(require_coordinator),
    analytics: AnalyticsService = Depends(get_analytics_service),
) -> SkillsAnalytics:
    return analytics.skills()


@router.get("/summary", response_model=SummaryAnalytics)
def summary(
    _: User = Depends(require_coordinator),
    analytics: AnalyticsService = Depends(get_analytics_service),
) -> SummaryAnalytics:
    return analytics.summary()
