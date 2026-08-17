from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID
from pydantic import BaseModel, Field


class InventoryCounts(BaseModel):
    """Counts of devices, interfaces, IP addresses, and VLANs."""

    devices: int = 0
    interfaces: int = 0
    ip_addresses: int = 0
    vlans: int = 0


class NetBoxIntegrationStatusResponse(BaseModel):
    """Safe connection status reporting."""

    configured: bool
    connected: bool
    tls_verified: bool
    authenticated: bool
    version: str | None = None
    hostname: str | None = None
    last_successful_sync: datetime | None = None
    current_sync_status: str  # idle, queued, running, succeeded, failed
    sync_started_at: datetime | None = None
    sync_completed_at: datetime | None = None
    sync_error: str | None = None
    inventory_counts: InventoryCounts = Field(default_factory=InventoryCounts)


class NetBoxTestConnectionResponse(BaseModel):
    """Connection test diagnostic details."""

    connected: bool
    tls_verified: bool
    authenticated: bool
    version: str | None = None
    hostname: str | None = None
    message: str


class NetBoxSyncResponse(BaseModel):
    """Synchronization submission response."""

    job_id: UUID
    status: str = "queued"


class NetBoxErrorContract(BaseModel):
    """Standard NetBox integration error contract."""

    code: str
    message: str
    details: Any = None
