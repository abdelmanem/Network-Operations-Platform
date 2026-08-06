from fastapi import APIRouter

router = APIRouter(tags=["version"])


@router.get("/version", summary="Application version", response_model=dict[str, str])
def version() -> dict[str, str]:
    return {"version": "0.1.0"}
