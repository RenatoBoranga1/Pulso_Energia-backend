from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import EmailStr

from app.schemas.common import ORMModel


class UserRead(ORMModel):
    id: UUID
    name: str
    email: EmailStr
    phone_number: str | None = None
    phone_number_masked: str | None = None
    phone_verified: bool = False
    phone_verified_at: datetime | None = None
    two_factor_enabled: bool = True
    account_status: str
    accepted_terms_at: datetime | None = None
    accepted_terms_version: str | None = None
    created_at: datetime
