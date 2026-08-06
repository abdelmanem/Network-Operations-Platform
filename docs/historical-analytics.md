# Historical Analytics Engine

## Purpose

The historical analytics engine analyzes immutable persisted discovery history without collecting live data, re-running comparisons, or introducing UI or REST surface area. It consumes the same immutable history records used by the reporting and persistence layers and produces structured trend, anomaly, and recommendation insights.

## Scope

- Reads persisted historical run records and finding records
- Classifies compliance, risk, and discovery trends
- Flags anomaly conditions from historical risk/compliance swings
- Produces recommendations and timeline entries from immutable inputs
- Provides a service wrapper for application-level integration

## Architecture

The engine follows the repository’s typed, immutable architecture:

- Context objects describe historical runs and findings
- The engine transforms that context into a structured analytics report
- Recommendation, anomaly, and timeline models remain immutable and easy to render later

## Usage

```python
from backend.app.analytics.context import HistoricalAnalyticsContext
from backend.app.analytics.engine import HistoricalAnalyticsEngine

context = HistoricalAnalyticsContext(runs=..., findings=...)
engine = HistoricalAnalyticsEngine()
report = engine.analyze(context)
```

## Notes

This milestone intentionally limits the engine to historical analysis over persisted data only. It does not add live collection, REST endpoints, or user-facing UI components.
