from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import jwt
from jwt import ExpiredSignatureError, InvalidTokenError

from app.core.config import Settings
from app.core.errors import AppError
from app.models.user import User
from app.schemas.auth import TokenPayload


@dataclass(frozen=True)
class IssuedRefreshToken:
    token: str
    token_jti: UUID
    family_id: UUID
    expires_at: datetime


class TokenService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def create_access_token(self, user: User) -> str:
        now = datetime.now(UTC)
        expires_at = now + timedelta(minutes=self.settings.access_token_expire_minutes)
        payload = {
            "sub": str(user.id),
            "email": user.email,
            "token_type": "access",
            "jti": str(uuid4()),
            "iat": int(now.timestamp()),
            "exp": int(expires_at.timestamp()),
        }
        return self._encode(payload)

    def create_refresh_token(self, user: User, *, family_id: UUID | None = None) -> IssuedRefreshToken:
        now = datetime.now(UTC)
        expires_at = now + timedelta(days=self.settings.refresh_token_expire_days)
        token_jti = uuid4()
        resolved_family_id = family_id or uuid4()
        payload = {
            "sub": str(user.id),
            "email": user.email,
            "token_type": "refresh",
            "jti": str(token_jti),
            "family_id": str(resolved_family_id),
            "iat": int(now.timestamp()),
            "exp": int(expires_at.timestamp()),
        }
        return IssuedRefreshToken(
            token=self._encode(payload),
            token_jti=token_jti,
            family_id=resolved_family_id,
            expires_at=expires_at,
        )

    def decode_access_token(self, token: str) -> TokenPayload:
        token_payload = self._decode(token=token, expired_message="Access token has expired.", invalid_message="Access token is invalid.")
        if token_payload.token_type != "access":
            raise AppError("Unsupported token type.", code="invalid_token", status_code=401)
        return token_payload

    def decode_refresh_token(self, token: str, *, allow_expired: bool = False) -> TokenPayload:
        token_payload = self._decode(
            token=token,
            expired_message="Refresh token has expired.",
            invalid_message="Refresh token is invalid.",
            verify_exp=not allow_expired,
        )
        if token_payload.token_type != "refresh" or token_payload.jti is None or token_payload.family_id is None:
            raise AppError("Unsupported token type.", code="invalid_token", status_code=401)
        return token_payload

    def _decode(self, *, token: str, expired_message: str, invalid_message: str, verify_exp: bool = True) -> TokenPayload:
        try:
            payload = jwt.decode(
                token,
                self.settings.jwt_secret_key,
                algorithms=[self.settings.jwt_algorithm],
                options={"verify_exp": verify_exp},
            )
        except ExpiredSignatureError as exc:
            raise AppError(expired_message, code="token_expired", status_code=401) from exc
        except InvalidTokenError as exc:
            raise AppError(invalid_message, code="invalid_token", status_code=401) from exc

        return TokenPayload.model_validate(payload)

    def _encode(self, payload: dict[str, object]) -> str:
        return jwt.encode(payload, self.settings.jwt_secret_key, algorithm=self.settings.jwt_algorithm)
