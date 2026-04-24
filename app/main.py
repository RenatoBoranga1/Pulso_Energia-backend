from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import setup_logging
from app.core.middleware import register_middlewares
from app.db.session import dispose_engine


logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        uploads_dir = settings.resolved_uploads_dir
        uploads_dir.mkdir(parents=True, exist_ok=True)
        logger.info(
            "Application startup completed",
            extra={
                "event": "application_startup",
                "environment": settings.environment,
                "uploads_dir": str(uploads_dir),
            },
        )
        yield
        dispose_engine()
        logger.info(
            "Application shutdown completed",
            extra={"event": "application_shutdown"},
        )

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
        lifespan=lifespan,
    )

    register_middlewares(app)
    register_exception_handlers(app)
    app.include_router(api_router)

    return app


app = create_app()
