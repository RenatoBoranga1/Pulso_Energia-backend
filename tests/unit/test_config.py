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


def test_settings_normalizes_render_postgres_url(monkeypatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("DATABASE_URL", "postgres://energy_user:secret@render-postgres.internal:5432/energy_bill_ai")

    from app.core.config import get_settings
    from app.db.session import dispose_engine

    dispose_engine()
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.database_url == (
        "postgresql+psycopg://energy_user:secret@render-postgres.internal:5432/energy_bill_ai"
    )

    dispose_engine()
    get_settings.cache_clear()


def test_settings_rejects_docker_database_host_in_production(monkeypatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://energy_user:secret@db:5432/energy_bill_ai")

    from app.core.config import get_settings
    from app.db.session import dispose_engine

    dispose_engine()
    get_settings.cache_clear()

    try:
        get_settings()
    except ValueError as exc:
        assert "PostgreSQL Internal Database URL" in str(exc)
    else:
        raise AssertionError("Expected production DATABASE_URL with host db to fail")

    dispose_engine()
    get_settings.cache_clear()
