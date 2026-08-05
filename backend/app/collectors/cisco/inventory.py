"""Cisco inventory parser implementations."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass

from backend.app.parsers.base import BaseParser
from backend.app.parsers.context import ParserContext, ParserInputFormat
from backend.app.parsers.exceptions import ParserValidationError
from backend.app.parsers.result import ParsedRecord, ParserResult

_VERSION_RE = re.compile(
    r"Cisco IOS(?: XE)? Software.*?Version (?P<version>[\w().-]+)",
    re.IGNORECASE | re.DOTALL,
)
_HOSTNAME_UPTIME_RE = re.compile(
    r"(?P<hostname>\S+)\s+uptime is\s+(?P<uptime>.+)",
    re.IGNORECASE,
)
_MODEL_RE = re.compile(r"[Mm]odel number\s*:\s*(?P<model>\S+)")
_BASE_MAC_RE = re.compile(r"[Bb]ase [Ee]thernet MAC [Aa]ddress\s*:\s*(?P<mac>\S+)")
_SYSTEM_SERIAL_RE = re.compile(r"[Ss]ystem [Ss]erial [Nn]umber\s*:\s*(?P<serial>\S+)")
_HARDWARE_RE = re.compile(r"[Hh]ardware\s*:\s*(?P<hardware>.+)")
_INVENTORY_RE = re.compile(
    r'NAME:\s*"(?P<name>[^"]+)".*?'
    r"PID:\s*(?P<pid>[^,\s]+)\s*,\s*"
    r"VID:\s*(?P<vid>[^,\s]*)\s*,\s*"
    r"SN:\s*(?P<serial>\S+)",
    re.IGNORECASE | re.DOTALL,
)
_POWER_RE = re.compile(
    r"Available:(?P<available>[\d.]+)\(w\).*?Used:(?P<used>[\d.]+)\(w\)",
    re.IGNORECASE | re.DOTALL,
)


@dataclass(slots=True)
class CiscoInventoryParser(BaseParser):
    """Parse Cisco inventory payloads into structured parser records."""

    name: str = "cisco-inventory-parser"
    supported_formats: frozenset[ParserInputFormat] = frozenset(
        {ParserInputFormat.JSON}
    )

    def parse(self, context: ParserContext, raw_output: object) -> ParserResult:
        """Parse raw Cisco collector payload into structured records."""

        if not isinstance(raw_output, Mapping):
            raise ParserValidationError("Cisco inventory payload must be a mapping.")

        target = self._mapping(raw_output.get("target"))
        commands = self._string_mapping(raw_output.get("commands"))
        http_payloads = self._string_mapping(raw_output.get("http"))
        snmp_payloads = self._snmp_mapping(raw_output.get("snmp"))
        device_id = self._text(target.get("identifier")) or context.source
        management_ip = self._text(target.get("address"))
        metadata = self._mapping(target.get("metadata"))

        device_payload = self._device_payload(
            device_id=device_id,
            management_ip=management_ip,
            metadata=metadata,
            raw_output=raw_output,
            commands=commands,
            http_payloads=http_payloads,
            snmp_payloads=snmp_payloads,
        )
        records: list[ParsedRecord] = [
            ParsedRecord(kind="device", payload=device_payload)
        ]
        records.extend(self._interface_records(device_id, commands, snmp_payloads))
        records.extend(self._vlan_records(device_id, commands, snmp_payloads))
        records.extend(self._neighbor_records(device_id, commands))
        power = self._power_record(device_id, commands, snmp_payloads)
        if power is not None:
            records.append(power)

        return ParserResult(
            parser_name=self.name,
            source=context.source,
            input_format=context.input_format,
            records=tuple(records),
            metadata={"platform_family": raw_output.get("platform_family", "")},
        )

    def _device_payload(
        self,
        *,
        device_id: str,
        management_ip: str | None,
        metadata: Mapping[str, object],
        raw_output: Mapping[str, object],
        commands: Mapping[str, str],
        http_payloads: Mapping[str, str],
        snmp_payloads: Mapping[str, tuple[tuple[str, str], ...]],
    ) -> dict[str, object]:
        show_version = commands.get("show version", "")
        show_inventory = commands.get("show inventory", "")
        http_text = "\n".join(http_payloads.values())
        system_snmp = self._flatten_snmp(snmp_payloads.get("system", ()))

        inventory_match = _INVENTORY_RE.search(show_inventory)
        hostname_match = _HOSTNAME_UPTIME_RE.search(show_version)
        model_match = _MODEL_RE.search(show_version)
        version_match = _VERSION_RE.search(show_version)
        base_mac_match = _BASE_MAC_RE.search(show_version)
        serial_match = _SYSTEM_SERIAL_RE.search(show_version)
        hardware_match = _HARDWARE_RE.search(show_version)

        hostname = (
            self._text(metadata.get("hostname"))
            or self._group(hostname_match, "hostname")
            or self._snmp_value(system_snmp, "sysName")
            or device_id
        )
        product_id = (
            self._text(metadata.get("product_id"))
            or self._group(inventory_match, "pid")
            or self._http_value(http_text, "product id")
        )
        model = (
            self._text(metadata.get("model"))
            or self._group(model_match, "model")
            or product_id
            or self._http_value(http_text, "model")
        )
        serial_number = (
            self._text(metadata.get("serial_number"))
            or self._group(serial_match, "serial")
            or self._group(inventory_match, "serial")
            or self._http_value(http_text, "serial")
        )
        software_version = (
            self._group(version_match, "version")
            or self._http_value(http_text, "version")
            or self._snmp_value(system_snmp, "sysDescr")
        )

        return {
            "device_id": device_id,
            "name": hostname,
            "manufacturer": "Cisco",
            "model": model,
            "serial_number": serial_number,
            "product_id": product_id,
            "management_ip": management_ip,
            "base_mac": self._group(base_mac_match, "mac")
            or self._http_value(http_text, "base mac"),
            "software_version": software_version,
            "uptime": self._group(hostname_match, "uptime")
            or self._snmp_value(system_snmp, "sysUpTime"),
            "hardware_revision": self._group(inventory_match, "vid")
            or self._group(hardware_match, "hardware"),
            "platform": raw_output.get(
                "parser_family",
                raw_output.get("platform_family"),
            ),
            "stack_members": self._stack_members(show_version),
        }

    def _interface_records(
        self,
        device_id: str,
        commands: Mapping[str, str],
        snmp_payloads: Mapping[str, tuple[tuple[str, str], ...]],
    ) -> list[ParsedRecord]:
        records = self._parse_interface_status(
            device_id,
            commands.get("show interfaces status", ""),
        )
        if records:
            return records

        snmp_rows = snmp_payloads.get("interfaces", ())
        return [
            ParsedRecord(
                kind="interface",
                payload={
                    "device_id": device_id,
                    "name": oid.rsplit(".", 1)[-1],
                    "description": value,
                },
            )
            for oid, value in snmp_rows[:128]
            if value.strip()
        ]

    def _parse_interface_status(
        self,
        device_id: str,
        output: str,
    ) -> list[ParsedRecord]:
        records: list[ParsedRecord] = []
        for line in output.splitlines():
            line = line.rstrip()
            if not line or line.lower().startswith(("port ", "---")):
                continue
            parts = line.split()
            if len(parts) < 4:
                continue
            name = parts[0]
            status_index = self._first_index(
                parts,
                {"connected", "notconnect", "disabled", "err-disabled", "inactive"},
            )
            if status_index is None:
                continue
            description = " ".join(parts[1:status_index]) or None
            records.append(
                ParsedRecord(
                    kind="interface",
                    payload={
                        "device_id": device_id,
                        "name": name,
                        "description": description,
                        "oper_status": parts[status_index],
                        "admin_status": (
                            "up" if parts[status_index] == "connected" else "down"
                        ),
                        "speed_mbps": (
                            self._speed_to_mbps(parts[-2]) if len(parts) >= 2 else None
                        ),
                    },
                )
            )
        return records

    def _vlan_records(
        self,
        device_id: str,
        commands: Mapping[str, str],
        snmp_payloads: Mapping[str, tuple[tuple[str, str], ...]],
    ) -> list[ParsedRecord]:
        output = commands.get("show vlan brief", "")
        records: list[ParsedRecord] = []
        for line in output.splitlines():
            parts = line.split()
            if len(parts) < 3 or not parts[0].isdigit():
                continue
            records.append(
                ParsedRecord(
                    kind="vlan",
                    payload={
                        "device_id": device_id,
                        "vlan_id": int(parts[0]),
                        "name": parts[1],
                        "status": parts[2],
                    },
                )
            )
        if records:
            return records

        return [
            ParsedRecord(
                kind="vlan",
                payload={
                    "device_id": device_id,
                    "vlan_id": index + 1,
                    "name": value,
                },
            )
            for index, (_, value) in enumerate(snmp_payloads.get("vlans", ()))
            if value.strip()
        ]

    def _neighbor_records(
        self,
        device_id: str,
        commands: Mapping[str, str],
    ) -> list[ParsedRecord]:
        records: list[ParsedRecord] = []
        records.extend(
            self._parse_neighbor_detail(
                device_id,
                commands.get("show cdp neighbors detail", ""),
                protocol="CDP",
            )
        )
        records.extend(
            self._parse_neighbor_detail(
                device_id,
                commands.get("show lldp neighbors detail", ""),
                protocol="LLDP",
            )
        )
        return records

    def _parse_neighbor_detail(
        self,
        device_id: str,
        output: str,
        *,
        protocol: str,
    ) -> list[ParsedRecord]:
        records: list[ParsedRecord] = []
        current: dict[str, str] = {}
        for line in output.splitlines() + [""]:
            stripped = line.strip()
            if not stripped:
                if current.get("remote_device_id") and current.get("local_interface"):
                    records.append(
                        ParsedRecord(
                            kind="neighbor",
                            payload={
                                "local_device_id": device_id,
                                "local_interface": current["local_interface"],
                                "remote_device_id": current["remote_device_id"],
                                "remote_interface": current.get("remote_interface"),
                                "protocol": protocol,
                            },
                        )
                    )
                current = {}
                continue
            lower = stripped.lower()
            if lower.startswith(("device id:", "system name:")):
                current["remote_device_id"] = stripped.split(":", 1)[1].strip()
            elif lower.startswith("interface:"):
                current["local_interface"] = (
                    stripped.split(":", 1)[1].split(",", 1)[0].strip()
                )
            elif lower.startswith(("port id", "port description")):
                current["remote_interface"] = stripped.split(":", 1)[1].strip()
        return records

    def _power_record(
        self,
        device_id: str,
        commands: Mapping[str, str],
        snmp_payloads: Mapping[str, tuple[tuple[str, str], ...]],
    ) -> ParsedRecord | None:
        output = commands.get("show power inline", "")
        if output:
            match = _POWER_RE.search(output)
            output_lower = output.lower()
            poe_enabled = "off" not in output_lower and "disabled" not in output_lower
            return ParsedRecord(
                kind="power",
                payload={
                    "device_id": device_id,
                    "source": "poe",
                    "status": "available" if poe_enabled else "disabled",
                    "available_watts": self._group(match, "available"),
                    "consumed_watts": self._group(match, "used"),
                    "poe_enabled": poe_enabled,
                },
            )
        if snmp_payloads.get("poe"):
            return ParsedRecord(
                kind="power",
                payload={
                    "device_id": device_id,
                    "source": "poe",
                    "status": "observed",
                    "poe_enabled": True,
                },
            )
        return None

    @staticmethod
    def _mapping(value: object) -> Mapping[str, object]:
        return value if isinstance(value, Mapping) else {}

    @staticmethod
    def _string_mapping(value: object) -> Mapping[str, str]:
        if not isinstance(value, Mapping):
            return {}
        return {str(key): str(item) for key, item in value.items()}

    @staticmethod
    def _snmp_mapping(value: object) -> Mapping[str, tuple[tuple[str, str], ...]]:
        if not isinstance(value, Mapping):
            return {}
        mapped: dict[str, tuple[tuple[str, str], ...]] = {}
        for key, rows in value.items():
            if not isinstance(rows, list | tuple):
                continue
            mapped[str(key)] = tuple(
                (str(row[0]), str(row[1]))
                for row in rows
                if isinstance(row, list | tuple) and len(row) == 2
            )
        return mapped

    @staticmethod
    def _flatten_snmp(rows: tuple[tuple[str, str], ...]) -> str:
        return "\n".join(f"{oid}={value}" for oid, value in rows)

    @staticmethod
    def _snmp_value(text: str, token: str) -> str | None:
        if token.lower() not in text.lower():
            return None
        for line in text.splitlines():
            if token.lower() in line.lower():
                return line.split("=", 1)[-1].strip()
        return None

    @staticmethod
    def _http_value(text: str, label: str) -> str | None:
        pattern = re.compile(rf"{re.escape(label)}\s*[:=]\s*(?P<value>[^\n\r<]+)", re.I)
        match = pattern.search(text)
        if match is None:
            return None
        return match.group("value").strip()

    @staticmethod
    def _group(match: re.Match[str] | None, group: str) -> str | None:
        if match is None:
            return None
        value = match.group(group).strip()
        return value if value else None

    @staticmethod
    def _text(value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text if text else None

    @staticmethod
    def _stack_members(output: str) -> tuple[str, ...]:
        members = [
            line.strip()
            for line in output.splitlines()
            if line.strip().startswith("*") and "switch" in line.lower()
        ]
        return tuple(members)

    @staticmethod
    def _first_index(parts: list[str], candidates: set[str]) -> int | None:
        for index, part in enumerate(parts):
            if part.lower() in candidates:
                return index
        return None

    @staticmethod
    def _speed_to_mbps(value: str) -> int | None:
        normalized = value.strip().lower()
        if normalized in {"auto", "a-100", "100"}:
            return 100
        if normalized in {"a-1000", "1000", "1g"}:
            return 1000
        if normalized.endswith("g") and normalized[:-1].isdigit():
            return int(normalized[:-1]) * 1000
        if normalized.isdigit():
            return int(normalized)
        return None
