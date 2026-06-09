from __future__ import annotations

import base64
import json
import logging
from abc import ABC, abstractmethod
from urllib import parse, request

from app.core.config import Settings
from app.core.errors import AppError


logger = logging.getLogger(__name__)


class SmsProvider(ABC):
    @abstractmethod
    def send_verification_code(self, *, phone_number: str, code: str) -> None:
        raise NotImplementedError


class MockSmsProvider(SmsProvider):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def send_verification_code(self, *, phone_number: str, code: str) -> None:
        if self.settings.environment.lower() != "production":
            logger.info(
                "Mock SMS verification code generated",
                extra={
                    "event": "mock_sms_verification_sent",
                    "phone_number_masked": _mask_phone_number(phone_number),
                    "code": code,
                },
            )


class TwilioSmsProvider(SmsProvider):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        if not settings.twilio_account_sid or not settings.twilio_auth_token or not settings.twilio_from_phone:
            raise AppError(
                "SMS provider is not configured correctly.",
                code="sms_provider_not_configured",
                status_code=500,
            )

    def send_verification_code(self, *, phone_number: str, code: str) -> None:
        endpoint = (
            f"https://api.twilio.com/2010-04-01/Accounts/"
            f"{self.settings.twilio_account_sid}/Messages.json"
        )
        payload = parse.urlencode(
            {
                "From": self.settings.twilio_from_phone,
                "To": _format_e164(phone_number),
                "Body": f"Seu codigo Pulso Energia e {code}. Ele expira em 5 minutos.",
            }
        ).encode("utf-8")
        auth_token = base64.b64encode(
            f"{self.settings.twilio_account_sid}:{self.settings.twilio_auth_token}".encode("utf-8")
        ).decode("ascii")
        http_request = request.Request(
            endpoint,
            data=payload,
            method="POST",
            headers={
                "Authorization": f"Basic {auth_token}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        try:
            with request.urlopen(http_request, timeout=15) as response:
                if response.status >= 400:
                    raise AppError(
                        "Nao foi possivel enviar o codigo por SMS.",
                        code="sms_delivery_failed",
                        status_code=502,
                    )
        except AppError:
            raise
        except Exception as exc:  # pragma: no cover - depends on external provider
            logger.error(
                "SMS delivery failed",
                extra={
                    "event": "sms_delivery_failed",
                    "phone_number_masked": _mask_phone_number(phone_number),
                    "exception": exc.__class__.__name__,
                },
            )
            raise AppError(
                "Nao foi possivel enviar o codigo por SMS.",
                code="sms_delivery_failed",
                status_code=502,
            ) from exc


def build_sms_provider(settings: Settings) -> SmsProvider:
    if settings.sms_provider == "twilio":
        return TwilioSmsProvider(settings)
    return MockSmsProvider(settings)


def _format_e164(phone_number: str) -> str:
    digits = "".join(ch for ch in phone_number if ch.isdigit())
    if digits.startswith("55"):
        return f"+{digits}"
    return f"+55{digits}"


def _mask_phone_number(phone_number: str) -> str:
    digits = "".join(ch for ch in phone_number if ch.isdigit())
    if len(digits) < 4:
        return "***"
    ddd = digits[:2]
    suffix = digits[-4:]
    middle = "*" * max(len(digits) - 6, 4)
    return f"({ddd}) {middle}-{suffix}"
