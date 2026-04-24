from __future__ import annotations

import argparse
import sys
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import select

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import get_settings
from app.core.enums import BillExtractionStatus, DocumentFileType, ExtractionLogLevel, ExtractionLogStage
from app.db.base import Base  # noqa: F401
from app.db.session import get_session_factory
from app.models.consumption_history import ConsumptionHistory
from app.models.extraction_confidence import ExtractionConfidence
from app.models.extraction_log import ExtractionLog
from app.models.uploaded_document import UploadedDocument
from app.models.user import User
from app.models.utility_bill import UtilityBill
from app.repositories.user_repository import UserRepository
from app.services.analytics.service import BillAnalyticsService
from app.services.auth.password_service import PasswordService
from app.services.documents.storage import LocalDocumentStorageService


PRIMARY_SAMPLE_SERIES: list[tuple[str, Decimal, int]] = [
    ("2025-04", Decimal("280.000"), 28),
    ("2025-05", Decimal("230.000"), 31),
    ("2025-06", Decimal("210.000"), 29),
    ("2025-07", Decimal("270.000"), 32),
    ("2025-08", Decimal("240.000"), 31),
    ("2025-09", Decimal("260.000"), 33),
    ("2025-10", Decimal("334.000"), 29),
    ("2025-11", Decimal("218.000"), 29),
    ("2025-12", Decimal("301.000"), 33),
    ("2026-01", Decimal("336.000"), 29),
    ("2026-02", Decimal("267.000"), 28),
    ("2026-03", Decimal("336.000"), 32),
    ("2026-04", Decimal("252.000"), 29),
]

SECONDARY_SAMPLE_SERIES: list[tuple[str, Decimal, int]] = [
    ("2025-11", Decimal("198.000"), 30),
    ("2025-12", Decimal("205.000"), 31),
    ("2026-01", Decimal("221.000"), 29),
    ("2026-02", Decimal("215.000"), 28),
    ("2026-03", Decimal("246.000"), 31),
    ("2026-04", Decimal("238.000"), 30),
]

PENDING_REVIEW_CONFIDENCE: dict[str, Decimal] = {
    "concessionaria": Decimal("0.9700"),
    "mes_referencia": Decimal("0.9400"),
    "consumo_kwh": Decimal("0.9100"),
    "dias_faturados": Decimal("0.8200"),
    "valor_total": Decimal("0.5800"),
    "bandeira_tarifaria": Decimal("0.7300"),
    "unidade_consumidora": Decimal("0.8900"),
    "vencimento": Decimal("0.6100"),
    "historico_consumo": Decimal("0.7600"),
}

PENDING_REVIEW_HISTORY: list[tuple[str, Decimal, int]] = [
    ("2026-01", Decimal("336.000"), 29),
    ("2026-02", Decimal("267.000"), 28),
    ("2026-03", Decimal("336.000"), 32),
    ("2026-04", Decimal("252.000"), 29),
    ("2026-05", Decimal("289.000"), 30),
]


def _build_placeholder_pdf(text: str) -> bytes:
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = f"BT\n/F1 12 Tf\n72 760 Td\n({escaped}) Tj\nET".encode("latin-1")
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


def _ensure_user(*, session, email: str, name: str, password: str) -> User:
    repository = UserRepository(session)
    user = repository.get_by_email(email)
    if user is not None:
        return user

    password_hash = PasswordService().hash_password(password)
    user = User(name=name, email=email, password_hash=password_hash)
    repository.add(user)
    session.commit()
    session.refresh(user)
    return user


def _build_confirmed_bill_text(*, provider: str, mes_referencia: str, consumo_kwh: Decimal, dias_faturados: int) -> str:
    return (
        f"Concessionaria: {provider}\n"
        f"Mes de referencia: {mes_referencia}\n"
        f"Consumo: {consumo_kwh} kWh\n"
        f"Dias faturados: {dias_faturados}\n"
    )


