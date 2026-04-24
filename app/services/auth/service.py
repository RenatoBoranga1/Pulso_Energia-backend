from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import status
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth import AuthLoginRequest, AuthLogoutRequest, AuthRefreshRequest, AuthRegisterRequest, TokenResponse
from app.schemas.user import UserRead
from app.services.auth.password_service import PasswordService
from app.services.auth.token_service import IssuedRefreshToken, TokenService


class AuthenticationService:
    def __init__(self, session: Session, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.user_repository = UserRepository(session)
        self.refresh_token_repository = RefreshTokenRepository(session)
        self.password_service = PasswordService()
        self.token_service = TokenService(settings)

    def register(self, payload: AuthRegisterRequest) -> TokenResponse:
        normalized_email = payload.email.strip().lower()
        existing_user = self.user_repository.get_by_email(normalized_email)
        if existing_user is not None:
            raise AppError(
                "Email is already registered.",
                code="email_already_registered",
                status_code=status.HTTP_409_CONFLICT,
            )

        user = User(
            name=payload.name.strip(),
            email=normalized_email,
            password_hash=self.password_service.hash_password(payload.password),
        )
        self.user_repository.add(user)
        self.session.commit()
        self.session.refresh(user)
        return self._build_token_response(user)

    def login(self, payload: AuthLoginRequest) -> TokenResponse:
        user = self.user_repository.get_by_email(payload.email)
        if user is None or not self.password_service.verify_password(payload.password, user.password_hash):
            raise AppError(
                "Invalid email or password.",
                code="invalid_credentials",
                status_code=status.HTTP_401_UNAUTHORIZED,
            )
        return self._build_token_response(user)

    def refresh(self, payload: AuthRefreshRequest) -> TokenResponse:
        token_payload = self.token_service.decode_refresh_token(payload.refresh_token, allow_expired=True)
        refresh_token = self._load_refresh_token(token_payload)
        user = self.user_repository.get_by_id(UUID(token_payload.sub))
        if user is None:
            raise AppError(
                "Authenticated user was not found.",
                code="invalid_token",
                status_code=status.HTTP_401_UNAUTHORIZED,
            )

        if refresh_token.revoked_at is not None:
            if refresh_token.replaced_by_jti is not None:
                self.refresh_token_repository.revoke_family(
                    user_id=user.id,
                    family_id=UUID(token_payload.family_id),
                )
                self.session.commit()
                raise AppError(
                    "Refresh token reuse detected; the session family was revoked.",
                    code="refresh_token_reused",
                    status_code=status.HTTP_401_UNAUTHORIZED,
                )
            raise AppError(
                "Refresh token has been revoked.",
                code="refresh_token_revoked",
                status_code=status.HTTP_401_UNAUTHORIZED,
            )

        if self._coerce_utc(refresh_token.expires_at) <= datetime.now(UTC):
            self.refresh_token_repository.revoke(refresh_token)
            self.session.commit()
            raise AppError(
                "Refresh token has expired.",
                code="token_expired",
                status_code=status.HTTP_401_UNAUTHORIZED,
            )

        issued_refresh_token = self.token_service.create_refresh_token(user, family_id=UUID(token_payload.family_id))
        self.refresh_token_repository.revoke(refresh_token, replaced_by_jti=issued_refresh_token.token_jti)
        self.refresh_token_repository.add(self._build_refresh_token_model(user=user, issued_token=issued_refresh_token))
        self.session.commit()
        self.session.refresh(user)
        return self._build_token_response(user, refresh_token=issued_refresh_token)

    def logout(self, payload: AuthLogoutRequest) -> None:
        token_payload = self.token_service.decode_refresh_token(payload.refresh_token, allow_expired=True)
        refresh_token = self._load_refresh_token(token_payload)
        if refresh_token.revoked_at is None:
            self.refresh_token_repository.revoke(refresh_token)
            self.session.commit()

    def get_current_user(self, token: str) -> User:
        payload = self.token_service.decode_access_token(token)
        user = self.user_repository.get_by_id(UUID(payload.sub))
        if user is None:
            raise AppError(
                "Authenticated user was not found.",
                code="invalid_token",
                status_code=status.HTTP_401_UNAUTHORIZED,
            )
        return user

    def _build_token_response(self, user: User, *, refresh_token: IssuedRefreshToken | None = None) -> TokenResponse:
        issued_refresh_token = refresh_token or self.token_service.create_refresh_token(user)
        if refresh_token is None:
            self.refresh_token_repository.add(self._build_refresh_token_model(user=user, issued_token=issued_refresh_token))
            self.session.commit()
            self.session.refresh(user)

        return TokenResponse(
            access_token=self.token_service.create_access_token(user),
            refresh_token=issued_refresh_token.token,
            expires_in_seconds=self.settings.access_token_expire_minutes * 60,
            refresh_expires_in_seconds=self.settings.refresh_token_expire_days * 24 * 60 * 60,
            user=UserRead.model_validate(user),
        )

    def _build_refresh_token_model(self, *, user: User, issued_token: IssuedRefreshToken) -> RefreshToken:
        return RefreshToken(
            user_id=user.id,
            token_jti=issued_token.token_jti,
            family_id=issued_token.family_id,
            expires_at=issued_token.expires_at,
        )

    def _load_refresh_token(self, token_payload) -> RefreshToken:
        refresh_token = self.refresh_token_repository.get_by_jti(UUID(token_payload.jti))
        if refresh_token is None or str(refresh_token.user_id) != token_payload.sub or str(refresh_token.family_id) != token_payload.family_id:
            raise AppError(
                "Refresh token is invalid.",
                code="invalid_token",
                status_code=status.HTTP_401_UNAUTHORIZED,
            )
        return refresh_token

    def _coerce_utc(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
