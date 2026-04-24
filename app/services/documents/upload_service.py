from __future__ import annotations

import mimetypes
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.enums import DocumentFileType, ExtractionLogLevel, ExtractionLogStage
from app.core.errors import AppError
from app.models.uploaded_document import UploadedDocument
from app.repositories.document_repository import DocumentRepository
from app.repositories.extraction_log_repository import ExtractionLogRepository
from app.repositories.user_repository import UserRepository
from app.schemas.document import DocumentUploadResponse
from app.services.documents.storage import LocalDocumentStorageService


SUPPORTED_EXTENSIONS = {
    ".pdf": DocumentFileType.PDF,
    ".jpg": DocumentFileType.JPG,
    ".jpeg": DocumentFileType.JPEG,
    ".png": DocumentFileType.PNG,
}


class DocumentUploadService:
    def __init__(self, session: Session, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.user_repository = UserRepository(session)
        self.document_repository = DocumentRepository(session)
        self.log_repository = ExtractionLogRepository(session)
        self.storage_service = LocalDocumentStorageService(settings)

    async def upload(self, *, user_id, file: UploadFile) -> DocumentUploadResponse:
        user = self.user_repository.get_by_id(user_id)
        if user is None:
            raise AppError(
                "User not found.",
                code="user_not_found",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        if not file.filename:
            raise AppError("Filename is required.", code="invalid_filename", status_code=status.HTTP_400_BAD_REQUEST)

        extension = Path(file.filename).suffix.lower()
        if extension not in SUPPORTED_EXTENSIONS:
            raise AppError(
                "Unsupported file type. Supported extensions: PDF, JPG, JPEG, PNG.",
                code="unsupported_file_type",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        content = await file.read()
        if not content:
            raise AppError("Uploaded file is empty.", code="empty_file", status_code=status.HTTP_400_BAD_REQUEST)

        if len(content) > self.settings.max_upload_size_bytes:
            raise AppError(
                f"File exceeds the configured upload limit of {self.settings.max_upload_size_mb} MB.",
                code="file_too_large",
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            )

        document_id = uuid4()
        storage_path = self.storage_service.build_storage_path(
            user_id=user.id,
            document_id=document_id,
            extension=extension.lstrip("."),
        )
        mime_type = file.content_type or mimetypes.guess_type(file.filename)[0] or "application/octet-stream"

        try:
            self.storage_service.save(path=storage_path, content=content)
            document = UploadedDocument(
                id=document_id,
                user_id=user.id,
                filename=file.filename,
                mime_type=mime_type,
                file_size_bytes=len(content),
                file_type=SUPPORTED_EXTENSIONS[extension],
                file_path=str(storage_path),
            )
            self.document_repository.add(document)
            self.log_repository.add(
                document_id=document.id,
                bill_id=None,
                stage=ExtractionLogStage.UPLOAD,
                level=ExtractionLogLevel.INFO,
                message="Document uploaded successfully.",
                source_component="document_upload_service",
            )
            self.session.commit()
        except Exception:
            self.session.rollback()
            if storage_path.exists():
                storage_path.unlink(missing_ok=True)
            raise

        return DocumentUploadResponse.model_validate(document)

