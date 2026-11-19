"""Coordinator analytics. Aggregates only: no names, emails or per-student data."""

from collections import Counter
from statistics import median

from sqlalchemy.orm import Session

from app.models.drive import Drive
from app.repositories.drive_repo import DriveRepository
from app.schemas.analytics import RoleCount, SkillCount, SkillsAnalytics, SummaryAnalytics


def ctc_point(drive: Drive) -> float | None:
    """Midpoint of the CTC range, or whichever end is known."""
    lo, hi = drive.ctc_lpa_min, drive.ctc_lpa_max
    if lo is not None and hi is not None:
        return (lo + hi) / 2
    return lo if lo is not None else hi


class AnalyticsService:
    def __init__(self, db: Session) -> None:
        self.drives = DriveRepository(db)

    def skills(self, limit: int = 20) -> SkillsAnalytics:
        drives = self.drives.unique_drives()
        counts: Counter[str] = Counter()
        for d in drives:
            counts.update(set(d.required_skills or []))
        top = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:limit]
        return SkillsAnalytics(
            total_drives=len(drives), top_skills=[SkillCount(skill=s, count=c) for s, c in top]
        )

    def summary(self) -> SummaryAnalytics:
        drives = self.drives.unique_drives()
        roles = Counter(d.role_category or "Unknown" for d in drives)
        ctcs = [p for d in drives if (p := ctc_point(d)) is not None]
        companies = {d.company.strip().lower() for d in drives if d.company}
        return SummaryAnalytics(
            total_drives=len(drives),
            total_companies=len(companies),
            drives_by_role_category=[
                RoleCount(role_category=r, count=c)
                for r, c in sorted(roles.items(), key=lambda kv: (-kv[1], kv[0]))
            ],
            median_ctc_lpa=round(median(ctcs), 2) if ctcs else None,
            drives_with_ctc=len(ctcs),
            drives_with_bond=sum(1 for d in drives if (d.bond_years or 0) > 0),
        )
