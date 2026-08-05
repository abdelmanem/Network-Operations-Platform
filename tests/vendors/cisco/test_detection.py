from __future__ import annotations

from backend.app.vendors.cisco.detection import CiscoDetectionSignals
from backend.app.vendors.cisco.platforms import default_registry


def test_platform_detection_matches_supported_signals() -> None:
    registry = default_registry()

    assert registry.detect(CiscoDetectionSignals(model="WS-C2960-24TT-L")).family == (
        "catalyst-2960"
    )
    assert registry.detect(
        CiscoDetectionSignals(product_id="WS-C2960X-24TS-L")
    ).family == ("catalyst-2960x")
    assert (
        registry.detect(
            CiscoDetectionSignals(platform_string="Cisco IOS XE Software")
        ).family
        == "catalyst-2960x"
    )
    assert registry.detect(
        CiscoDetectionSignals(sys_object_id="1.3.6.1.4.1.9.1.748")
    ).family == ("catalyst-express-500")
    assert (
        registry.detect(CiscoDetectionSignals(http_banner="Cisco Aironet wireless"))
        is not None
    )
