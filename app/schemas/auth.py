from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, EmailStr, Field, StringConstraints

from app.schemas.user import UserRead


class AuthRegisterRequest(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class AuthLoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class AuthRefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=32)


class AuthLogoutRequest(BaseModel):
    refresh_token: str = Field(min_length=32)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in_seconds: int
    refresh_expires_in_seconds: int
    user: UserRead


class TokenPayload(BaseModel):
    sub: Annotated[str, StringConstraints(min_length=1)]
    email: EmailStr
    token_type: str
    exp: int
    iat: int
    jti: str | None = None
    family_id: str | None = None
