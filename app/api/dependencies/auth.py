from __future__ import annotations

from fastapi import Depends, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.api.dependencies.database import get_db
from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.models.user import AccountStatus, User
from app.services.auth.service import AuthenticationService


http_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(http_bearer),
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User:
    if credentials is None:
        raise AppError(
            "Authentication credentials were not provided.",
            code="not_authenticated",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    service = AuthenticationService(session=session, settings=settings)
    return service.get_current_user(credentials.credentials)


def get_active_user(current_user: User = Depends(get_current_user)) -> User:
    if current_user.account_status == AccountStatus.BLOCKED.value:
        raise AppError(
            "Sua conta esta bloqueada. Entre em contato com o suporte.",
            code="account_blocked",
            status_code=status.HTTP_403_FORBIDDEN,
        )
    if not current_user.phone_verified or current_user.account_status != AccountStatus.ACTIVE.value:
        raise AppError(
            "Confirme seu celular para continuar.",
            code="phone_verification_required",
            status_code=status.HTTP_403_FORBIDDEN,
        )
    return current_user
