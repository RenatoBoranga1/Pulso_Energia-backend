from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_active_user
from app.api.dependencies.database import get_db
from app.api.dependencies.rate_limit import extraction_rate_limit
from app.core.config import Settings, get_settings
from app.models.user import User
from app.schemas.analytics import BillAnalyticsResponse, BillForecastResponse
from app.schemas.extraction import BillReviewResponse, ConfirmBillRequest, ExtractBillRequest, UserBillHistoryResponse
from app.services.analytics.service import BillAnalyticsService
from app.services.bills.management_service import BillManagementService
from app.services.extraction.bill_extraction_service import BillExtractionService
from app.services.review.bill_review_service import BillReviewService


router = APIRouter(prefix="/bills", tags=["bills"])
users_router = APIRouter(prefix="/users", tags=["users"])


@router.post("/extract", response_model=BillReviewResponse, summary="Extract structured data from a bill document")
def extract_bill(
    payload: ExtractBillRequest,
    _: None = Depends(extraction_rate_limit),
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(get_active_user),
) -> BillReviewResponse:
    service = BillExtractionService(session=session, settings=settings)
    return service.extract(document_id=payload.document_id, current_user_id=current_user.id)


@router.get("/{bill_id}", response_model=BillReviewResponse, summary="Get a bill extraction review payload")
def get_bill(
    bill_id: UUID,
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(get_active_user),
) -> BillReviewResponse:
    service = BillExtractionService(session=session, settings=settings)
    return service.get_bill_review(bill_id=bill_id, current_user_id=current_user.id)


@router.get("/{bill_id}/analytics", response_model=BillAnalyticsResponse, summary="Get consumption analytics for a bill")
def get_bill_analytics(
    bill_id: UUID,
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(get_active_user),
) -> BillAnalyticsResponse:
    service = BillAnalyticsService(session=session, settings=settings)
    return service.get_analytics(bill_id=bill_id, current_user_id=current_user.id)


@router.get("/{bill_id}/forecast", response_model=BillForecastResponse, summary="Get the next 8 months forecast for a bill")
def get_bill_forecast(
    bill_id: UUID,
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(get_active_user),
) -> BillForecastResponse:
    service = BillAnalyticsService(session=session, settings=settings)
    return service.get_forecast(bill_id=bill_id, current_user_id=current_user.id)


@router.post("/{bill_id}/confirm", response_model=BillReviewResponse, summary="Confirm reviewed bill data")
def confirm_bill(
    bill_id: UUID,
    payload: ConfirmBillRequest,
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(get_active_user),
) -> BillReviewResponse:
    service = BillReviewService(session=session, settings=settings)
    return service.confirm(bill_id=bill_id, payload=payload, current_user_id=current_user.id)


@router.delete("/{bill_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a bill and its uploaded document")
def delete_bill(
    bill_id: UUID,
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(get_active_user),
) -> Response:
    service = BillManagementService(session=session, settings=settings)
    service.delete_bill(bill_id=bill_id, current_user_id=current_user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@users_router.get("/{user_id}/history", response_model=UserBillHistoryResponse, summary="List a user's bill history")
def get_user_bill_history(
    user_id: UUID,
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(get_active_user),
) -> UserBillHistoryResponse:
    service = BillReviewService(session=session, settings=settings)
    return service.list_user_history(user_id=user_id, current_user_id=current_user.id)
