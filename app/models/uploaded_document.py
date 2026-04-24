from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import DocumentFileType
from app.db.base_class import Base, CreatedAtMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.extraction_log import ExtractionLog
    from app.models.user import User
    from app.models.utility_bill import UtilityBill


class UploadedDocument(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "uploaded_documents"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(nullable=False)
    file_type: Mapped[DocumentFileType] = mapped_column(
        Enum(DocumentFileType, native_enum=False, validate_strings=True, length=16),
        nullable=False,
    )
    file_path: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    user: Mapped["User"] = relationship(back_populates="documents")
    utility_bill: Mapped["UtilityBill | None"] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        uselist=False,
    )
    extraction_logs: Mapped[list["ExtractionLog"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
    )
