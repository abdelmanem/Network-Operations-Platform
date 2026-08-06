"""Shared exporter helpers."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from backend.app.reporting.models import DocumentNode, RenderedDocument


def document_to_dict(document: RenderedDocument) -> dict[str, Any]:
    """Serialize a rendered document to a dictionary."""

    return {
        "report_type": document.report_type.value,
        "metadata": {
            "title": document.metadata.title,
            "run_id": (
                str(document.metadata.run_id)
                if document.metadata.run_id is not None
                else None
            ),
            "generated_at": (
                document.metadata.generated_at.isoformat()
                if document.metadata.generated_at is not None
                else None
            ),
            "site": document.metadata.site,
            "device_role": document.metadata.device_role,
            "platform": document.metadata.platform,
        },
        "statistics": _statistics_dict(document),
        "recommendations": [
            {
                "recommendation_id": item.recommendation_id,
                "category": item.category.value,
                "action": item.action.value,
                "priority": item.priority.value,
                "subject_type": item.subject_type,
                "subject_id": item.subject_id,
                "reason_code": item.reason_code,
            }
            for item in document.recommendations
        ],
        "document": node_to_dict(document.root),
    }


def node_to_dict(node: DocumentNode) -> dict[str, Any]:
    """Serialize a document node."""

    return {
        "node_type": node.node_type.value,
        "attributes": _serialize_attributes(node.attributes),
        "children": [node_to_dict(child) for child in node.children],
    }


def _statistics_dict(document: RenderedDocument) -> dict[str, object]:
    stats = document.statistics
    return {
        "total_devices": stats.total_devices,
        "reachable_devices": stats.reachable_devices,
        "unreachable_devices": stats.unreachable_devices,
        "discovery_success_pct": stats.discovery_success_pct,
        "netbox_accuracy_pct": stats.netbox_accuracy_pct,
        "compliance_score": stats.compliance_score,
        "critical_findings": stats.critical_findings,
        "major_findings": stats.major_findings,
        "minor_findings": stats.minor_findings,
        "missing_devices": stats.missing_devices,
        "extra_devices": stats.extra_devices,
        "changed_devices": stats.changed_devices,
        "interface_changes": stats.interface_changes,
        "vlan_changes": stats.vlan_changes,
        "configuration_changes": stats.configuration_changes,
    }


def _serialize_attributes(attributes: Mapping[str, object]) -> dict[str, object]:
    serialized: dict[str, object] = {}
    for key, value in attributes.items():
        if isinstance(value, tuple):
            serialized[key] = list(value)
        else:
            serialized[key] = value
    return serialized


def document_to_json(document: RenderedDocument) -> bytes:
    """Serialize a rendered document to JSON bytes."""

    return json.dumps(document_to_dict(document), indent=2, default=str).encode("utf-8")
