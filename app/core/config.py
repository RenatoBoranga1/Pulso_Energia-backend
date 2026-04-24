from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = Field(default="Energy Bill AI Backend", validation_alias="APP_NAME")
    app_version: str = Field(default="0.1.0", validation_alias="APP_VERSION")
    environment: str = Field(default="development", validation_alias="ENVIRONMENT")
    debug: bool = Field(default=False, validation_alias="DEBUG")
    api_v1_prefix: str = Field(default="/api/v1", validation_alias="API_V1_PREFIX")
    database_url: str = Field(
        default="postgresql+psycopg://energy_user:energy_pass@localhost:5432/energy_bill_ai",
        validation_alias="DATABASE_URL",
    )
    uploads_dir: Path = Field(default=Path("uploads"), validation_alias="UPLOADS_DIR")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        validation_alias="LOG_LEVEL",
    )
    db_pool_size: int = Field(default=10, validation_alias="DB_POOL_SIZE")
    db_max_overflow: int = Field(default=20, validation_alias="DB_MAX_OVERFLOW")
    db_pool_timeout_seconds: int = Field(default=30, validation_alias="DB_POOL_TIMEOUT_SECONDS")
    db_pool_recycle_seconds: int = Field(default=1800, validation_alias="DB_POOL_RECYCLE_SECONDS")
    max_upload_size_mb: int = Field(default=15, validation_alias="MAX_UPLOAD_SIZE_MB")
    low_confidence_threshold: float = Field(default=0.75, validation_alias="LOW_CONFIDENCE_THRESHOLD")
    ocr_languages: str = Field(default="por+eng", validation_alias="OCR_LANGUAGES")
    tesseract_cmd: str | None = Field(default=None, validation_alias="TESSERACT_CMD")
    jwt_secret_key: str = Field(default="change-this-in-production", validation_alias="JWT_SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", validation_alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(default=60, validation_alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    refresh_token_expire_days: int = Field(default=14, validation_alias="REFRESH_TOKEN_EXPIRE_DAYS")
    rate_limit_enabled: bool = Field(default=True, validation_alias="RATE_LIMIT_ENABLED")
    auth_rate_limit_requests: int = Field(default=5, validation_alias="AUTH_RATE_LIMIT_REQUESTS")
    auth_rate_limit_window_seconds: int = Field(default=60, validation_alias="AUTH_RATE_LIMIT_WINDOW_SECONDS")
    upload_rate_limit_requests: int = Field(default=10, validation_alias="UPLOAD_RATE_LIMIT_REQUESTS")
    upload_rate_limit_window_seconds: int = Field(default=300, validation_alias="UPLOAD_RATE_LIMIT_WINDOW_SECONDS")
    extraction_rate_limit_requests: int = Field(default=10, validation_alias="EXTRACTION_RATE_LIMIT_REQUESTS")
    extraction_rate_limit_window_seconds: int = Field(default=300, validation_alias="EXTRACTION_RATE_LIMIT_WINDOW_SECONDS")
    forecast_horizon_months: int = Field(default=8, validation_alias="FORECAST_HORIZON_MONTHS")
    prophet_min_history_points: int = Field(default=12, validation_alias="PROPHET_MIN_HISTORY_POINTS")
    forecast_interval_zscore: float = Field(default=1.96, validation_alias="FORECAST_INTERVAL_ZSCORE")
    enable_prophet: bool = Field(default=True, validation_alias="ENABLE_PROPHET")

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    @property
    def resolved_uploads_dir(self) -> Path:
        return self.uploads_dir.expanduser().resolve()


@lru_cache
def get_settings() -> Settings:
    return Settings()
