from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.api.dependencies.database import get_db
from app.api.dependencies.rate_limit import upload_rate_limit
from app.core.config import Settings, get_settings
from app.models.user import User
from app.schemas.document import DocumentUploadResponse
from app.services.documents.upload_service import DocumentUploadService


router = APIRouter(prefix="/documents", tags=["documents"])


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a utility bill document",
)
async def upload_document(
    file: UploadFile = File(...),
    _: None = Depends(upload_rate_limit),
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(get_current_user),
) -> DocumentUploadResponse:
    service = DocumentUploadService(session=session, settings=settings)
    return await service.upload(user_id=current_user.id, file=file)