def _build_pending_review_text() -> str:
    return (
        "CONCESSIONARIA: Seed Energy Provider\n"
        "MES REFERENCIA: 2026-05\n"
        "CONSUMO FATURADO: 289 kWh\n"
        "DIAS FATURADOS: 30\n"
        "VALOR TOTAL: R$ 214,98\n"
        "BANDEIRA TARIFARIA: Amarela\n"
        "UNIDADE CONSUMIDORA: SEED-UNIT-001\n"
        "VENCIMENTO: 15/06/2026\n"
        "HISTORICO 2026-01 336 29 | 2026-02 267 28 | 2026-03 336 32 | 2026-04 252 29 | 2026-05 289 30\n"
        "OBSERVACAO: OCR encontrou ruido na area de valor total.\n"
    )


def _ensure_document(
    *,
    session,
    storage_service: LocalDocumentStorageService,
    user: User,
    filename: str,
    text: str,
) -> UploadedDocument:
    statement = select(UploadedDocument).where(
        UploadedDocument.user_id == user.id,
        UploadedDocument.filename == filename,
    )
    document = session.execute(statement).scalar_one_or_none()
    content = _build_placeholder_pdf(text)

    if document is None:
        document_id = uuid4()
        storage_path = storage_service.build_storage_path(
            user_id=user.id,
            document_id=document_id,
            extension="pdf",
        )
        document = UploadedDocument(
            id=document_id,
            user_id=user.id,
            filename=filename,
            mime_type="application/pdf",
            file_size_bytes=len(content),
            file_type=DocumentFileType.PDF,
            file_path=str(storage_path),
        )
    else:
        storage_path = storage_service.resolve(document.file_path)

    storage_service.save(path=storage_path, content=content)
    document.extracted_text = text
    document.file_size_bytes = len(content)
    session.add(document)
    session.flush()
    return document


def _replace_consumption_history(
    *,
    session,
    bill: UtilityBill,
    history_rows: list[tuple[str, Decimal, int]],
) -> None:
    bill.consumption_history.clear()
    session.flush()
    bill.consumption_history.extend(
        [
            ConsumptionHistory(
                mes_referencia=mes_referencia,
                consumo_kwh=consumo_kwh,
                dias_faturados=dias_faturados,
            )
            for mes_referencia, consumo_kwh, dias_faturados in history_rows
        ]
    )


def _replace_confidence_scores(
    *,
    session,
    bill: UtilityBill,
    confidence_map: dict[str, Decimal],
) -> None:
    bill.confidence_scores.clear()
    session.flush()
    bill.confidence_scores.extend(
        [
            ExtractionConfidence(
                field_name=field_name,
                confidence_score=score,
            )
            for field_name, score in confidence_map.items()
        ]
    )


def _replace_document_logs(
    *,
    session,
    document: UploadedDocument,
    bill: UtilityBill | None,
    entries: list[tuple[ExtractionLogStage, ExtractionLogLevel, str, str]],
) -> None:
    document.extraction_logs.clear()
    session.flush()
    document.extraction_logs.extend(
        [
            ExtractionLog(
                bill=bill,
                stage=stage,
                level=level,
                message=message,
                source_component=source_component,
            )
            for stage, level, message, source_component in entries
        ]
    )


