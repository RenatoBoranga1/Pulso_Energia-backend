from __future__ import annotations

from decimal import Decimal
from pathlib import Path


def _escape_pdf_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def build_pdf_with_lines(lines: list[str]) -> bytes:
    text_commands = ["BT", "/F1 12 Tf", "72 760 Td"]
    for index, line in enumerate(lines):
        escaped = _escape_pdf_text(line)
        if index == 0:
            text_commands.append(f"({escaped}) Tj")
        else:
            text_commands.append("0 -16 Td")
            text_commands.append(f"({escaped}) Tj")
    text_commands.append("ET")
    stream = "\n".join(text_commands).encode("latin-1")

    objects = [
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>\nendobj\n",
        b"4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n",
        f"5 0 obj\n<< /Length {len(stream)} >>\nstream\n".encode("latin-1") + stream + b"\nendstream\nendobj\n",
    ]

    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objects:
        offsets.append(len(pdf))
        pdf.extend(obj)

    xref_offset = len(pdf)
    pdf.extend(b"xref\n0 6\n0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("latin-1"))
    pdf.extend(b"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n")
    pdf.extend(str(xref_offset).encode("latin-1"))
    pdf.extend(b"\n%%EOF\n")
    return bytes(pdf)


def _create_confirmed_bill(client, auth_headers) -> str:
    pdf_bytes = build_pdf_with_lines(
        [
            "Concessionaria: Enel Sao Paulo",
            "Mes de referencia: 04/2026",
            "Consumo do mes: 252 kWh",
            "Dias faturados: 29",
            "Valor total: R$ 198,45",
            "Bandeira tarifaria: Verde",
            "Unidade Consumidora: 123456789",
            "Vencimento: 15/05/2026",
            "Historico de consumo",
            "2025-12 301 33",
            "2026-01 336 29",
            "2026-02 267 28",
            "2026-03 336 32",
            "2026-04 252 29",
        ]
    )

    upload_response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("conta.pdf", pdf_bytes, "application/pdf")},
        headers=auth_headers,
    )
    assert upload_response.status_code == 201
    document_id = upload_response.json()["id"]

    extract_response = client.post(
        "/api/v1/bills/extract",
        json={"document_id": document_id},
        headers=auth_headers,
    )
    assert extract_response.status_code == 200
    extracted_bill = extract_response.json()

    preconfirm_analytics = client.get(f"/api/v1/bills/{extracted_bill['bill_id']}/analytics", headers=auth_headers)
    assert preconfirm_analytics.status_code == 409
    assert preconfirm_analytics.json()["error"]["code"] == "bill_not_confirmed"

    confirm_response = client.post(
        f"/api/v1/bills/{extracted_bill['bill_id']}/confirm",
        json={
            "data": {
                "concessionaria": extracted_bill["structured_data"]["concessionaria"],
                "mes_referencia": extracted_bill["structured_data"]["mes_referencia"],
                "consumo_kwh": extracted_bill["structured_data"]["consumo_kwh"],
                "dias_faturados": extracted_bill["structured_data"]["dias_faturados"],
                "valor_total": extracted_bill["structured_data"]["valor_total"],
                "bandeira_tarifaria": extracted_bill["structured_data"]["bandeira_tarifaria"],
                "unidade_consumidora": extracted_bill["structured_data"]["unidade_consumidora"],
                "vencimento": extracted_bill["structured_data"]["vencimento"],
                "historico_consumo": extracted_bill["structured_data"]["historico_consumo"],
            }
        },
        headers=auth_headers,
    )
    assert confirm_response.status_code == 200
    return extracted_bill["bill_id"]


