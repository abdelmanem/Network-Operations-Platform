"""Optional integration scaffold for production transports."""

# ruff: noqa: I001

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("NOP_TRANSPORT_INTEGRATION") != "1",
    reason="Enable NOP_TRANSPORT_INTEGRATION=1 to run live transport checks.",
)


def test_production_transport_scaffold() -> None:
    """Placeholder for future live transport integration checks."""

    assert True
