"""NetBox response and inventory models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import cast

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator


def _unwrap_choice_value(value: object) -> object | None:
    """Normalize NetBox enum-like values from dicts or objects."""

    if value is None:
        return None
    if isinstance(value, dict):
        inner_value = value.get("value")
        return cast(object | None, inner_value)
    if isinstance(value, BaseModel):
        payload = value.model_dump()
        if isinstance(payload, dict):
            inner_value = payload.get("value")
            if inner_value is not None:
                return cast(object, inner_value)
    try:
        choice_value = object.__getattribute__(value, "value")
    except (AttributeError, TypeError):
        return None
    return cast(object, choice_value)


def _coerce_int(value: object) -> int | None:
    """Coerce NetBox integer-like values to a Python int."""

    if value is None:
        return None

    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None

    normalized = _unwrap_choice_value(value)
    if normalized is None:
        return None
    return _coerce_int(normalized)


class NetBoxModel(BaseModel):
    """Base model for NetBox payloads."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class NetBoxChoice(NetBoxModel):
    """NetBox choice field representation."""

    value: str
    label: str


class NetBoxObjectReference(NetBoxModel):
    """Reference to a related NetBox object."""

    id: int
    name: str | None = None
    slug: str | None = None
    display: str | None = None


class NetBoxIPAddressReference(NetBoxModel):
    """Reference to a NetBox IP address."""

    id: int
    address: str
    family: int | None = None
    display: str | None = None

    @field_validator("family", mode="before")
    @classmethod
    def _validate_family(cls, v: object) -> int | None:
        return _coerce_int(v)


class NetBoxDeviceTypeReference(NetBoxModel):
    """Reference to a NetBox device type."""

    id: int
    model: str
    slug: str | None = None
    display: str | None = None
    manufacturer: NetBoxObjectReference | None = None


class NetBoxStatusResponse(NetBoxModel):
    """Representation of the NetBox status endpoint."""

    version: str | None = Field(
        default=None,
        validation_alias=AliasChoices("version", "netbox_version", "netbox-version"),
    )
    api_version: str | None = Field(
        default=None,
        validation_alias=AliasChoices("api_version", "api-version"),
    )
    hostname: str | None = None
    status: str | None = None


class NetBoxCollectionResponse[ModelT: NetBoxModel](NetBoxModel):
    """Generic paginated NetBox REST response."""

    count: int
    next: str | None = None
    previous: str | None = None
    results: list[ModelT] = Field(default_factory=list)


class NetBoxSite(NetBoxModel):
    """Validated site payload from NetBox."""

    id: int
    name: str
    slug: str
    region: NetBoxObjectReference | None = None
    location: NetBoxObjectReference | None = None
    facility: str | None = None
    description: str | None = None
    status: NetBoxChoice | None = None


class NetBoxRack(NetBoxModel):
    """Validated rack payload from NetBox."""

    id: int
    name: str
    site: NetBoxObjectReference
    facility_id: str | None = None
    u_height: int | None = None
    role: NetBoxObjectReference | None = None
    description: str | None = None


class NetBoxManufacturer(NetBoxModel):
    """Validated manufacturer payload from NetBox."""

    id: int
    name: str
    slug: str


class NetBoxDeviceType(NetBoxModel):
    """Validated device type payload from NetBox."""

    id: int
    manufacturer: NetBoxObjectReference
    model: str
    slug: str
    part_number: str | None = None
    u_height: int | None = None
    is_full_depth: bool | None = None


class NetBoxRole(NetBoxModel):
    """Validated device role payload from NetBox."""

    id: int
    name: str
    slug: str
    color: str | None = None


class NetBoxPlatform(NetBoxModel):
    """Validated platform payload from NetBox."""

    id: int
    name: str
    slug: str
    manufacturer: NetBoxObjectReference | None = None
    napalm_driver: str | None = None


class NetBoxDevice(NetBoxModel):
    """Validated device payload from NetBox."""

    id: int
    name: str
    device_type: NetBoxDeviceTypeReference
    site: NetBoxObjectReference | None = None
    rack: NetBoxObjectReference | None = None
    role: NetBoxObjectReference | None = None
    platform: NetBoxObjectReference | None = None
    serial: str | None = None
    status: NetBoxChoice | None = None
    primary_ip4: NetBoxIPAddressReference | None = None
    primary_ip6: NetBoxIPAddressReference | None = None


class NetBoxInterface(NetBoxModel):
    """Validated interface payload from NetBox."""

    id: int
    name: str
    device: NetBoxObjectReference
    type: str | None = None
    enabled: bool = True
    mac_address: str | None = None
    description: str | None = None

    @field_validator("type", mode="before")
    @classmethod
    def _validate_type(cls, v: object) -> str | None:
        value = _unwrap_choice_value(v)
        if value is None:
            return None
        return str(value)


class NetBoxIPAddress(NetBoxModel):
    """Validated IP address payload from NetBox."""

    id: int
    address: str
    family: int
    status: NetBoxChoice | None = None
    dns_name: str | None = None
    assigned_object_type: str | None = None
    assigned_object: NetBoxObjectReference | None = None

    @field_validator("family", mode="before")
    @classmethod
    def _validate_family(cls, v: object) -> int | None:
        return _coerce_int(v)


class NetBoxVLAN(NetBoxModel):
    """Validated VLAN payload from NetBox."""

    id: int
    vid: int
    name: str
    site: NetBoxObjectReference | None = None
    status: NetBoxChoice | None = None
    role: NetBoxObjectReference | None = None


@dataclass(frozen=True, slots=True)
class NetBoxInventoryDataset:
    """Grouped NetBox payloads used to build canonical inventory."""

    sites: tuple[NetBoxSite, ...] = field(default_factory=tuple)
    racks: tuple[NetBoxRack, ...] = field(default_factory=tuple)
    devices: tuple[NetBoxDevice, ...] = field(default_factory=tuple)
    interfaces: tuple[NetBoxInterface, ...] = field(default_factory=tuple)
    ip_addresses: tuple[NetBoxIPAddress, ...] = field(default_factory=tuple)
    vlans: tuple[NetBoxVLAN, ...] = field(default_factory=tuple)
    platforms: tuple[NetBoxPlatform, ...] = field(default_factory=tuple)
    manufacturers: tuple[NetBoxManufacturer, ...] = field(default_factory=tuple)
    device_types: tuple[NetBoxDeviceType, ...] = field(default_factory=tuple)
    roles: tuple[NetBoxRole, ...] = field(default_factory=tuple)
