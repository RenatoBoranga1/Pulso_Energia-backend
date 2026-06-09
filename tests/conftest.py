from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


def _reset_settings_state() -> None:
    from app.api.dependencies.rate_limit import get_rate_limiter
    from app.core.config import get_settings
    from app.db.session import dispose_engine

    dispose_engine()
    get_rate_limiter.cache_clear()
    get_settings.cache_clear()


@pytest.fixture
def app(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///:memory:")
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("MPLCONFIGDIR", str(tmp_path / ".matplotlib"))
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key")

    _reset_settings_state()

    from app.db.base import Base
    from app.db.session import get_engine
    from app.main import create_app

    application = create_app()
    Base.metadata.create_all(bind=get_engine())
    yield application

    Base.metadata.drop_all(bind=get_engine())
    _reset_settings_state()


@pytest.fixture
def client(app) -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def sample_user_password() -> str:
    return "TestPass123!"


@pytest.fixture
def sample_user(sample_user_password: str):
    from app.db.session import get_session_factory
    from app.models.user import AccountStatus, User
    from app.services.auth.password_service import PasswordService

    session = get_session_factory()()
    try:
        user = User(
            name="Test User",
            email="test.user@example.com",
            password_hash=PasswordService().hash_password(sample_user_password),
            phone_number="14999994321",
            phone_verified=True,
            phone_verified_at=datetime.now(UTC),
            account_status=AccountStatus.ACTIVE.value,
            accepted_terms_at=datetime.now(UTC),
            accepted_terms_version="test-version",
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user
    finally:
        session.close()


@pytest.fixture
def auth_headers(sample_user) -> dict[str, str]:
    from app.core.config import get_settings
    from app.services.auth.token_service import TokenService

    token = TokenService(get_settings()).create_access_token(sample_user)
    return {"Authorization": f"Bearer {token}"}
