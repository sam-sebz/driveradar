from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import analytics, auth, drives, health, profile
from app.core.config import Settings, get_settings
from app.core.errors import register_error_handlers
from app.core.logging import RequestIdMiddleware, configure_logging
from app.core.rate_limit import RateLimiter
from app.db.session import Database
from app.services.extractor_factory import build_extractor
from app.services.storage import LocalFileStore


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title="DriveRadar API",
        version="0.1.0",
        description="Upload a campus placement notice, see eligibility and missing skills.",
    )
    app.state.settings = settings
    app.state.db = Database(settings.database_url)
    app.state.extractor = build_extractor(settings)
    app.state.storage = LocalFileStore(settings.upload_dir)
    app.state.login_limiter = RateLimiter(settings.login_rate_limit_per_minute, 60.0)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )
    app.add_middleware(RequestIdMiddleware)
    register_error_handlers(app)

    for module in (health, auth, profile, drives, analytics):
        app.include_router(module.router)
    return app
