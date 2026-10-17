from fastapi import APIRouter

from app.api.routes import (
    activities,
    analytics,
    auth,
    care,
    config,
    conversation,
    files,
    health,
    memories,
    patients,
    personalization,
    review,
    speech,
    sync,
)

API_V1_PREFIX = "/api/v1"

api_router = APIRouter(prefix=API_V1_PREFIX)
for module in (
    health,
    auth,
    config,
    patients,
    memories,
    personalization,
    activities,
    care,
    analytics,
    review,
    conversation,
    files,
    speech,
    sync,
):
    api_router.include_router(module.router)
