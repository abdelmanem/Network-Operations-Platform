from fastapi import APIRouter

router = APIRouter(prefix="/discovery", tags=["discovery"])


@router.get("", summary="Discovery operations", response_model=dict[str, str])
def discovery_root() -> dict[str, str]:
    return {"status": "available"}
