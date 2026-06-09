from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.user import UserRead


class PhoneStartVerificationRequest(BaseModel):
    phone_number: str = Field(min_length=10, max_length=20)


class PhoneStartVerificationResponse(BaseModel):
    phone_number_masked: str
    expires_in_seconds: int
    resend_available_in_seconds: int
    account_status: str
    message: str


class PhoneConfirmVerificationRequest(BaseModel):
    code: str = Field(min_length=6, max_length=6)


class PhoneConfirmVerificationResponse(BaseModel):
    phone_verified: bool
    phone_verified_at: datetime | None = None
    account_status: str
    phone_number_masked: str | None = None
    message: str
    user: UserRead


class PhoneVerificationStatusResponse(BaseModel):
    phone_number_masked: str | None = None
    phone_verified: bool
    account_status: str
    has_pending_code: bool
    expires_in_seconds: int | None = None
    resend_available_in_seconds: int | None = None
    message: str | None = None
