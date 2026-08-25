"""Durable discovery-job worker lease policy.

The worker may observe jobs across tenants, but every claim, heartbeat,
recovery, and state update remains explicitly tenant-scoped. Expired owned
leases are reconciled to a terminal state and are never automatically resumed.
"""

from __future__ import annotations

from uuid import UUID

PROTECTED_DISCOVERY_JOB_ID = UUID("d792bcff-fb06-4428-ab53-557e0cd6eeb9")
DISCOVERY_JOB_LEASE_SECONDS = 120.0
DISCOVERY_JOB_HEARTBEAT_INTERVAL_SECONDS = 30.0
DISCOVERY_JOB_POLL_INTERVAL_SECONDS = 1.0
DISCOVERY_JOB_CLAIM_LIMIT = 8

LEASE_EXPIRED_MESSAGE = (
    "Discovery worker lease expired; execution was not resumed."
)
HEARTBEAT_LOST_MESSAGE = (
    "Discovery worker heartbeat failed; execution was stopped without resume."
)
