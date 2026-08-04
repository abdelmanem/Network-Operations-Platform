"""Discovery pipeline registry."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class DiscoveryRegistry:
    """Register named discovery pipelines."""

    _pipelines: dict[str, object] = field(default_factory=dict)

    def register(self, name: str, pipeline: object) -> None:
        """Register a discovery pipeline."""

        self._pipelines[name] = pipeline

    def get(self, name: str) -> object:
        """Return a registered pipeline."""

        try:
            return self._pipelines[name]
        except KeyError as exc:
            raise KeyError(f"Unknown discovery pipeline: {name}") from exc

    def names(self) -> tuple[str, ...]:
        """Return registered pipeline names."""

        return tuple(self._pipelines)
