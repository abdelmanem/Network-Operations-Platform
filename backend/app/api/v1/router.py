from fastapi import APIRouter

from backend.app.api.v1.comparison import router as comparison_router
from backend.app.api.v1.compliance import router as compliance_router
from backend.app.api.v1.dashboard import router as dashboard_router
from backend.app.api.v1.devices import router as devices_router
from backend.app.api.v1.findings import router as findings_router
from backend.app.api.v1.health import router as health_router
from backend.app.api.v1.history import router as history_router
from backend.app.api.v1.inventory import router as inventory_router
from backend.app.api.v1.jobs import router as jobs_router
from backend.app.api.v1.metrics import router as metrics_router
from backend.app.api.v1.scheduler import router as scheduler_router
from backend.app.api.v1.snapshots import router as snapshots_router
from backend.app.api.v1.version import router as version_router

router = APIRouter(prefix="/api/v1")
router.include_router(health_router)
router.include_router(version_router)
router.include_router(metrics_router)
router.include_router(jobs_router)
router.include_router(scheduler_router)
router.include_router(history_router)
router.include_router(findings_router)
router.include_router(devices_router)
router.include_router(comparison_router)
router.include_router(compliance_router)
router.include_router(dashboard_router)
router.include_router(inventory_router)
router.include_router(snapshots_router)
