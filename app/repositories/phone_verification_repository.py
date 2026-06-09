from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.phone_verification_code import PhoneVerificationCode


class PhoneVerificationRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_latest_for_user(self, user_id: UUID) -> PhoneVerificationCode | None:
        statement = (
            select(PhoneVerificationCode)
            .where(PhoneVerificationCode.user_id == user_id)
            .order_by(PhoneVerificationCode.created_at.desc())
        )
        return self.session.execute(statement).scalars().first()

    def get_pending_for_user(self, user_id: UUID) -> PhoneVerificationCode | None:
        statement = (
            select(PhoneVerificationCode)
            .where(
                PhoneVerificationCode.user_id == user_id,
                PhoneVerificationCode.used_at.is_(None),
            )
            .order_by(PhoneVerificationCode.created_at.desc())
        )
        return self.session.execute(statement).scalars().first()

    def add(self, code: PhoneVerificationCode) -> PhoneVerificationCode:
        self.session.add(code)
        self.session.flush()
        self.session.refresh(code)
        return code

    def mark_used(self, code: PhoneVerificationCode) -> None:
        code.used_at = datetime.now(UTC)
        self.session.add(code)
        self.session.flush()

    def increment_attempts(self, code: PhoneVerificationCode) -> None:
        code.attempts += 1
        self.session.add(code)
        self.session.flush()

    def invalidate_pending_for_user(self, user_id: UUID) -> None:
        statement = (
            select(PhoneVerificationCode)
            .where(
                PhoneVerificationCode.user_id == user_id,
                PhoneVerificationCode.used_at.is_(None),
            )
        )
        for pending in self.session.execute(statement).scalars().all():
            pending.used_at = datetime.now(UTC)
            self.session.add(pending)
        self.session.flush()
