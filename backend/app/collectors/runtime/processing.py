"""Shared collector payload processing used by runtime and discovery execution."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from backend.app.normalization.engine import NormalizationEngine, NormalizationResult
from backend.app.parsers.context import ParserContext, ParserInputFormat
from backend.app.parsers.pipeline import ParserPipeline
from backend.app.parsers.result import ParserResult
from backend.app.snapshot.mapper import SnapshotMapper
from backend.app.snapshot.models import InventorySnapshotModel


@dataclass(frozen=True, slots=True)
class ProcessedCollectorPayload:
    """Canonical result of parsing and normalizing a collector payload."""

    parsed_result: ParserResult
    normalized_result: NormalizationResult
    snapshot_model: InventorySnapshotModel


def process_collector_payload(
    *,
    parser_pipeline: ParserPipeline,
    normalization_engine: NormalizationEngine,
    snapshot_mapper: SnapshotMapper,
    source: str,
    parser_name: str | None,
    run_id: UUID,
    metadata: dict[str, object],
    raw_payload: dict[str, object],
) -> ProcessedCollectorPayload:
    """Run the common parser and normalizer pipeline for collected raw data."""

    parser_context = ParserContext(
        source=source,
        input_format=ParserInputFormat.JSON,
        parser_name=parser_name,
        run_id=run_id,
        metadata=dict(metadata),
    )
    parsed_result = parser_pipeline.parse(parser_context, raw_payload)
    normalized_result = normalization_engine.normalize(parsed_result)
    return ProcessedCollectorPayload(
        parsed_result=parsed_result,
        normalized_result=normalized_result,
        snapshot_model=snapshot_mapper.to_model(normalized_result.snapshot),
    )
