"""Metadata helpers for policy definitions."""

from __future__ import annotations

from backend.app.policies.models import PolicyMetadata


class PolicyMetadataBuilder:
    """Simple builder for metadata values."""

    @staticmethod
    def from_values(
        *,
        owner: str | None = None,
        tags: tuple[str, ...] | None = None,
    ) -> PolicyMetadata:
        return PolicyMetadata(owner=owner, tags=() if tags is None else tags)
