"""Plugin registry for application extensions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from backend.app.core.exceptions import PluginError


class Plugin(Protocol):
    """Protocol implemented by application plugins."""

    name: str

    def register(self, registry: PluginRegistry) -> None:
        """Register the plugin with the application."""


type PluginName = str


@dataclass(slots=True)
class PluginRegistry:
    """In-memory plugin registry."""

    _plugins: dict[PluginName, Plugin] = field(default_factory=dict)

    def register(self, plugin: Plugin) -> None:
        """Register a plugin instance."""

        if plugin.name in self._plugins:
            raise PluginError(f"Plugin '{plugin.name}' is already registered.")
        self._plugins[plugin.name] = plugin

    def get(self, name: PluginName) -> Plugin:
        """Return a registered plugin."""

        try:
            return self._plugins[name]
        except KeyError as exc:
            raise PluginError(f"Plugin '{name}' is not registered.") from exc

    def list(self) -> tuple[Plugin, ...]:
        """Return all registered plugins."""

        return tuple(self._plugins.values())
