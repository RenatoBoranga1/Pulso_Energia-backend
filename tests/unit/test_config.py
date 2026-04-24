from __future__ import annotations

from pathlib import Path


def test_settings_read_environment_variables(monkeypatch) -> None:
    monkeypatch.setenv("APP_NAME", "Energy Tests")
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///./tests.db")
    monkeypatch.setenv("UPLOADS_DIR", "custom-uploads")
    monkeypatch.setenv("REFRESH_TOKEN_EXPIRE_DAYS", "21")
    monkeypatch.setenv("AUTH_RATE_LIMIT_REQUESTS", "7")

    from app.core.config import get_settings
    from app.db.session import dispose_engine

    dispose_engine()
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.app_name == "Energy Tests"
    assert settings.database_url == "sqlite+pysqlite:///./tests.db"
    assert settings.uploads_dir == Path("custom-uploads")
    assert settings.refresh_token_expire_days == 21
    assert settings.auth_rate_limit_requests == 7
    assert settings.is_sqlite is True

    dispose_engine()
    get_settings.cache_clear()
