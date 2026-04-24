from __future__ import annotations

import logging
from uuid import UUID

from fastapi import status
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.repositories.document_repository import DocumentRepository
from app.repositories.utility_bill_repository import UtilityBillRepository
from app.services.documents.storage import LocalDocumentStorageService


logger = logging.getLogger(__name__)


class BillManagementService:
    def __init__(self, session: Session, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.bill_repository = UtilityBillRepository(session)
        self.document_repository = DocumentRepository(session)
        self.storage_service = LocalDocumentStorageService(settings)

    def delete_bill(self, *, bill_id: UUID, current_user_id: UUID) -> None:
        bill = self.bill_repository.get_by_id_for_user(bill_id, current_user_id)
        if bill is None:
            raise AppError("Bill not found.", code="bill_not_found", status_code=status.HTTP_404_NOT_FOUND)

        document = bill.document
        if document is None:
            raise AppError(
                "The bill document could not be located.",
                code="document_not_found",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        stored_path = document.file_path
        self.document_repository.delete(document)
        self.session.commit()

        try:
            self.storage_service.delete(stored_path)
        except Exception:
            logger.exception(
                "Failed to remove stored document after bill deletion",
                extra={"event": "bill_file_delete_failed", "bill_id": str(bill_id), "stored_path": stored_path},
            )
