from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


def test_immutable_history_migration_is_registered() -> None:
    config = Config("alembic.ini")
    script = ScriptDirectory.from_config(config)
    revision = script.get_revision("20260805_1300")

    assert revision is not None
    assert revision.module.revision == "20260805_1300"


def test_immutable_history_migration_contains_required_tables() -> None:
    migration = Path("alembic/versions/20260805_1300_immutable_discovery_history.py")
    contents = migration.read_text(encoding="utf-8")

    for table_name in (
        "discovery_runs",
        "snapshots",
        "snapshot_devices",
        "snapshot_interfaces",
        "snapshot_vlans",
        "snapshot_neighbors",
        "comparison_results",
        "findings",
        "evidence",
    ):
        assert table_name in contents
