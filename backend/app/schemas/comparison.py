from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ComparisonResultResponse(BaseModel):
    id: UUID
    expected_snapshot_id: UUID
    observed_snapshot_id: UUID
    compared_at: datetime
    metrics: dict[str, object] = Field(default_factory=dict)
    findings: list[dict[str, object]] = Field(default_factory=list)


class ComparisonState(BaseModel):
    """Expected or observed state for a device."""

    device_id: str
    name: str | None = None
    manufacturer: str | None = None
    model: str | None = None
    serial_number: str | None = None
    product_id: str | None = None
    management_ip: str | None = None
    platform: str | None = None


class VarianceSummary(BaseModel):
    """Summary of a variance for a single field."""

    field_name: str = Field(description="Name of the field that differs")
    expected_value: object | None = Field(description="Value from expected state")
    observed_value: object | None = Field(description="Value from observed state")
    difference_type: str = Field(
        description="Type of difference: MISSING, UNEXPECTED, MODIFIED, etc."
    )


class DeviceComparisonResponse(BaseModel):
    """Full comparison for a single device."""

    device_id: str
    comparison_result_id: UUID | None = None
    compared_at: datetime | None = None
    expected_state: ComparisonState | None = None
    observed_state: ComparisonState | None = None
    variances: list[VarianceSummary] = Field(
        default_factory=list, description="List of differences between states"
    )
