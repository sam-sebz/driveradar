"""Application settings. Everything comes from environment variables (12-factor)."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

LLMProvider = Literal["mock", "openai", "anthropic", "gemini"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    app_env: str = "development"
    log_level: str = "INFO"

    database_url: str = "postgresql+psycopg://driveradar:driveradar@localhost:5432/driveradar"

    # No default on purpose: the app refuses to start without a signing secret.
    jwt_secret: SecretStr
    access_token_minutes: int = 15
    refresh_token_days: int = 7

    cors_origins: str = "http://localhost:5173"
    login_rate_limit_per_minute: int = 5

    upload_dir: str = "./uploads"
    max_upload_mb: int = 10

    llm_provider: LLMProvider = "mock"
    llm_model: str | None = None
    llm_timeout_seconds: float = 30.0
    openai_api_key: SecretStr | None = None
    anthropic_api_key: SecretStr | None = None
    gemini_api_key: SecretStr | None = None

    # percentage = CGPA x factor when a notice states a percentage cut-off for UG.
    cgpa_to_percent_factor: float = Field(default=10.0, gt=0)

    seed_demo_data: bool = False

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # values come from the environment
