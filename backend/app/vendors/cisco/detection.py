"""Cisco platform detection helpers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CiscoDetectionSignals:
    """Optional inputs used to identify a Cisco platform."""

    model: str | None = None
    product_id: str | None = None
    platform_string: str | None = None
    sys_object_id: str | None = None
    http_banner: str | None = None