def _ensure_confirmed_bill(
    *,
    session,
    user: User,
    document: UploadedDocument,
    provider: str,
    unit_code: str,
    mes_referencia: str,
    consumo_kwh: Decimal,
    dias_faturados: int,
) -> UtilityBill:
    statement = select(UtilityBill).where(
        UtilityBill.user_id == user.id,
        UtilityBill.mes_referencia == mes_referencia,
    )
    bill = session.execute(statement).scalar_one_or_none()
    if bill is None:
        bill = UtilityBill(user_id=user.id, document_id=document.id)

    bill.document_id = document.id
    bill.concessionaria = provider
    bill.mes_referencia = mes_referencia
    bill.consumo_kwh = consumo_kwh
    bill.dias_faturados = dias_faturados
    bill.valor_total = Decimal("0.00")
    bill.bandeira_tarifaria = "Verde"
    bill.unidade_consumidora = unit_code
    bill.extraction_status = BillExtractionStatus.CONFIRMED
    bill.review_required = False
    bill.forecasts.clear()
    bill.insights.clear()
    session.add(bill)
    session.flush()
    _replace_consumption_history(session=session, bill=bill, history_rows=[(mes_referencia, consumo_kwh, dias_faturados)])
    _replace_confidence_scores(
        session=session,
        bill=bill,
        confidence_map={
            "concessionaria": Decimal("1.0000"),
            "mes_referencia": Decimal("1.0000"),
            "consumo_kwh": Decimal("1.0000"),
            "dias_faturados": Decimal("1.0000"),
            "valor_total": Decimal("1.0000"),
            "bandeira_tarifaria": Decimal("1.0000"),
            "unidade_consumidora": Decimal("1.0000"),
            "vencimento": Decimal("1.0000"),
            "historico_consumo": Decimal("1.0000"),
        },
    )
    _replace_document_logs(
        session=session,
        document=document,
        bill=bill,
        entries=[
            (
                ExtractionLogStage.UPLOAD,
                ExtractionLogLevel.INFO,
                "Seed document registered successfully.",
                "seed_dev_data",
            ),
            (
                ExtractionLogStage.REVIEW,
                ExtractionLogLevel.INFO,
                "Seed bill stored as confirmed reference data.",
                "seed_dev_data",
            ),
        ],
    )
    return bill


def _ensure_pending_review_bill(
    *,
    session,
    user: User,
    document: UploadedDocument,
    provider: str,
    unit_code: str,
) -> UtilityBill:
    statement = select(UtilityBill).where(
        UtilityBill.user_id == user.id,
        UtilityBill.document_id == document.id,
    )
    bill = session.execute(statement).scalar_one_or_none()
    if bill is None:
        bill = UtilityBill(user_id=user.id, document_id=document.id)

    bill.document_id = document.id
    bill.concessionaria = provider
    bill.mes_referencia = "2026-05"
    bill.consumo_kwh = Decimal("289.000")
    bill.dias_faturados = 30
    bill.valor_total = Decimal("214.98")
    bill.bandeira_tarifaria = "Amarela"
    bill.unidade_consumidora = unit_code
    bill.extraction_status = BillExtractionStatus.PENDING_REVIEW
    bill.review_required = True
    bill.forecasts.clear()
    bill.insights.clear()
    session.add(bill)
    session.flush()

    _replace_consumption_history(session=session, bill=bill, history_rows=PENDING_REVIEW_HISTORY)
    _replace_confidence_scores(session=session, bill=bill, confidence_map=PENDING_REVIEW_CONFIDENCE)
    _replace_document_logs(
        session=session,
        document=document,
        bill=bill,
        entries=[
            (
                ExtractionLogStage.UPLOAD,
                ExtractionLogLevel.INFO,
                "Seed pending-review document registered successfully.",
                "seed_dev_data",
            ),
            (
                ExtractionLogStage.TEXT_EXTRACTION,
                ExtractionLogLevel.INFO,
                "Seed text extracted from placeholder PDF.",
                "seed_dev_data",
            ),
            (
                ExtractionLogStage.TEXT_EXTRACTION,
                ExtractionLogLevel.WARNING,
                "OCR-like noise detected around the total amount block.",
                "seed_dev_data",
            ),
            (
                ExtractionLogStage.SEMANTIC_PARSING,
                ExtractionLogLevel.INFO,
                "Structured payload generated for manual review.",
                "seed_dev_data",
            ),
            (
                ExtractionLogStage.VALIDATION,
                ExtractionLogLevel.WARNING,
                "Low-confidence fields require manual confirmation: valor_total, vencimento.",
                "seed_dev_data",
            ),
        ],
    )
    return bill


