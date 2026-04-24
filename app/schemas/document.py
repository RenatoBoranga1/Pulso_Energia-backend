from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.core.enums import DocumentFileType
from app.schemas.common import ORMModel


class UploadedDocumentRead(ORMModel):
    id: UUID
    user_id: UUID
    filename: str
    mime_type: str
    file_size_bytes: int
    file_type: DocumentFileType
    file_path: str
    extracted_text: str | None = None
    created_at: datetime


class DocumentUploadResponse(UploadedDocumentRead):
    pass

