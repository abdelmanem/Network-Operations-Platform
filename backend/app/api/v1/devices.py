from __future__ import annotations

from datetime import datetime
from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.api.v1.dependencies import get_db_session
from backend.app.persistence.models import SnapshotDeviceRecord, SnapshotSource
from backend.app.persistence.repositories import FindingRepository, SnapshotRepository
from backend.app.schemas.comparison import (
    ComparisonState,
    DeviceComparisonResponse,
    VarianceSummary,
)
from backend.app.schemas.devices import DeviceHistoryItem, DeviceHistoryResponse

router = APIRouter(prefix="/devices", tags=["devices"])


def _normalize_device_identity(value: str | None) -> str:
    return "" if value is None else value.strip().casefold()


def _match_device_by_identity(
    devices: list[SnapshotDeviceRecord] | tuple[SnapshotDeviceRecord, ...],
    *,
    device_id: str | None = None,
    name: str | None = None,
    serial_number: str | None = None,
) -> SnapshotDeviceRecord | None:
    if not devices:
        return None

    for field_name, raw_value in (
        ("device_id", device_id),
        ("name", name),
        ("serial_number", serial_number),
    ):
        if raw_value is None:
            continue
        normalized_value = _normalize_device_identity(raw_value)
        for device in devices:
            candidate = getattr(device, field_name, None)
            if field_name == "device_id" and candidate == raw_value:
                return device
            if field_name in {"name", "serial_number"} and (
                _normalize_device_identity(candidate) == normalized_value
            ):
                return device
    return None


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

    # Match devices using the same logical identity semantics as the accepted
    # comparison pipeline: exact device_id first, then normalized name, then serial.
    expected_device = None
    if expected_snapshot:
        expected_devices = snapshot_repo.get_snapshot_devices(expected_snapshot.id)
        expected_device = _match_device_by_identity(
            expected_devices,
            device_id=device_id,
            name=device_id,
        )

    observed_device = None
    if observed_snapshot:
        observed_devices = snapshot_repo.get_snapshot_devices(observed_snapshot.id)
        observed_device = _match_device_by_identity(
            observed_devices,
            device_id=device_id,
            name=(expected_device.name if expected_device is not None else device_id),
            serial_number=(
                expected_device.serial_number
                if expected_device is not None
                else None
            ),
        )
        if observed_device is None and expected_device is not None:
            observed_device = _match_device_by_identity(
                observed_devices,
                name=expected_device.name,
                serial_number=expected_device.serial_number,
            )

    if observed_device is None:
        live_devices = snapshot_repo.get_latest_live_devices()
        observed_device = _match_device_by_identity(
            live_devices,
            device_id=device_id,
            name=(expected_device.name if expected_device is not None else device_id),
            serial_number=(
                expected_device.serial_number
                if expected_device is not None
                else None
            ),
        )
        if observed_device is None and expected_device is not None:
            observed_device = _match_device_by_identity(
                live_devices,
                name=expected_device.name,
                serial_number=expected_device.serial_number,
            )

    if expected_device is None and observed_device is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device {device_id} not found in any snapshot.",
        )

    # Findings are persisted against the comparison's logical subject name.
    target_names = {
        _normalize_device_identity(device_id),
    }
    if expected_device is not None:
        target_names.add(_normalize_device_identity(expected_device.name))
    if observed_device is not None:
        target_names.add(_normalize_device_identity(observed_device.name))
    findings = tuple(
        finding
        for finding in comparison.findings
        if any(
            (
                subject_id := _normalize_device_identity(
                    str(evidence.details.get("subject_id"))
                )
            )
            and any(
                subject_id == target_name or subject_id.startswith(target_name + ":")
                for target_name in target_names
            )
            for evidence in finding.evidence
            if isinstance(evidence.details, dict)
        )
    )

    # Build variance summary from findings
    variances = []
    for finding in findings:
        if isinstance(finding.expected_state, dict) and isinstance(
            finding.observed_state, dict
        ):
            diff_type = str(
                finding.expected_state.get(
                    "difference_type",
                    finding.observed_state.get("difference_type"),
                )
                or "UNKNOWN"
            )
            if observed_device is not None and diff_type.lower() == "missing":
                continue

            evidence_details = next(
                (
                    evidence.details
                    for evidence in finding.evidence
                    if isinstance(evidence.details, dict)
                ),
                {},
            )
            variance = VarianceSummary(
                field_name=str(
                    evidence_details.get(
                        "field_name", finding.expected_state.get("field_name")
                    )
                    or "unknown"
                ),
                expected_value=finding.expected_state.get("value"),
                observed_value=finding.observed_state.get("value"),
                difference_type=diff_type,
            )
            variances.append(variance)

    # When both expected and observed live devices are present, ensure field-level
    # attribute differences (e.g. serial_number) are represented even if the comparison
    # record did not contain findings for this specific snapshot.
    if expected_device is not None and observed_device is not None:
        existing_fields = {v.field_name for v in variances}
        if (
            expected_device.serial_number
            and observed_device.serial_number
            and _normalize_device_identity(expected_device.serial_number)
            != _normalize_device_identity(observed_device.serial_number)
            and "serial_number" not in existing_fields
            and "serial" not in existing_fields
        ):
            variances.append(
                VarianceSummary(
                    field_name="serial_number",
                    expected_value=expected_device.serial_number,
                    observed_value=observed_device.serial_number,
                    difference_type="modified",
                )
            )
        if (
            expected_device.model
            and observed_device.model
            and _normalize_device_identity(expected_device.model)
            != _normalize_device_identity(observed_device.model)
            and "model" not in existing_fields
        ):
            variances.append(
                VarianceSummary(
                    field_name="model",
                    expected_value=expected_device.model,
                    observed_value=observed_device.model,
                    difference_type="modified",
                )
            )

    # If observed_device is missing, ensure a missing variance is present
    if observed_device is None and not variances:
        variances.append(
            VarianceSummary(
                field_name="device",
                expected_value=expected_device.name if expected_device else device_id,
                observed_value=None,
                difference_type="missing",
            )
        )

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
