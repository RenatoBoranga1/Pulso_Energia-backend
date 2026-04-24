from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.refresh_token import RefreshToken


class RefreshTokenRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, refresh_token: RefreshToken) -> RefreshToken:
        self.session.add(refresh_token)
        self.session.flush()
        self.session.refresh(refresh_token)
        return refresh_token

    def get_by_jti(self, token_jti: UUID) -> RefreshToken | None:
        statement = select(RefreshToken).where(RefreshToken.token_jti == token_jti)
        return self.session.execute(statement).scalar_one_or_none()

    def revoke(self, refresh_token: RefreshToken, *, replaced_by_jti: UUID | None = None) -> RefreshToken:
        refresh_token.revoked_at = datetime.now(UTC)
        refresh_token.replaced_by_jti = replaced_by_jti
        self.session.add(refresh_token)
        self.session.flush()
        return refresh_token

    def revoke_family(self, *, user_id: UUID, family_id: UUID) -> int:
        statement = select(RefreshToken).where(
            RefreshToken.user_id == user_id,
            RefreshToken.family_id == family_id,
            RefreshToken.revoked_at.is_(None),
        )
        active_tokens = list(self.session.execute(statement).scalars().all())
        revoked_at = datetime.now(UTC)
        for token in active_tokens:
            token.revoked_at = revoked_at
            self.session.add(token)
        self.session.flush()
        return len(active_tokens)
