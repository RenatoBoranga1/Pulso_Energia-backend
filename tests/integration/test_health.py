from __future__ import annotations


def test_health_endpoint_returns_healthy_status(client) -> None:
    response = client.get("/health")

    assert response.status_code == 200

    payload = response.json()
    assert payload["status"] == "healthy"
    assert payload["dependencies"]["database"]["status"] == "healthy"
    assert payload["environment"] == "test"
    assert "X-Request-ID" in response.headers

