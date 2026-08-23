"""Cisco platform registry."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field

from backend.app.vendors.cisco.detection import CiscoDetectionSignals
from backend.app.vendors.cisco.metadata import CiscoPlatformDefinition
from backend.app.vendors.cisco.models.aironet import AIRONET_1131
from backend.app.vendors.cisco.models.ce500 import CATALYST_EXPRESS_500
from backend.app.vendors.cisco.models.ios import CATALYST_2960, CATALYST_3560
from backend.app.vendors.cisco.models.iosxe import CATALYST_2960X


PUBLIC_PLATFORM_ALIASES: dict[str, str] = {
    "cisco-ios": "catalyst-2960",
    "cisco-iosxe": "catalyst-2960x",
    "ios": "catalyst-2960",
    "iosxe": "catalyst-2960x",
    "cisco-ios-xe": "catalyst-2960x",
    "cisco-ios-x": "catalyst-2960x",
    "cisco-ios-xe-software": "catalyst-2960x",
    "cisco-ios-software": "catalyst-2960",
    "cisco-catalyst-2960": "catalyst-2960",
    "catalyst-2960": "catalyst-2960",
    "cisco-catalyst-2960x": "catalyst-2960x",
    "catalyst-2960x": "catalyst-2960x",
}


@dataclass(slots=True)
class CiscoPlatformRegistry:
    """Register and resolve Cisco platform definitions."""

    _platforms: dict[str, CiscoPlatformDefinition] = field(default_factory=dict)

    def canonicalize_family(self, family: str) -> str:
        """Normalize user-facing platform labels to canonical registry families."""

        normalized = family.strip().lower().replace("_", "-")
        normalized = re.sub(r"\s+", "-", normalized)
        normalized = normalized.strip("-")
        return PUBLIC_PLATFORM_ALIASES.get(normalized, normalized)

    def register(self, platform: CiscoPlatformDefinition) -> None:
        """Register a platform definition."""

        self._platforms[platform.family] = platform

    def get(self, family: str) -> CiscoPlatformDefinition:
        """Return a platform by family."""

        return self._platforms[family]

    def all(self) -> tuple[CiscoPlatformDefinition, ...]:
        """Return all registered platforms."""

        return tuple(self._platforms.values())

    def detect(self, signals: CiscoDetectionSignals) -> CiscoPlatformDefinition | None:
        """Return the best matching platform for the supplied signals."""

        best_match: CiscoPlatformDefinition | None = None
        best_score = 0
        for platform in self._platforms.values():
            score = self._score(platform, signals)
            if score > best_score:
                best_match = platform
                best_score = score
        return best_match

    def detect_by_model(self, model: str) -> tuple[CiscoPlatformDefinition, ...]:
        """Return platforms matching a model string."""

        return self._matches(lambda platform: platform.matches_model(model))

    def detect_by_pid(self, product_id: str) -> tuple[CiscoPlatformDefinition, ...]:
        """Return platforms matching a product id."""

        return self._matches(lambda platform: platform.matches_pid(product_id))

    def detect_by_platform_string(
        self, platform_string: str
    ) -> tuple[CiscoPlatformDefinition, ...]:
        """Return platforms matching a platform string."""

        return self._matches(
            lambda platform: platform.matches_platform_string(platform_string)
        )

    def detect_by_sys_object_id(
        self, sys_object_id: str
    ) -> tuple[CiscoPlatformDefinition, ...]:
        """Return platforms matching a sysObjectID."""

        return self._matches(
            lambda platform: platform.matches_sys_object_id(sys_object_id)
        )

    def detect_by_http_banner(
        self, http_banner: str
    ) -> tuple[CiscoPlatformDefinition, ...]:
        """Return platforms matching an HTTP banner."""

        return self._matches(lambda platform: platform.matches_http_banner(http_banner))

    def _matches(
        self, predicate: Callable[[CiscoPlatformDefinition], bool]
    ) -> tuple[CiscoPlatformDefinition, ...]:
        return tuple(
            platform for platform in self._platforms.values() if predicate(platform)
        )

    @staticmethod
    def _score(
        platform: CiscoPlatformDefinition, signals: CiscoDetectionSignals
    ) -> int:
        score = 0
        if signals.model is not None and platform.matches_model(signals.model):
            score += 5
        if signals.product_id is not None and platform.matches_pid(signals.product_id):
            score += 5
        if signals.platform_string is not None and platform.matches_platform_string(
            signals.platform_string
        ):
            score += 4
        if signals.sys_object_id is not None and platform.matches_sys_object_id(
            signals.sys_object_id
        ):
            score += 4
        if signals.http_banner is not None and platform.matches_http_banner(
            signals.http_banner
        ):
            score += 3
        return score


def default_registry() -> CiscoPlatformRegistry:
    """Return the default Cisco platform registry."""

    registry = CiscoPlatformRegistry()
    for platform in (
        CATALYST_2960,
        CATALYST_2960X,
        CATALYST_3560,
        CATALYST_EXPRESS_500,
        AIRONET_1131,
    ):
        registry.register(platform)
    return registry
