from __future__ import annotations

from app.db.session import get_session_factory
from app.models.user import User
from app.services.auth.password_service import PasswordService


def test_register_login_and_me_flow(client) -> None:
    register_response = client.post(
        "/api/v1/auth/register",
        json={
            "name": "Auth User",
            "email": "auth.user@example.com",
            "password": "StrongPass123!",
        },
    )

    assert register_response.status_code == 201
    register_payload = register_response.json()
    assert register_payload["token_type"] == "bearer"
    assert register_payload["user"]["email"] == "auth.user@example.com"
    assert register_payload["refresh_token"]
    assert register_payload["refresh_expires_in_seconds"] > register_payload["expires_in_seconds"]

    me_response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {register_payload['access_token']}"},
    )
    assert me_response.status_code == 200
    assert me_response.json()["email"] == "auth.user@example.com"

    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "auth.user@example.com",
            "password": "StrongPass123!",
        },
    )
    assert login_response.status_code == 200
    login_payload = login_response.json()
    assert login_payload["user"]["email"] == "auth.user@example.com"
    assert login_payload["refresh_token"]


def test_refresh_rotates_token_pair_and_rejects_reuse(client) -> None:
    register_response = client.post(
        "/api/v1/auth/register",
        json={
            "name": "Rotate User",
            "email": "rotate.user@example.com",
            "password": "RotatePass123!",
        },
    )
    original_refresh_token = register_response.json()["refresh_token"]

    refresh_response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": original_refresh_token},
    )

    assert refresh_response.status_code == 200
    refresh_payload = refresh_response.json()
    assert refresh_payload["access_token"]
    assert refresh_payload["refresh_token"]
    assert refresh_payload["refresh_token"] != original_refresh_token

    reused_response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": original_refresh_token},
    )

    assert reused_response.status_code == 401
    assert reused_response.json()["error"]["code"] == "refresh_token_reused"


def test_logout_revokes_refresh_token(client) -> None:
    register_response = client.post(
        "/api/v1/auth/register",
        json={
            "name": "Logout User",
            "email": "logout.user@example.com",
            "password": "LogoutPass123!",
        },
    )
    refresh_token = register_response.json()["refresh_token"]

    logout_response = client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": refresh_token},
    )

    assert logout_response.status_code == 204

    refresh_response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )

    assert refresh_response.status_code == 401
    assert refresh_response.json()["error"]["code"] == "refresh_token_revoked"


def test_protected_route_requires_authentication(client) -> None:
    response = client.get("/api/v1/auth/me")

    assert response.status_code == 401
    payload = response.json()
    assert payload["error"]["code"] == "not_authenticated"


def test_user_history_forbidden_for_other_user(client, sample_user, auth_headers) -> None:
    session = get_session_factory()()
    try:
        other_user = User(
            name="Other User",
            email="other.user@example.com",
            password_hash=PasswordService().hash_password("OtherPass123!"),
        )
        session.add(other_user)
        session.commit()
        session.refresh(other_user)
    finally:
        session.close()

    response = client.get(f"/api/v1/users/{other_user.id}/history", headers=auth_headers)

    assert response.status_code == 403
    payload = response.json()
    assert payload["error"]["code"] == "forbidden"


def test_login_rejects_invalid_credentials(client, sample_user) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": sample_user.email,
            "password": "WrongPassword123!",
        },
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"


def test_login_rate_limit_returns_429(client, sample_user, sample_user_password) -> None:
    last_response = None

    for _ in range(6):
        last_response = client.post(
            "/api/v1/auth/login",
            json={
                "email": sample_user.email,
                "password": sample_user_password,
            },
        )

    assert last_response is not None
    assert last_response.status_code == 429
    assert last_response.json()["error"]["code"] == "rate_limit_exceeded"
    assert "Retry-After" in last_response.headers
