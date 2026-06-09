from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, CreatedAtMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.phone_verification_code import PhoneVerificationCode
    from app.models.refresh_token import RefreshToken
    from app.models.uploaded_document import UploadedDocument
    from app.models.utility_bill import UtilityBill


class AccountStatus(str, Enum):
    PENDING_PHONE_VERIFICATION = "pending_phone_verification"
    ACTIVE = "active"
    BLOCKED = "blocked"


class User(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "users"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    phone_number: Mapped[str | None] = mapped_column(String(20), nullable=True, unique=True, index=True)
    phone_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    phone_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    two_factor_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    account_status: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default=AccountStatus.PENDING_PHONE_VERIFICATION.value,
        server_default=AccountStatus.PENDING_PHONE_VERIFICATION.value,
        index=True,
    )
    accepted_terms_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    accepted_terms_version: Mapped[str | None] = mapped_column(String(32), nullable=True)

    documents: Mapped[list["UploadedDocument"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    utility_bills: Mapped[list["UtilityBill"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    phone_verification_codes: Mapped[list["PhoneVerificationCode"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )

    @property
    def phone_number_masked(self) -> str | None:
        if not self.phone_number:
            return None
        digits = "".join(ch for ch in self.phone_number if ch.isdigit())
        if len(digits) < 4:
            return None
        ddd = digits[:2]
        suffix = digits[-4:]
        middle = "*" * max(len(digits) - 6, 4)
        return f"({ddd}) {middle}-{suffix}"
