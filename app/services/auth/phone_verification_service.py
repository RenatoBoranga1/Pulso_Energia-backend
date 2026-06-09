from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import status
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.models.phone_verification_code import PhoneVerificationCode
from app.models.user import AccountStatus, User
from app.repositories.phone_verification_repository import PhoneVerificationRepository
from app.repositories.user_repository import UserRepository
from app.schemas.phone_verification import (
    PhoneConfirmVerificationRequest,
    PhoneConfirmVerificationResponse,
    PhoneStartVerificationRequest,
    PhoneStartVerificationResponse,
    PhoneVerificationStatusResponse,
)
from app.schemas.user import UserRead
from app.services.sms.provider import SmsProvider, build_sms_provider


class PhoneVerificationService:
    def __init__(self, session: Session, settings: Settings, sms_provider: SmsProvider | None = None) -> None:
        self.session = session
        self.settings = settings
        self.sms_provider = sms_provider or build_sms_provider(settings)
        self.user_repository = UserRepository(session)
        self.phone_repository = PhoneVerificationRepository(session)

    def start_verification(
        self,
        *,
        user: User,
        payload: PhoneStartVerificationRequest,
    ) -> PhoneStartVerificationResponse:
        if user.account_status == AccountStatus.BLOCKED.value:
            raise AppError(
                "Sua conta esta bloqueada. Entre em contato com o suporte.",
                code="account_blocked",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        normalized_phone = self._normalize_phone_number(payload.phone_number)
        existing_user = self.user_repository.get_by_phone_number(normalized_phone)
        if existing_user is not None and existing_user.id != user.id:
            raise AppError(
                "Esse numero de celular ja esta vinculado a outra conta.",
                code="phone_number_already_registered",
                status_code=status.HTTP_409_CONFLICT,
            )

        latest = self.phone_repository.get_latest_for_user(user.id)
        resend_available_in_seconds = 0
        if latest is not None and latest.used_at is None:
            resend_available_in_seconds = self._seconds_until(
                latest.created_at + timedelta(seconds=self.settings.phone_verification_resend_interval_seconds)
            )
            if resend_available_in_seconds > 0 and latest.phone_number == normalized_phone:
                raise AppError(
                    "Aguarde alguns segundos antes de solicitar um novo codigo.",
                    code="phone_verification_resend_too_soon",
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    details={"retry_after_seconds": resend_available_in_seconds},
                )

        code = self._generate_code()
        expires_at = datetime.now(UTC) + timedelta(minutes=self.settings.phone_verification_code_expire_minutes)
        self.phone_repository.invalidate_pending_for_user(user.id)

        user.phone_number = normalized_phone
        user.phone_verified = False
        user.phone_verified_at = None
        user.account_status = AccountStatus.PENDING_PHONE_VERIFICATION.value

        verification = PhoneVerificationCode(
            user_id=user.id,
            phone_number=normalized_phone,
            code_hash=self._hash_code(phone_number=normalized_phone, code=code),
            expires_at=expires_at,
        )
        self.phone_repository.add(verification)
        self.sms_provider.send_verification_code(phone_number=normalized_phone, code=code)
        self.session.add(user)
        self.session.commit()
        self.session.refresh(user)

        return PhoneStartVerificationResponse(
            phone_number_masked=user.phone_number_masked or self._mask_phone(normalized_phone),
            expires_in_seconds=self.settings.phone_verification_code_expire_minutes * 60,
            resend_available_in_seconds=self.settings.phone_verification_resend_interval_seconds,
            account_status=user.account_status,
            message="Enviamos um codigo para o celular informado. Digite os 6 digitos para continuar.",
        )

    def resend_code(self, *, user: User) -> PhoneStartVerificationResponse:
        if not user.phone_number:
            raise AppError(
                "Informe um numero de celular antes de reenviar o codigo.",
                code="phone_number_required",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        return self.start_verification(
            user=user,
            payload=PhoneStartVerificationRequest(phone_number=user.phone_number),
        )

    def confirm_verification(
        self,
        *,
        user: User,
        payload: PhoneConfirmVerificationRequest,
    ) -> PhoneConfirmVerificationResponse:
        if not user.phone_number:
            raise AppError(
                "Informe um numero de celular antes de confirmar o codigo.",
                code="phone_number_required",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        verification = self.phone_repository.get_pending_for_user(user.id)
        if verification is None:
            raise AppError(
                "Nao existe um codigo ativo para esse usuario. Solicite um novo envio.",
                code="phone_verification_not_started",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        if self._coerce_utc(verification.expires_at) <= datetime.now(UTC):
            self.phone_repository.mark_used(verification)
            self.session.commit()
            raise AppError(
                "O codigo expirou. Solicite um novo codigo para continuar.",
                code="phone_verification_code_expired",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        if verification.attempts >= self.settings.phone_verification_max_attempts:
            self.phone_repository.mark_used(verification)
            self.session.commit()
            raise AppError(
                "Voce excedeu o limite de tentativas. Solicite um novo codigo.",
                code="phone_verification_attempts_exceeded",
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        if not secrets.compare_digest(
            verification.code_hash,
            self._hash_code(phone_number=verification.phone_number, code=payload.code),
        ):
            self.phone_repository.increment_attempts(verification)
            if verification.attempts >= self.settings.phone_verification_max_attempts:
                self.phone_repository.mark_used(verification)
            self.session.commit()
            raise AppError(
                "Codigo invalido. Revise os 6 digitos e tente novamente.",
                code="phone_verification_code_invalid",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        self.phone_repository.mark_used(verification)
        user.phone_verified = True
        user.phone_verified_at = datetime.now(UTC)
        user.account_status = AccountStatus.ACTIVE.value
        self.session.add(user)
        self.session.commit()
        self.session.refresh(user)

        return PhoneConfirmVerificationResponse(
            phone_verified=True,
            phone_verified_at=user.phone_verified_at,
            account_status=user.account_status,
            phone_number_masked=user.phone_number_masked,
            message="Celular confirmado com sucesso. Agora voce ja pode acessar o app.",
            user=UserRead.model_validate(user),
        )

    def status(self, *, user: User) -> PhoneVerificationStatusResponse:
        pending = self.phone_repository.get_pending_for_user(user.id)
        has_pending_code = pending is not None and self._coerce_utc(pending.expires_at) > datetime.now(UTC)
        expires_in_seconds = None
        resend_available_in_seconds = None
        if has_pending_code and pending is not None:
            expires_in_seconds = self._seconds_until(self._coerce_utc(pending.expires_at))
            resend_available_in_seconds = self._seconds_until(
                self._coerce_utc(pending.created_at)
                + timedelta(seconds=self.settings.phone_verification_resend_interval_seconds)
            )

        return PhoneVerificationStatusResponse(
            phone_number_masked=user.phone_number_masked,
            phone_verified=user.phone_verified,
            account_status=user.account_status,
            has_pending_code=has_pending_code,
            expires_in_seconds=expires_in_seconds,
            resend_available_in_seconds=resend_available_in_seconds,
            message=self._build_status_message(user=user, has_pending_code=has_pending_code),
        )

    def _build_status_message(self, *, user: User, has_pending_code: bool) -> str:
        if user.phone_verified:
            return "Seu numero ja esta confirmado."
        if not user.phone_number:
            return "Para proteger sua conta, confirme seu numero de celular."
        if has_pending_code:
            return "Digite o codigo de 6 digitos enviado por SMS."
        return "Solicite um novo codigo para concluir a verificacao."

    def _normalize_phone_number(self, phone_number: str) -> str:
        digits = "".join(ch for ch in phone_number if ch.isdigit())
        if digits.startswith("55") and len(digits) in {12, 13}:
            digits = digits[2:]
        if len(digits) not in {10, 11}:
            raise AppError(
                "Informe um numero de celular valido com DDD.",
                code="invalid_phone_number",
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        return digits

    def _generate_code(self) -> str:
        if self.settings.sms_provider == "mock":
            return self.settings.sms_mock_fixed_code
        return f"{secrets.randbelow(1_000_000):06d}"

    def _hash_code(self, *, phone_number: str, code: str) -> str:
        value = f"{phone_number}:{code}:{self.settings.jwt_secret_key}"
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    def _mask_phone(self, phone_number: str) -> str:
        digits = "".join(ch for ch in phone_number if ch.isdigit())
        ddd = digits[:2]
        suffix = digits[-4:]
        middle = "*" * max(len(digits) - 6, 4)
        return f"({ddd}) {middle}-{suffix}"

    def _seconds_until(self, expires_at: datetime) -> int:
        remaining = int((expires_at - datetime.now(UTC)).total_seconds())
        return max(0, remaining)

    def _coerce_utc(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
