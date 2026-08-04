"""Mapping layer from NetBox payloads to canonical inventory models."""

from __future__ import annotations

from dataclasses import dataclass

from backend.app.integrations.netbox.models import (
    NetBoxDevice,
    NetBoxDeviceType,
    NetBoxInterface,
    NetBoxIPAddress,
    NetBoxManufacturer,
    NetBoxObjectReference,
    NetBoxPlatform,
    NetBoxRack,
    NetBoxRole,
    NetBoxSite,
    NetBoxVLAN,
)
from backend.app.inventory.entities import (
    VLAN,
    Device,
    DeviceType,
    Interface,
    IPAddress,
    Manufacturer,
    Platform,
    Rack,
    Role,
    Site,
)


def _reference_name(reference: NetBoxObjectReference | None) -> str | None:
    return (
        None
        if reference is None
        else reference.name or reference.slug or str(reference.id)
    )


@dataclass(slots=True)
class NetBoxInventoryMapper:
    """Transform NetBox payloads into canonical inventory models."""

    def site(self, payload: NetBoxSite) -> Site:
        """Map a NetBox site payload."""

        return Site(
            name=payload.name,
            slug=payload.slug,
            region=_reference_name(payload.region),
            location=_reference_name(payload.location),
            facility=payload.facility,
            description=payload.description,
        )

    def rack(self, payload: NetBoxRack) -> Rack:
        """Map a NetBox rack payload."""

        return Rack(
            name=payload.name,
            site_name=_reference_name(payload.site) or "",
            facility_id=payload.facility_id,
            u_height=payload.u_height,
            role=_reference_name(payload.role),
            description=payload.description,
        )

    def manufacturer(self, payload: NetBoxManufacturer) -> Manufacturer:
        """Map a NetBox manufacturer payload."""

        return Manufacturer(name=payload.name, slug=payload.slug)

    def device_type(self, payload: NetBoxDeviceType) -> DeviceType:
        """Map a NetBox device type payload."""

        return DeviceType(
            manufacturer=Manufacturer(
                name=payload.manufacturer.name or payload.manufacturer.display or "",
                slug=payload.manufacturer.slug
                or payload.manufacturer.name
                or payload.manufacturer.display
                or "",
            ),
            model=payload.model,
            slug=payload.slug,
            part_number=payload.part_number,
            u_height=payload.u_height,
            is_full_depth=payload.is_full_depth,
        )

    def platform(self, payload: NetBoxPlatform) -> Platform:
        """Map a NetBox platform payload."""

        return Platform(
            name=payload.name,
            slug=payload.slug,
            manufacturer_name=_reference_name(payload.manufacturer),
            napalm_driver=payload.napalm_driver,
        )

    def role(self, payload: NetBoxRole) -> Role:
        """Map a NetBox role payload."""

        return Role(name=payload.name, slug=payload.slug, color=payload.color)

    def interface(self, payload: NetBoxInterface) -> Interface:
        """Map a NetBox interface payload."""

        return Interface(
            name=payload.name,
            device_name=_reference_name(payload.device) or "",
            type=payload.type,
            enabled=payload.enabled,
            mac_address=payload.mac_address,
            description=payload.description,
        )

    def ip_address(self, payload: NetBoxIPAddress) -> IPAddress:
        """Map a NetBox IP address payload."""

        return IPAddress(
            address=payload.address,
            family=payload.family,
            status=payload.status.value if payload.status is not None else None,
            dns_name=payload.dns_name,
            assigned_object_type=payload.assigned_object_type,
            assigned_object_name=_reference_name(payload.assigned_object),
            device_name=_reference_name(payload.assigned_object),
        )

    def vlan(self, payload: NetBoxVLAN) -> VLAN:
        """Map a NetBox VLAN payload."""

        return VLAN(
            vid=payload.vid,
            name=payload.name,
            site_name=_reference_name(payload.site),
            status=payload.status.value if payload.status is not None else None,
            role=_reference_name(payload.role),
        )

    def device(self, payload: NetBoxDevice) -> Device:
        """Map a NetBox device payload."""

        manufacturer = payload.device_type.manufacturer
        if manufacturer is None:
            manufacturer_name = payload.device_type.model
            manufacturer_slug = payload.device_type.slug or payload.device_type.model
        else:
            manufacturer_name = (
                manufacturer.name or manufacturer.display or payload.device_type.model
            )
            manufacturer_slug = (
                manufacturer.slug
                or manufacturer.name
                or manufacturer.display
                or payload.device_type.model
            )
        device_type = DeviceType(
            manufacturer=Manufacturer(
                name=manufacturer_name,
                slug=manufacturer_slug,
            ),
            model=payload.device_type.model,
            slug=payload.device_type.slug or payload.device_type.model,
        )
        return Device(
            name=payload.name,
            site_name=_reference_name(payload.site),
            rack_name=_reference_name(payload.rack),
            device_type=device_type,
            role=(
                Role(
                    name=_reference_name(payload.role) or "",
                    slug=payload.role.slug or _reference_name(payload.role) or "",
                )
                if payload.role is not None
                else None
            ),
            platform=(
                Platform(
                    name=(
                        payload.platform.name or _reference_name(payload.platform) or ""
                    ),
                    slug=(
                        payload.platform.slug or _reference_name(payload.platform) or ""
                    ),
                )
                if payload.platform is not None
                else None
            ),
            serial=payload.serial,
            status=payload.status.value if payload.status is not None else None,
            primary_ip=(
                payload.primary_ip4.address
                if payload.primary_ip4 is not None
                else (
                    payload.primary_ip6.address
                    if payload.primary_ip6 is not None
                    else None
                )
            ),
        )