def _seed_confirmed_portfolio(
    *,
    session,
    storage_service: LocalDocumentStorageService,
    user: User,
    provider: str,
    unit_code: str,
    series: list[tuple[str, Decimal, int]],
) -> list[UUID]:
    seeded_bill_ids: list[UUID] = []
    for mes_referencia, consumo_kwh, dias_faturados in series:
        document = _ensure_document(
            session=session,
            storage_service=storage_service,
            user=user,
            filename=f"seed-{mes_referencia}.pdf",
            text=_build_confirmed_bill_text(
                provider=provider,
                mes_referencia=mes_referencia,
                consumo_kwh=consumo_kwh,
                dias_faturados=dias_faturados,
            ),
        )
        bill = _ensure_confirmed_bill(
            session=session,
            user=user,
            document=document,
            provider=provider,
            unit_code=unit_code,
            mes_referencia=mes_referencia,
            consumo_kwh=consumo_kwh,
            dias_faturados=dias_faturados,
        )
        seeded_bill_ids.append(bill.id)
    return seeded_bill_ids


def _seed_pending_review_scenario(
    *,
    session,
    storage_service: LocalDocumentStorageService,
    user: User,
    provider: str,
    unit_code: str,
) -> UUID:
    document = _ensure_document(
        session=session,
        storage_service=storage_service,
        user=user,
        filename="seed-pending-review-2026-05.pdf",
        text=_build_pending_review_text(),
    )
    bill = _ensure_pending_review_bill(
        session=session,
        user=user,
        document=document,
        provider=provider,
        unit_code=unit_code,
    )
    return bill.id


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed realistic development users and utility-bill scenarios.")
    parser.add_argument("--name", default="Seed User")
    parser.add_argument("--email", default="seed.user@example.com")
    parser.add_argument("--password", default="ChangeMe123!")
    parser.add_argument("--skip-secondary-user", action="store_true")
    args = parser.parse_args()

    settings = get_settings()
    storage_service = LocalDocumentStorageService(settings)
    session_factory = get_session_factory()

    primary_confirmed_ids: list[UUID] = []
    secondary_confirmed_ids: list[UUID] = []
    primary_user_id: UUID | None = None
    secondary_user_id: UUID | None = None
    primary_pending_bill_id: UUID | None = None

    session = session_factory()
    try:
        primary_user = _ensure_user(session=session, email=args.email, name=args.name, password=args.password)
        primary_user_id = primary_user.id
        primary_confirmed_ids = _seed_confirmed_portfolio(
            session=session,
            storage_service=storage_service,
            user=primary_user,
            provider="Seed Energy Provider",
            unit_code="SEED-UNIT-001",
            series=PRIMARY_SAMPLE_SERIES,
        )
        primary_pending_bill_id = _seed_pending_review_scenario(
            session=session,
            storage_service=storage_service,
            user=primary_user,
            provider="Seed Energy Provider",
            unit_code="SEED-UNIT-001",
        )

        secondary_user = None
        if not args.skip_secondary_user:
            secondary_user = _ensure_user(
                session=session,
                email="ops.user@example.com",
                name="Ops Seed User",
                password="OpsPass123!",
            )
            secondary_user_id = secondary_user.id
            secondary_confirmed_ids = _seed_confirmed_portfolio(
                session=session,
                storage_service=storage_service,
                user=secondary_user,
                provider="Seed Energy Provider Sul",
                unit_code="SEED-UNIT-OPS-001",
                series=SECONDARY_SAMPLE_SERIES,
            )

        session.commit()
    finally:
        session.close()

    session = session_factory()
    try:
        analytics_service = BillAnalyticsService(session=session, settings=settings)
        for bill_id in primary_confirmed_ids + secondary_confirmed_ids:
            current_user_id = primary_user_id if bill_id in primary_confirmed_ids else secondary_user_id
            if current_user_id is None:
                continue
            analytics_service.refresh_artifacts_for_bill(bill_id=bill_id, current_user_id=current_user_id)
    finally:
        session.close()

    print("Seed completed successfully.")
    print(f"Primary user email: {args.email}")
    print(f"Primary user password: {args.password}")
    print(f"Primary confirmed bills: {len(primary_confirmed_ids)}")
    print(f"Primary pending-review bill: {primary_pending_bill_id}")
    if not args.skip_secondary_user:
        print("Secondary user email: ops.user@example.com")
        print("Secondary user password: OpsPass123!")
        print(f"Secondary confirmed bills: {len(secondary_confirmed_ids)}")


if __name__ == "__main__":
    main()
