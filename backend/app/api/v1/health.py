from typing import Annotated

from fastapi import APIRouter, Depends

from backend.app.config.settings import Settings, get_settings

router = APIRouter(tags=["health"])


@router.get(
    "/health", summary="Application health check", response_model=dict[str, str]
)
def health_check(
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, str]:
    return {"status": "ok", "version": settings.app_version}
