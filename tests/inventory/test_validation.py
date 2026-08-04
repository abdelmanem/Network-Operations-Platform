import pytest
from backend.app.integrations.netbox.exceptions import (
    NetBoxValidationError,
    NetBoxVersionMismatchError,
)
from backend.app.integrations.netbox.models import NetBoxSite
from backend.app.inventory.validation import (
    validate_collection_payload,
    validate_model,
    validate_version,
)


def test_validate_collection_payload_rejects_missing_results() -> None:
    with pytest.raises(NetBoxValidationError):
        validate_collection_payload({"count": 1}, context="sites")


def test_validate_model_parses_site_payload() -> None:
    site = validate_model(
        {"id": 1, "name": "Site A", "slug": "site-a"},
        NetBoxSite,
        context="site",
    )

    assert site.name == "Site A"


def test_validate_version_rejects_mismatch() -> None:
    with pytest.raises(NetBoxVersionMismatchError):
        validate_version("4.6.7", "4.6.6", context="NetBox")