def test_bill_analytics_and_forecast_endpoints(client, auth_headers) -> None:
    bill_id = _create_confirmed_bill(client, auth_headers)

    analytics_response = client.get(f"/api/v1/bills/{bill_id}/analytics", headers=auth_headers)
    assert analytics_response.status_code == 200
    analytics_payload = analytics_response.json()

    assert analytics_payload["bill_id"] == bill_id
    assert analytics_payload["reference_month"] == "2026-04"
    assert analytics_payload["history_points_used"] == 5
    assert len(analytics_payload["series"]) == 5
    assert len(analytics_payload["month_over_month_variations"]) == 4
    assert analytics_payload["highest_consumption"]["mes_referencia"] in {"2026-01", "2026-03"}
    assert analytics_payload["lowest_consumption"]["mes_referencia"] == "2026-04"
    assert analytics_payload["insights"]

    forecast_response = client.get(f"/api/v1/bills/{bill_id}/forecast", headers=auth_headers)
    assert forecast_response.status_code == 200
    forecast_payload = forecast_response.json()

    assert forecast_payload["bill_id"] == bill_id
    assert forecast_payload["reference_month"] == "2026-04"
    assert forecast_payload["model_used"] == "moving_average_linear_trend"
    assert forecast_payload["history_points_used"] == 5
    assert forecast_payload["horizon_months"] == 8
    assert len(forecast_payload["generated_forecasts"]) == 8
    assert "Previsao persistida com o metodo" in forecast_payload["explanation"]
    assert Decimal(forecast_payload["reference_tariff_brl_per_kwh"]) == Decimal("0.7875")
    assert forecast_payload["generated_forecasts"][0]["mes_referencia"] == "2026-05"
    assert Decimal(forecast_payload["generated_forecasts"][0]["predicted_kwh"]) > Decimal("0")
    assert Decimal(forecast_payload["generated_forecasts"][0]["estimated_value_brl"]) > Decimal("0")
    assert forecast_payload["insights"]


def test_bill_analytics_handles_missing_billed_days_without_internal_error(client, auth_headers) -> None:
    pdf_bytes = build_pdf_with_lines(
        [
            "Concessionaria: Enel Sao Paulo",
            "Mes de referencia: 04/2026",
            "Consumo do mes: 252 kWh",
            "Valor total: R$ 198,45",
            "Historico de consumo",
            "2025-12 301 33",
            "2026-01 336 29",
            "2026-02 267",
            "2026-03 336 32",
            "2026-04 252",
        ]
    )

    upload_response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("conta_missing_days.pdf", pdf_bytes, "application/pdf")},
        headers=auth_headers,
    )
    assert upload_response.status_code == 201
    document_id = upload_response.json()["id"]

    extract_response = client.post(
        "/api/v1/bills/extract",
        json={"document_id": document_id},
        headers=auth_headers,
    )
    assert extract_response.status_code == 200
    extracted_bill = extract_response.json()

    confirm_response = client.post(
        f"/api/v1/bills/{extracted_bill['bill_id']}/confirm",
        json={
            "data": {
                "concessionaria": "Enel Sao Paulo",
                "mes_referencia": "2026-04",
                "consumo_kwh": 252,
                "dias_faturados": None,
                "valor_total": "198.45",
                "bandeira_tarifaria": "Verde",
                "unidade_consumidora": "123456789",
                "vencimento": "2026-05-15",
                "historico_consumo": [
                    {"mes_referencia": "2025-12", "consumo_kwh": "301", "dias_faturados": 33},
                    {"mes_referencia": "2026-01", "consumo_kwh": "336", "dias_faturados": 29},
                    {"mes_referencia": "2026-02", "consumo_kwh": "267", "dias_faturados": None},
                    {"mes_referencia": "2026-03", "consumo_kwh": "336", "dias_faturados": 32},
                    {"mes_referencia": "2026-04", "consumo_kwh": "252", "dias_faturados": None},
                ],
            }
        },
        headers=auth_headers,
    )
    assert confirm_response.status_code == 200

    analytics_response = client.get(f"/api/v1/bills/{extracted_bill['bill_id']}/analytics", headers=auth_headers)
    assert analytics_response.status_code == 200
    analytics_payload = analytics_response.json()
    assert len(analytics_payload["series"]) == 5
    assert analytics_payload["series"][-1]["dias_faturados"] is None


def test_delete_bill_removes_history_entry_and_file(client, sample_user, auth_headers) -> None:
    bill_id = _create_confirmed_bill(client, auth_headers)

    bill_response = client.get(f"/api/v1/bills/{bill_id}", headers=auth_headers)
    assert bill_response.status_code == 200
    stored_path = Path(bill_response.json()["document"]["file_path"])
    assert stored_path.exists()

    delete_response = client.delete(f"/api/v1/bills/{bill_id}", headers=auth_headers)
    assert delete_response.status_code == 204

    history_response = client.get(f"/api/v1/users/{sample_user.id}/history", headers=auth_headers)
    assert history_response.status_code == 200
    assert history_response.json()["bills"] == []

    get_deleted_response = client.get(f"/api/v1/bills/{bill_id}", headers=auth_headers)
    assert get_deleted_response.status_code == 404
    assert not stored_path.exists()
