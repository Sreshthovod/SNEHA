"""FastAPI application factory. Run with: `uv run uvicorn app.main:app --reload`."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.api.routes.files import UPLOAD_PATH_SUFFIX
from app.api.routes.speech import TRANSCRIBE_PATH_SUFFIX
from app.core.body_limit import BodySizeLimitMiddleware
from app.core.config import Environment, Settings, get_settings
from app.core.errors import register_error_handlers
from app.core.request_id import REQUEST_ID_HEADER, RequestIdMiddleware
from app.core.version import service_version


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    logging.basicConfig(level=logging.DEBUG if settings.debug else logging.INFO)

    app = FastAPI(
        title=settings.app_name,
        version=service_version(),
        description=(
            "Backend for SNEHA, an assistive cognitive-activity and memory-support platform. "
            "SNEHA is not a diagnostic system."
        ),
        debug=settings.debug,
        # Interactive docs are for developers; production serves only the API.
        docs_url=None if settings.environment is Environment.PRODUCTION else "/docs",
        redoc_url=None if settings.environment is Environment.PRODUCTION else "/redoc",
        openapi_url=None if settings.environment is Environment.PRODUCTION else "/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        # Bearer tokens only; the dashboard never sends cookies.
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", REQUEST_ID_HEADER],
        expose_headers=[REQUEST_ID_HEADER],
    )
    app.add_middleware(
        BodySizeLimitMiddleware,
        default_limit=settings.max_json_body_bytes,
        upload_limit=settings.max_upload_bytes,
        upload_paths=(UPLOAD_PATH_SUFFIX, TRANSCRIBE_PATH_SUFFIX),
    )
    app.add_middleware(RequestIdMiddleware)
    register_error_handlers(app)
    app.include_router(api_router)
    return app


app = create_app()
