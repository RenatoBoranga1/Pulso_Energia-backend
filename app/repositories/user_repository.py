from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.user import User


class UserRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, user_id: UUID) -> User | None:
        statement = select(User).where(User.id == user_id)
        return self.session.execute(statement).scalar_one_or_none()

    def get_by_email(self, email: str) -> User | None:
        normalized_email = email.strip().lower()
        statement = select(User).where(func.lower(User.email) == normalized_email)
        return self.session.execute(statement).scalar_one_or_none()

    def get_by_phone_number(self, phone_number: str) -> User | None:
        statement = select(User).where(User.phone_number == phone_number)
        return self.session.execute(statement).scalar_one_or_none()

    def add(self, user: User) -> User:
        self.session.add(user)
        self.session.flush()
        self.session.refresh(user)
        return user
