from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.db.session import get_session_factory
from app.models.phone_verification_code import PhoneVerificationCode
from app.models.user import AccountStatus


def _register_pending_user(client, *, email: str = "phone.user@example.com") -> dict:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "name": "Phone User",
            "email": email,
            "password": "PhonePass123!",
            "accepted_terms": True,
        },
    )
    assert response.status_code == 201
    return response.json()


def test_start_phone_verification_masks_phone_and_requires_confirmation(client) -> None:
    register_payload = _register_pending_user(client)
    response = client.post(
        "/api/v1/auth/phone/start-verification",
        json={"phone_number": "(14) 99999-4321"},
        headers={"Authorization": f"Bearer {register_payload['access_token']}"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["phone_number_masked"].endswith("-4321")
    assert payload["account_status"] == "pending_phone_verification"
    assert payload["expires_in_seconds"] == 300


def test_confirm_phone_verification_with_mock_code_activates_account(client) -> None:
    register_payload = _register_pending_user(client, email="activate.user@example.com")
    client.post(
        "/api/v1/auth/phone/start-verification",
        json={"phone_number": "14999994321"},
        headers={"Authorization": f"Bearer {register_payload['access_token']}"},
    )

    confirm_response = client.post(
        "/api/v1/auth/phone/confirm-verification",
        json={"code": "123456"},
        headers={"Authorization": f"Bearer {register_payload['access_token']}"},
    )

    assert confirm_response.status_code == 200
    confirm_payload = confirm_response.json()
    assert confirm_payload["phone_verified"] is True
    assert confirm_payload["account_status"] == "active"
    assert confirm_payload["user"]["phone_verified"] is True


def test_confirm_phone_verification_rejects_invalid_code_and_limits_attempts(client) -> None:
    register_payload = _register_pending_user(client, email="invalid.code@example.com")
    client.post(
        "/api/v1/auth/phone/start-verification",
        json={"phone_number": "14999994321"},
        headers={"Authorization": f"Bearer {register_payload['access_token']}"},
    )

    last_response = None
    for _ in range(5):
        last_response = client.post(
            "/api/v1/auth/phone/confirm-verification",
            json={"code": "000000"},
            headers={"Authorization": f"Bearer {register_payload['access_token']}"},
        )

    assert last_response is not None
    assert last_response.status_code in {400, 429}

    locked_response = client.post(
        "/api/v1/auth/phone/confirm-verification",
        json={"code": "123456"},
        headers={"Authorization": f"Bearer {register_payload['access_token']}"},
    )
    assert locked_response.status_code == 404 or locked_response.status_code == 429


def test_confirm_phone_verification_rejects_expired_code(client) -> None:
    register_payload = _register_pending_user(client, email="expired.code@example.com")
    start_response = client.post(
        "/api/v1/auth/phone/start-verification",
        json={"phone_number": "14999994321"},
        headers={"Authorization": f"Bearer {register_payload['access_token']}"},
    )
    assert start_response.status_code == 200

    session = get_session_factory()()
    try:
        code = session.query(PhoneVerificationCode).first()
        code.expires_at = datetime.now(UTC) - timedelta(minutes=1)
        session.add(code)
        session.commit()
    finally:
        session.close()

    confirm_response = client.post(
        "/api/v1/auth/phone/confirm-verification",
        json={"code": "123456"},
        headers={"Authorization": f"Bearer {register_payload['access_token']}"},
    )

    assert confirm_response.status_code == 400
    assert confirm_response.json()["error"]["code"] == "phone_verification_code_expired"


def test_pending_user_cannot_access_protected_bill_routes(client) -> None:
    register_payload = _register_pending_user(client, email="pending.blocked@example.com")

    history_response = client.get(
        "/api/v1/users/00000000-0000-0000-0000-000000000001/history",
        headers={"Authorization": f"Bearer {register_payload['access_token']}"},
    )
    assert history_response.status_code == 403
    assert history_response.json()["error"]["code"] == "phone_verification_required"


def test_phone_status_masks_phone_number(client) -> None:
    register_payload = _register_pending_user(client, email="status.user@example.com")
    client.post(
        "/api/v1/auth/phone/start-verification",
        json={"phone_number": "14999994321"},
        headers={"Authorization": f"Bearer {register_payload['access_token']}"},
    )

    status_response = client.get(
        "/api/v1/auth/phone/status",
        headers={"Authorization": f"Bearer {register_payload['access_token']}"},
    )

    assert status_response.status_code == 200
    payload = status_response.json()
    assert payload["phone_number_masked"].endswith("-4321")
    assert payload["phone_verified"] is False
