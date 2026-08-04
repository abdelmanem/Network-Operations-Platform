import pytest
from backend.app.core.exceptions import PluginError
from backend.app.core.plugins import PluginRegistry


class DemoPlugin:
    name = "demo"

    def register(self, registry: PluginRegistry) -> None:
        registry.register(self)


def test_plugin_registry_registers_and_resolves() -> None:
    registry = PluginRegistry()
    plugin = DemoPlugin()

    registry.register(plugin)

    assert registry.get("demo") is plugin
    assert registry.list() == (plugin,)


def test_plugin_registry_rejects_duplicates() -> None:
    registry = PluginRegistry()
    plugin = DemoPlugin()

    registry.register(plugin)

    with pytest.raises(PluginError):
        registry.register(plugin)
