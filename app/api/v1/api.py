from fastapi import APIRouter

from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.bills import router as bills_router
from app.api.v1.endpoints.bills import users_router
from app.api.v1.endpoints.documents import router as documents_router


router = APIRouter(prefix="/api/v1")
router.include_router(auth_router)
router.include_router(documents_router)
router.include_router(bills_router)
router.include_router(users_router)
