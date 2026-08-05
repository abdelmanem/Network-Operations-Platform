from __future__ import annotations

from backend.app.transports.base import TransportCapability
from backend.app.vendors.cisco.capabilities import (
    CiscoCapability,
    CiscoCapabilityMatrix,
)


def test_capability_matrix_reports_supported_features() -> None:
    matrix = CiscoCapabilityMatrix()

    assert matrix.supports("catalyst-2960x", CiscoCapability.HTTP) is True
    assert matrix.supports("catalyst-2960", CiscoCapability.HTTP) is False
    assert matrix.transport_support("aironet-1131") == frozenset(
        {TransportCapability.HTTP, TransportCapability.SNMP}
    )
    assert CiscoCapability.CONFIG_BACKUP in matrix.capabilities("catalyst-3560")
