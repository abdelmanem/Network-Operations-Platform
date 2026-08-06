# Reporting and Export Engine

The reporting engine is a framework-agnostic, immutable pipeline for building, rendering, and exporting reports from cached discovery, comparison, compliance, findings, evidence, and metrics data.

## Architecture

- Report data is assembled by the builder from a cached ReportContext.
- Rendering translates immutable report data into a structured document tree.
- Exporters consume the rendered document tree through the same interface.

## Supported report types

- Executive Summary
- Inventory Report
- Discovery Report
- Compliance Report
- Difference Report
- Finding Report
- Historical Report
- Technical Report

## Notes

- The engine never recollects devices, reruns comparison, or reruns compliance evaluation.
- Recommendations remain structured data instead of hardcoded prose.
- Templates are pluggable and do not embed presentation logic.
