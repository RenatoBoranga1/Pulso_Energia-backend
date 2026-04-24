from __future__ import annotations

from decimal import Decimal


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


def test_upload_extract_and_confirm_bill_flow(client, sample_user, auth_headers) -> None:
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
    uploaded_document = upload_response.json()
    assert uploaded_document["filename"] == "conta.pdf"
    assert uploaded_document["mime_type"] == "application/pdf"
    assert uploaded_document["file_type"] == "pdf"

    extract_response = client.post(
        "/api/v1/bills/extract",
        json={"document_id": uploaded_document["id"]},
        headers=auth_headers,
    )

    assert extract_response.status_code == 200
    extracted_bill = extract_response.json()
    assert extracted_bill["extraction_status"] == "PENDING_REVIEW"
    assert extracted_bill["review_required"] is True
    assert extracted_bill["structured_data"]["mes_referencia"] == "2026-04"
    assert Decimal(extracted_bill["structured_data"]["consumo_kwh"]) == Decimal("252")
    assert Decimal(extracted_bill["structured_data"]["valor_total"]) == Decimal("198.45")
    assert len(extracted_bill["structured_data"]["historico_consumo"]) == 5
    assert extracted_bill["logs"]

    bill_id = extracted_bill["bill_id"]
    confirmation_payload = {
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
    }

    confirm_response = client.post(
        f"/api/v1/bills/{bill_id}/confirm",
        json=confirmation_payload,
        headers=auth_headers,
    )

    assert confirm_response.status_code == 200
    confirmed_bill = confirm_response.json()
    assert confirmed_bill["extraction_status"] == "CONFIRMED"
    assert confirmed_bill["review_required"] is False
    assert confirmed_bill["fields_for_review"] == []

    history_response = client.get(f"/api/v1/users/{sample_user.id}/history", headers=auth_headers)
    assert history_response.status_code == 200
    history_payload = history_response.json()
    assert history_payload["user_id"] == str(sample_user.id)
    assert len(history_payload["bills"]) == 1
    assert history_payload["bills"][0]["extraction_status"] == "CONFIRMED"


def test_upload_extract_handles_consumption_line_with_reference_month_before_kwh_amount(client, auth_headers) -> None:
    pdf_bytes = build_pdf_with_lines(
        [
            "Concessionaria: CPFL Paulista",
            "Mes de referencia: 04/2026",
            "Consumo Uso Sistema [KWh]-TUSD ABR/26 kWh 252,0000 0,44266000 0,57083334 143,85",
            "Consumo - TE ABR/26 kWh 252,0000 0,24605000 0,31730159 79,96",
            "Valor total: R$ 228,15",
            "Bandeira tarifaria: Verde",
            "Vencimento: 18/05/2026",
            "ABR 26 llllllllllllllllllllllllllllllllllllllllllllllllllllllll 252 29",
            "MAR 26 lllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllll 336 32",
            "F",
            "JA",
            "E",
            "N",
            "V",
            "2",
            "2",
            "6",
            "6 l",
            "lllllllllllllll",
            "2",
            "3",
            "6",
            "3",
            "7",
            "6",
            "2",
            "2",
            "8",
            "9",
            "DEZ 25 lllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllll 301 33",
            "NOV 25 lllllllllllllllllllllllllllllllllllllllllllllllll 218 29",
            "OUT 25 lllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllll 334 29",
            "SET 25 llllllllllllllllllllllllllllllllllllllllllllllllllllllllll 260 33",
            "AGO 25 llllllllllllllllllllllllllllllllllllllllllllllllllllll 240 31",
            "J",
            "J",
            "U",
            "U",
            "L",
            "N",
            "2",
            "2",
            "5",
            "5",
            "lllllllllllll 2",
            "2",
            "7",
            "1",
            "0",
            "0",
            "3",
            "2",
            "2",
            "9",
            "MAI 25 lllllllllllllllllllllllllllllllllllllllllllllllllll 230 31",
            "ABR 25 lllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllll 280 28",
        ]
    )

    upload_response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("conta_realista.pdf", pdf_bytes, "application/pdf")},
        headers=auth_headers,
    )
    assert upload_response.status_code == 201

    extract_response = client.post(
        "/api/v1/bills/extract",
        json={"document_id": upload_response.json()["id"]},
        headers=auth_headers,
    )

    assert extract_response.status_code == 200
    extracted_bill = extract_response.json()
    assert Decimal(extracted_bill["structured_data"]["consumo_kwh"]) == Decimal("252")
    assert Decimal(extracted_bill["structured_data"]["valor_total"]) == Decimal("228.15")
    assert [item["mes_referencia"] for item in extracted_bill["structured_data"]["historico_consumo"]] == [
        "2025-04",
        "2025-05",
        "2025-06",
        "2025-07",
        "2025-08",
        "2025-09",
        "2025-10",
        "2025-11",
        "2025-12",
        "2026-01",
        "2026-02",
        "2026-03",
        "2026-04",
    ]
    assert [item["dias_faturados"] for item in extracted_bill["structured_data"]["historico_consumo"][-4:]] == [29, 28, 32, 29]
    assert Decimal(extracted_bill["structured_data"]["historico_consumo"][-1]["consumo_kwh"]) == Decimal("252")
