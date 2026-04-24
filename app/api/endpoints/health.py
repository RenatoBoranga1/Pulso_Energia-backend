from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.core.config import Settings, get_settings
from app.schemas.health import HealthResponse
from app.services.health import HealthService


router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    responses={503: {"model": HealthResponse}},
    summary="Application healthcheck",
)
def get_health(settings: Settings = Depends(get_settings)) -> JSONResponse:
    service = HealthService(settings=settings)
    status_code, payload = service.check()
    return JSONResponse(status_code=status_code, content=payload.model_dump(mode="json"))

