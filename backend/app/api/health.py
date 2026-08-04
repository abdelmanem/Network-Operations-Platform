from typing import Annotated

from fastapi import APIRouter, Depends

from backend.app.dependencies.settings import Settings, get_settings

router = APIRouter(tags=["health"])


@router.get("/health", summary="Application health check")
def health_check(
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, str]:
    return {"status": "ok", "version": settings.app_version}
