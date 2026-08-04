from backend.app.transports.timeout import TransportTimeout


def test_transport_timeout_serializes_to_mapping() -> None:
    timeout = TransportTimeout(connect_seconds=5.0, total_seconds=10.0)

    assert timeout.as_dict()["connect"] == 5.0
    assert timeout.as_dict()["total"] == 10.0
