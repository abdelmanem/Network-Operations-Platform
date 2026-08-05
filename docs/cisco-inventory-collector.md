# Cisco Inventory Collector

Milestone 11 introduces the first production Cisco inventory collectors. These
collectors use the existing runtime, transport manager, Cisco platform registry,
parser framework, normalization engine, and immutable snapshot model.

## Supported Platforms

- Cisco Catalyst 2960
- Cisco Catalyst 2960X
- Cisco Catalyst 3560
- Cisco Catalyst Express 500
- Cisco Aironet 1131

## Scope

The collectors gather inventory data only:

- hostname and management IP
- serial number, model, product ID, base MAC, hardware revision
- IOS or firmware version and uptime
- interface inventory
- VLAN inventory
- PoE status where supported
- CDP and LLDP neighbors where supported
- stack member summary when visible in command output

The collectors do not collect running configuration, startup configuration, or
configuration backup data. They also do not evaluate compliance, compare NetBox
state, modify NetBox, or generate reports.

## Architecture

The Cisco collector package lives under `backend/app/collectors/cisco`.

Transport selection is centralized in `CiscoTransportSelector` and follows the
required priority:

1. SSH
2. SNMP
3. HTTP

The selector consults the Cisco platform registry and capability matrix before
choosing a registered transport adapter. The collector then opens or reuses the
session through `TransportManager`, so connection pooling, retries, rate
limiting, circuit breaking, and credentials remain owned by the transport layer.

## Parsing and Normalization

`CiscoInventoryParser` accepts the collector's JSON payload and emits structured
parser records:

- `device`
- `interface`
- `vlan`
- `neighbor`
- `power`

The generic normalization mapper converts those records into immutable snapshot
entities. Cisco-specific parsing stays inside the Cisco collector package; the
snapshot model remains vendor-neutral.

## Testing

Unit tests mock all transport sessions. Parser tests use text fixtures for common
Catalyst command output. Live device tests are scaffolded but disabled by default:

```bash
NOP_CISCO_INTEGRATION=1 pytest tests/integration/test_cisco_inventory_collector.py
```

## Known Limitations

- SNMP parsing is intentionally conservative until real device walks are added as
  fixtures.
- HTTP collection is limited to the existing Catalyst Express-compatible endpoint
  metadata.
- Command parsing covers common Catalyst formats and should be expanded with
  additional fixture samples during field validation.
