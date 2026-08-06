"""Validation utilities for NetBox inventory data."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TypeVar, cast

from pydantic import BaseModel, ValidationError

from backend.app.integrations.netbox.exceptions import (
    NetBoxValidationError,
    NetBoxVersionMismatchError,
)

TModel = TypeVar("TModel", bound=BaseModel)


def validate_required_keys(
    payload: Mapping[str, object],
    keys: Sequence[str],
    *,
    context: str,
) -> None:
    """Ensure a payload includes the expected keys."""

    missing_keys = [key for key in keys if key not in payload]
    if missing_keys:
        joined_keys = ", ".join(missing_keys)
        raise NetBoxValidationError(
            f"{context} is missing required keys: {joined_keys}"
        )


def validate_collection_payload(
    payload: object,
    *,
    context: str,
) -> Mapping[str, object]:
    """Validate a NetBox collection response shape."""

    if not isinstance(payload, Mapping):
        raise NetBoxValidationError(f"{context} must be a mapping.")

    validate_required_keys(payload, ("count", "results"), context=context)
    results = payload["results"]
    if not isinstance(results, list):
        raise NetBoxValidationError(f"{context} results must be a list.")

    return cast(Mapping[str, object], payload)


def validate_model[
    TModel: BaseModel
](payload: object, model_type: type[TModel], *, context: str,) -> TModel:
    """Validate a single payload against a Pydantic model."""

    try:
        return model_type.model_validate(payload)
    except ValidationError as exc:
        raise NetBoxValidationError(f"{context} is invalid.") from exc


def validate_version(
    expected_version: str,
    actual_version: str | None,
    *,
    context: str,
) -> None:
    """Validate a NetBox version string."""

    if actual_version is None:
        raise NetBoxValidationError(f"{context} did not include a version string.")

    if actual_version != expected_version:
        raise NetBoxVersionMismatchError(
            expected_version=expected_version,
            actual_version=actual_version,
        )
