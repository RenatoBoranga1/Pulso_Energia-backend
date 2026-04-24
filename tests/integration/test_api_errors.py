from __future__ import annotations

from uuid import uuid4


def test_upload_rejects_unsupported_file_type_with_structured_error(client, auth_headers) -> None:
    response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("conta.txt", b"nao suportado", "text/plain")},
        headers=auth_headers,
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["error"]["code"] == "unsupported_file_type"
    assert "Supported extensions" in payload["error"]["message"]
    assert payload["error"]["request_id"]


def test_extract_returns_404_for_unknown_document(client, auth_headers) -> None:
    response = client.post(
        "/api/v1/bills/extract",
        json={"document_id": str(uuid4())},
        headers=auth_headers,
    )

    assert response.status_code == 404
    payload = response.json()
    assert payload["error"]["code"] == "document_not_found"
    assert payload["error"]["message"] == "Document not found."


def test_analytics_returns_404_for_unknown_bill(client, auth_headers) -> None:
    response = client.get(f"/api/v1/bills/{uuid4()}/analytics", headers=auth_headers)

    assert response.status_code == 404
    payload = response.json()
    assert payload["error"]["code"] == "bill_not_found"
    assert payload["error"]["message"] == "Bill not found."


def test_request_validation_error_returns_standardized_payload(client, auth_headers) -> None:
    response = client.post(
        "/api/v1/bills/extract",
        json={"document_id": "not-a-uuid"},
        headers=auth_headers,
    )

    assert response.status_code == 422
    payload = response.json()
    assert payload["error"]["code"] == "request_validation_error"
    assert payload["error"]["message"] == "Request validation failed."
    assert payload["error"]["details"]
    assert payload["error"]["request_id"]
