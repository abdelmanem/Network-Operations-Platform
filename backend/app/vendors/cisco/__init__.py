"""Cisco platform support framework."""

from backend.app.vendors.cisco.capabilities import (
    CiscoCapability,
    CiscoCapabilityMatrix,
)
from backend.app.vendors.cisco.detection import CiscoDetectionSignals
from backend.app.vendors.cisco.metadata import (
    CiscoPlatformDefinition,
    CiscoPlatformMetadata,
)
from backend.app.vendors.cisco.platforms import CiscoPlatformRegistry, default_registry

__all__ = [
    "CiscoCapability",
    "CiscoCapabilityMatrix",
    "CiscoDetectionSignals",
    "CiscoPlatformDefinition",
    "CiscoPlatformMetadata",
    "CiscoPlatformRegistry",
    "default_registry",
]
