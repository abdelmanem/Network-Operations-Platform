from __future__ import annotations

import os

import pytest


@pytest.mark.skipif(
    os.getenv("NOP_CISCO_INTEGRATION") != "1",
    reason="Cisco inventory integration tests require NOP_CISCO_INTEGRATION=1.",
)
def test_cisco_inventory_integration_scaffold() -> None:
    """Document the opt-in marker for future live device integration tests."""

    assert os.getenv("NOP_CISCO_INTEGRATION") == "1"
