from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


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
    sms_provider: Literal["mock", "twilio"] = Field(default="mock", validation_alias="SMS_PROVIDER")
    sms_mock_fixed_code: str = Field(default="123456", validation_alias="SMS_MOCK_FIXED_CODE")
    twilio_account_sid: str | None = Field(default=None, validation_alias="TWILIO_ACCOUNT_SID")
    twilio_auth_token: str | None = Field(default=None, validation_alias="TWILIO_AUTH_TOKEN")
    twilio_from_phone: str | None = Field(default=None, validation_alias="TWILIO_FROM_PHONE")
    phone_verification_code_expire_minutes: int = Field(
        default=5,
        validation_alias="PHONE_VERIFICATION_CODE_EXPIRE_MINUTES",
    )
    phone_verification_max_attempts: int = Field(
        default=5,
        validation_alias="PHONE_VERIFICATION_MAX_ATTEMPTS",
    )
    phone_verification_resend_interval_seconds: int = Field(
        default=30,
        validation_alias="PHONE_VERIFICATION_RESEND_INTERVAL_SECONDS",
    )
    terms_current_version: str = Field(default="2026-04-28", validation_alias="TERMS_CURRENT_VERSION")
    rate_limit_enabled: bool = Field(default=True, validation_alias="RATE_LIMIT_ENABLED")
    auth_rate_limit_requests: int = Field(default=20, validation_alias="AUTH_RATE_LIMIT_REQUESTS")
    auth_rate_limit_window_seconds: int = Field(default=60, validation_alias="AUTH_RATE_LIMIT_WINDOW_SECONDS")
    auth_login_rate_limit_requests: int = Field(default=20, validation_alias="AUTH_LOGIN_RATE_LIMIT_REQUESTS")
    auth_login_rate_limit_window_seconds: int = Field(default=60, validation_alias="AUTH_LOGIN_RATE_LIMIT_WINDOW_SECONDS")
    auth_register_rate_limit_requests: int = Field(default=10, validation_alias="AUTH_REGISTER_RATE_LIMIT_REQUESTS")
    auth_register_rate_limit_window_seconds: int = Field(default=60, validation_alias="AUTH_REGISTER_RATE_LIMIT_WINDOW_SECONDS")
    auth_token_rate_limit_requests: int = Field(default=60, validation_alias="AUTH_TOKEN_RATE_LIMIT_REQUESTS")
    auth_token_rate_limit_window_seconds: int = Field(default=60, validation_alias="AUTH_TOKEN_RATE_LIMIT_WINDOW_SECONDS")
    phone_rate_limit_requests: int = Field(default=20, validation_alias="PHONE_RATE_LIMIT_REQUESTS")
    phone_rate_limit_window_seconds: int = Field(default=60, validation_alias="PHONE_RATE_LIMIT_WINDOW_SECONDS")
    upload_rate_limit_requests: int = Field(default=10, validation_alias="UPLOAD_RATE_LIMIT_REQUESTS")
    upload_rate_limit_window_seconds: int = Field(default=300, validation_alias="UPLOAD_RATE_LIMIT_WINDOW_SECONDS")
    extraction_rate_limit_requests: int = Field(default=10, validation_alias="EXTRACTION_RATE_LIMIT_REQUESTS")
    extraction_rate_limit_window_seconds: int = Field(default=300, validation_alias="EXTRACTION_RATE_LIMIT_WINDOW_SECONDS")
    forecast_horizon_months: int = Field(default=8, validation_alias="FORECAST_HORIZON_MONTHS")
    prophet_min_history_points: int = Field(default=12, validation_alias="PROPHET_MIN_HISTORY_POINTS")
    forecast_interval_zscore: float = Field(default=1.96, validation_alias="FORECAST_INTERVAL_ZSCORE")
    enable_prophet: bool = Field(default=True, validation_alias="ENABLE_PROPHET")

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, value: object) -> str:
        if not isinstance(value, str):
            raise TypeError("DATABASE_URL must be a string")

        database_url = value.strip()
        if not database_url:
            raise ValueError("DATABASE_URL cannot be empty")

        if database_url.startswith("postgres://"):
            return "postgresql+psycopg://" + database_url.removeprefix("postgres://")
        if database_url.startswith("postgresql://"):
            return "postgresql+psycopg://" + database_url.removeprefix("postgresql://")
        return database_url

    @field_validator("database_url")
    @classmethod
    def reject_local_database_url_in_production(cls, value: str, info) -> str:
        environment = str(info.data.get("environment", "")).lower()
        if environment not in {"production", "prod"}:
            return value

        parsed_url = make_url(value)
        if parsed_url.drivername.startswith("sqlite"):
            raise ValueError("SQLite cannot be used as DATABASE_URL in production")

        blocked_hosts = {"localhost", "127.0.0.1", "0.0.0.0", "db"}
        if parsed_url.host in blocked_hosts:
            raise ValueError(
                "DATABASE_URL points to a local/Docker host. "
                "On Render, use the PostgreSQL Internal Database URL from the Render database service.",
            )
        return value

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
