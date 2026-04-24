from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.uploaded_document import UploadedDocument


class DocumentRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, document: UploadedDocument) -> UploadedDocument:
        self.session.add(document)
        self.session.flush()
        self.session.refresh(document)
        return document

    def get_by_id(self, document_id: UUID) -> UploadedDocument | None:
        statement = select(UploadedDocument).where(UploadedDocument.id == document_id)
        return self.session.execute(statement).scalar_one_or_none()

    def get_by_id_for_user(self, document_id: UUID, user_id: UUID) -> UploadedDocument | None:
        statement = select(UploadedDocument).where(
            UploadedDocument.id == document_id,
            UploadedDocument.user_id == user_id,
        )
        return self.session.execute(statement).scalar_one_or_none()

    def save(self, document: UploadedDocument) -> UploadedDocument:
        self.session.add(document)
        self.session.flush()
        self.session.refresh(document)
        return document

    def delete(self, document: UploadedDocument) -> None:
        self.session.delete(document)
        self.session.flush()
