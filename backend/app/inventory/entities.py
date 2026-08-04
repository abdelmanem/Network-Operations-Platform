"""Canonical immutable inventory models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class InventoryModel(BaseModel):
    """Base model for canonical inventory objects."""

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)


class Site(InventoryModel):
    """Canonical site object."""

    name: str
    slug: str
    region: str | None = None
    location: str | None = None
    facility: str | None = None
    description: str | None = None


class Rack(InventoryModel):
    """Canonical rack object."""

    name: str
    site_name: str
    facility_id: str | None = None
    u_height: int | None = None
    role: str | None = None
    description: str | None = None


class Manufacturer(InventoryModel):
    """Canonical manufacturer object."""

    name: str
    slug: str


class DeviceType(InventoryModel):
    """Canonical device type object."""

    manufacturer: Manufacturer
    model: str
    slug: str
    part_number: str | None = None
    u_height: int | None = None
    is_full_depth: bool | None = None


class Platform(InventoryModel):
    """Canonical platform object."""

    name: str
    slug: str
    manufacturer_name: str | None = None
    napalm_driver: str | None = None


class Role(InventoryModel):
    """Canonical role object."""

    name: str
    slug: str
    color: str | None = None


class Interface(InventoryModel):
    """Canonical interface object."""

    name: str
    device_name: str
    type: str | None = None
    enabled: bool = True
    mac_address: str | None = None
    description: str | None = None


class IPAddress(InventoryModel):
    """Canonical IP address object."""

    address: str
    family: int
    status: str | None = None
    dns_name: str | None = None
    assigned_object_type: str | None = None
    assigned_object_name: str | None = None
    device_name: str | None = None


class VLAN(InventoryModel):
    """Canonical VLAN object."""

    vid: int
    name: str
    site_name: str | None = None
    status: str | None = None
    role: str | None = None


class Device(InventoryModel):
    """Canonical device object."""

    name: str
    site_name: str | None = None
    rack_name: str | None = None
    device_type: DeviceType
    role: Role | None = None
    platform: Platform | None = None
    serial: str | None = None
    status: str | None = None
    primary_ip: str | None = None
    interfaces: tuple[Interface, ...] = Field(default_factory=tuple)
    ip_addresses: tuple[IPAddress, ...] = Field(default_factory=tuple)
