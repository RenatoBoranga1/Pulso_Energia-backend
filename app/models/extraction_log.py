from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import ExtractionLogLevel, ExtractionLogStage
from app.db.base_class import Base, CreatedAtMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.uploaded_document import UploadedDocument
    from app.models.utility_bill import UtilityBill


class ExtractionLog(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "extraction_logs"

    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("uploaded_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    bill_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("utility_bills.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    stage: Mapped[ExtractionLogStage] = mapped_column(
        Enum(ExtractionLogStage, native_enum=False, validate_strings=True, length=64),
        nullable=False,
    )
    level: Mapped[ExtractionLogLevel] = mapped_column(
        Enum(ExtractionLogLevel, native_enum=False, validate_strings=True, length=16),
        nullable=False,
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    source_component: Mapped[str | None] = mapped_column(String(120), nullable=True)

    document: Mapped["UploadedDocument"] = relationship(back_populates="extraction_logs")
    bill: Mapped["UtilityBill | None"] = relationship(back_populates="extraction_logs")
