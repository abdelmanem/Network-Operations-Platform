# Cisco Platform Support Framework

The Cisco platform support framework defines immutable metadata for supported
Cisco device families without opening live network connections.

## Components

- `backend/app/vendors/cisco/metadata.py` defines immutable platform metadata
  and platform definitions.
- `backend/app/vendors/cisco/platforms.py` provides the platform registry and
  detection helpers.
- `backend/app/vendors/cisco/capabilities.py` defines platform capabilities and
  the capability matrix.
- `backend/app/vendors/cisco/catalog/commands.py` defines command catalogs only.
- `backend/app/vendors/cisco/catalog/snmp.py` defines SNMP OID groups only.
- `backend/app/vendors/cisco/catalog/http.py` defines HTTP endpoint metadata
  only.
- `backend/app/vendors/cisco/detection.py` defines detection signals used by
  the framework.
- `backend/app/vendors/cisco/models/*.py` provides family-specific platform
  definitions.

## Design Notes

- All platform data is immutable and framework agnostic.
- Catalogs describe metadata only and never execute commands or requests.
- Detection is signal-based and can be used by future discovery components.
- Capability advertisement is declarative and keyed by platform family.

