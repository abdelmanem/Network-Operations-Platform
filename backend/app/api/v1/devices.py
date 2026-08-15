from __future__ import annotations

from datetime import datetime
from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.api.v1.dependencies import get_db_session
from backend.app.persistence.models import SnapshotSource
from backend.app.persistence.repositories import FindingRepository, SnapshotRepository
from backend.app.schemas.comparison import (
    ComparisonState,
    DeviceComparisonResponse,
    VarianceSummary,
)
from backend.app.schemas.devices import DeviceHistoryItem, DeviceHistoryResponse

router = APIRouter(prefix="/devices", tags=["devices"])


@router.get(
    "/{device_id}/history",
    response_model=DeviceHistoryResponse,
    summary="Get device history",
)
def get_device_history(
    device_id: str,
    db_session: Annotated[Session, Depends(get_db_session)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
) -> DeviceHistoryResponse:
    repository = SnapshotRepository(db_session)
    snapshots = repository.list_by_source(SnapshotSource.LIVE)
    items: list[dict[str, object]] = []
    for snapshot in snapshots:
        for device in getattr(snapshot, "devices", []):
            if device.device_id == device_id:
                items.append(
                    {
                        "id": device.id,
                        "device_id": device.device_id,
                        "name": device.name,
                        "model": device.model,
                        "serial_number": device.serial_number,
                        "platform": device.platform,
                        "created_at": device.created_at,
                    }
                )
    if not items:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device history not found",
        )
    start = (page - 1) * page_size
    end = start + page_size
    return DeviceHistoryResponse(
        device_id=device_id,
        items=[
            DeviceHistoryItem(
                id=UUID(str(item["id"])),
                device_id=str(item["device_id"]),
                name=str(item["name"]),
                model=str(item["model"]) if item["model"] is not None else None,
                serial_number=(
                    str(item["serial_number"])
                    if item["serial_number"] is not None
                    else None
                ),
                platform=(
                    str(item["platform"]) if item["platform"] is not None else None
                ),
                created_at=cast(datetime, item["created_at"]),
            )
            for item in items[start:end]
        ],
    )


@router.get(
    "/{device_id}/compare",
    response_model=DeviceComparisonResponse,
    summary="Compare device expected vs observed",
)
def compare_device(
    db_session: Annotated[Session, Depends(get_db_session)],
    device_id: str,
    run_id: UUID | None = Query(  # noqa: B008
        None, description="Specific comparison run; latest if omitted"
    ),
) -> DeviceComparisonResponse:
    """
    Compare expected vs observed state for a single device.

    This endpoint returns the full device record from both NetBox (expected)
    and live discovery (observed), along with all field-level variances.
    """

    snapshot_repo = SnapshotRepository(db_session)
    finding_repo = FindingRepository(db_session)

    # Get the comparison result to find which snapshots to compare
    if run_id:
        comparison = finding_repo.get_comparison_result(run_id)
    else:
        comparison = finding_repo.get_latest_comparison()

    if comparison is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No comparison found. Run discovery first.",
        )

    # Get expected and observed snapshots
    expected_snapshot = snapshot_repo.get(comparison.expected_snapshot_id)
    observed_snapshot = snapshot_repo.get(comparison.observed_snapshot_id)

    # Get the specific device records from each snapshot
    expected_device = None
    if expected_snapshot:
        devices = snapshot_repo.get_snapshot_devices(
            expected_snapshot.id, device_id=device_id
        )
        if devices:
            expected_device = devices[0]

    observed_device = None
    if observed_snapshot:
        devices = snapshot_repo.get_snapshot_devices(
            observed_snapshot.id, device_id=device_id
        )
        if devices:
            observed_device = devices[0]

    if expected_device is None and observed_device is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device {device_id} not found in any snapshot.",
        )

    # Get all findings for this device to show variances
    findings = finding_repo.list_by_device(device_id)

    # Build variance summary from findings
    variances = []
    for finding in findings:
        if isinstance(finding.expected_state, dict) and isinstance(
            finding.observed_state, dict
        ):
            variance = VarianceSummary(
                field_name=finding.expected_state.get("field_name", "unknown"),
                expected_value=finding.expected_state.get("value"),
                observed_value=finding.observed_state.get("value"),
                difference_type=finding.expected_state.get(
                    "difference_type", "UNKNOWN"
                ),
            )
            variances.append(variance)

    # Build comparison state objects
    expected_state = None
    if expected_device:
        expected_state = ComparisonState(
            device_id=expected_device.device_id,
            name=expected_device.name,
            manufacturer=expected_device.manufacturer,
            model=expected_device.model,
            serial_number=expected_device.serial_number,
            product_id=expected_device.product_id,
            management_ip=expected_device.management_ip,
            platform=expected_device.platform,
        )

    observed_state = None
    if observed_device:
        observed_state = ComparisonState(
            device_id=observed_device.device_id,
            name=observed_device.name,
            manufacturer=observed_device.manufacturer,
            model=observed_device.model,
            serial_number=observed_device.serial_number,
            product_id=observed_device.product_id,
            management_ip=observed_device.management_ip,
            platform=observed_device.platform,
        )

    return DeviceComparisonResponse(
        device_id=device_id,
        comparison_result_id=comparison.id,
        compared_at=comparison.compared_at,
        expected_state=expected_state,
        observed_state=observed_state,
        variances=variances,
    )
