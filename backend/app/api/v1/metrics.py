from fastapi import APIRouter

router = APIRouter(tags=["metrics"])


@router.get("/metrics", summary="Service metrics", response_model=dict[str, object])
def metrics() -> dict[str, object]:
    return {
        "service": "network-operations-platform",
        "status": "ok",
        "jobs": {"submitted": 0, "queued": 0, "completed": 0},
    }
