from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.errors import error_body

router = APIRouter(tags=["health"])


@router.get("/health", response_model=None)
def health(db: Session = Depends(get_db)) -> dict[str, str] | JSONResponse:
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return JSONResponse(
            error_body("DB_UNAVAILABLE", "Database is not reachable"), status_code=503
        )
    return {"status": "ok"}
