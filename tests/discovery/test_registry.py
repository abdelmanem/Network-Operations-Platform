from dataclasses import dataclass

from backend.app.discovery.registry import DiscoveryRegistry


@dataclass(slots=True)
class DummyPipeline:
    name: str = "default"


def test_discovery_registry_registers_and_resolves_pipeline() -> None:
    registry = DiscoveryRegistry()
    pipeline = DummyPipeline()

    registry.register("default", pipeline)

    assert registry.get("default") is pipeline
    assert registry.names() == ("default",)
