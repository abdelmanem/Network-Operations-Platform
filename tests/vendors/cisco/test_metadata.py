from __future__ import annotations

import pytest
from backend.app.transports.base import TransportCapability
from backend.app.vendors.cisco.capabilities import CiscoCapability
from backend.app.vendors.cisco.catalog.commands import build_common_command_catalog
from backend.app.vendors.cisco.catalog.http import build_common_http_catalog
from backend.app.vendors.cisco.catalog.snmp import build_common_snmp_catalog
from backend.app.vendors.cisco.metadata import CiscoPlatformMetadata


def test_platform_metadata_validation_rejects_missing_fields() -> None:
    with pytest.raises(ValueError):
        CiscoPlatformMetadata(
            family="",
            display_name="Cisco Catalyst 2960",
            model_names=("WS-C2960-24TT-L",),
            product_ids=("WS-C2960-24TT-L",),
            transport_support=frozenset({TransportCapability.SSH}),
            parser_family="ios",
            firmware_family="ios",
            capabilities=frozenset({CiscoCapability.SSH}),
        )


def test_platform_metadata_validation_accepts_valid_metadata() -> None:
    metadata = CiscoPlatformMetadata(
        family="catalyst-2960",
        display_name="Cisco Catalyst 2960",
        model_names=("WS-C2960-24TT-L",),
        product_ids=("WS-C2960-24TT-L",),
        transport_support=frozenset({TransportCapability.SSH}),
        parser_family="ios",
        firmware_family="ios",
        capabilities=frozenset({CiscoCapability.SSH}),
    )

    assert metadata.family == "catalyst-2960"
    assert build_common_command_catalog().categories()
    assert build_common_snmp_catalog().groups_names()
    assert build_common_http_catalog().paths()
