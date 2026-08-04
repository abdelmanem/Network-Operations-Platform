"""Collector SDK abstractions."""

from backend.app.collectors.base import BaseCollector
from backend.app.collectors.capability import CollectorCapability
from backend.app.collectors.context import CollectorContext
from backend.app.collectors.registry import CollectorRegistry
from backend.app.collectors.result import CollectorResult

__all__ = [
    "BaseCollector",
    "CollectorCapability",
    "CollectorContext",
    "CollectorRegistry",
    "CollectorResult",
]
