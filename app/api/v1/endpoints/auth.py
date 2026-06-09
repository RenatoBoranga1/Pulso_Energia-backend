from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.api.dependencies.database import get_db
from app.api.dependencies.rate_limit import auth_rate_limit
from app.core.config import Settings, get_settings
from app.models.user import User
from app.schemas.auth import AuthLoginRequest, AuthLogoutRequest, AuthRefreshRequest, AuthRegisterRequest, TokenResponse
from app.schemas.phone_verification import (
    PhoneConfirmVerificationRequest,
    PhoneConfirmVerificationResponse,
    PhoneStartVerificationRequest,
    PhoneStartVerificationResponse,
    PhoneVerificationStatusResponse,
)
from app.schemas.user import UserRead
from app.services.auth.phone_verification_service import PhoneVerificationService
from app.services.auth.service import AuthenticationService


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED, summary="Register a new user")
def register(
    payload: AuthRegisterRequest,
    _: None = Depends(auth_rate_limit),
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> TokenResponse:
    service = AuthenticationService(session=session, settings=settings)
    return service.register(payload)


@router.post("/login", response_model=TokenResponse, summary="Authenticate and receive an access token")
def login(
    payload: AuthLoginRequest,
    _: None = Depends(auth_rate_limit),
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> TokenResponse:
    service = AuthenticationService(session=session, settings=settings)
    return service.login(payload)


@router.post("/refresh", response_model=TokenResponse, summary="Rotate a refresh token and issue a new token pair")
def refresh(
    payload: AuthRefreshRequest,
    _: None = Depends(auth_rate_limit),
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> TokenResponse:
    service = AuthenticationService(session=session, settings=settings)
    return service.refresh(payload)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, summary="Revoke a refresh token")
def logout(
    payload: AuthLogoutRequest,
    _: None = Depends(auth_rate_limit),
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Response:
    service = AuthenticationService(session=session, settings=settings)
    service.logout(payload)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserRead, summary="Get the authenticated user")
def me(current_user: User = Depends(get_current_user)) -> UserRead:
    return UserRead.model_validate(current_user)


@router.post(
    "/phone/start-verification",
    response_model=PhoneStartVerificationResponse,
    summary="Start phone verification for the authenticated user",
)
def start_phone_verification(
    payload: PhoneStartVerificationRequest,
    _: None = Depends(auth_rate_limit),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> PhoneStartVerificationResponse:
    service = PhoneVerificationService(session=session, settings=settings)
    return service.start_verification(user=current_user, payload=payload)


@router.post(
    "/phone/resend-code",
    response_model=PhoneStartVerificationResponse,
    summary="Resend a phone verification code",
)
def resend_phone_verification_code(
    _: None = Depends(auth_rate_limit),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> PhoneStartVerificationResponse:
    service = PhoneVerificationService(session=session, settings=settings)
    return service.resend_code(user=current_user)


@router.post(
    "/phone/confirm-verification",
    response_model=PhoneConfirmVerificationResponse,
    summary="Confirm a phone verification code",
)
def confirm_phone_verification(
    payload: PhoneConfirmVerificationRequest,
    _: None = Depends(auth_rate_limit),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> PhoneConfirmVerificationResponse:
    service = PhoneVerificationService(session=session, settings=settings)
    return service.confirm_verification(user=current_user, payload=payload)


@router.get(
    "/phone/status",
    response_model=PhoneVerificationStatusResponse,
    summary="Get phone verification status for the authenticated user",
)
def get_phone_verification_status(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> PhoneVerificationStatusResponse:
    service = PhoneVerificationService(session=session, settings=settings)
    return service.status(user=current_user)
