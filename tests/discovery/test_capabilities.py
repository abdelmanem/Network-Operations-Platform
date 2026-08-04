from backend.app.collectors.capability import CollectorCapability


def test_collector_capabilities_include_network_primitives() -> None:
    assert CollectorCapability.SSH.value == "SSH"
    assert CollectorCapability.SNMP.value == "SNMP"
    assert CollectorCapability.LLDP.value == "LLDP"
