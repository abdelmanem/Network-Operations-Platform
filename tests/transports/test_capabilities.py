from backend.app.transports.base import TransportCapability


def test_transport_capabilities_include_core_channels() -> None:
    assert TransportCapability.SSH.value == "SSH"
    assert TransportCapability.SNMP.value == "SNMP"
    assert TransportCapability.HTTP.value == "HTTP"
