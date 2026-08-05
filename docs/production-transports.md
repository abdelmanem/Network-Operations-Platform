# Production Transport Adapters

Milestone 10 introduces the concrete, vendor-neutral transport adapters that sit
on top of the reusable transport framework.

## Scope

- HTTP transport via `httpx`
- SSH transport via `Netmiko` with `Paramiko` fallback
- SNMP transport via `pysnmp` or `pysnmp-lextudio`
- shared retry, circuit breaker, timeout, and rate limiting support
- typed metrics and diagnostics models for connection troubleshooting

The adapters are designed for connection establishment, session reuse, and
generic protocol interaction. They do not implement Cisco commands, collectors,
inventory logic, or compliance evaluation.

## Installation

Install the production transport libraries alongside the project dependencies:

```bash
pip install httpx netmiko paramiko pysnmp-lextudio
```

If you prefer the upstream pysnmp package, you may substitute `pysnmp` for
`pysnmp-lextudio`.

## Integration Testing

Live transport checks are disabled by default. To enable the optional scaffold:

```bash
set NOP_TRANSPORT_INTEGRATION=1
```

or on Linux:

```bash
export NOP_TRANSPORT_INTEGRATION=1
```

The repository includes a skipped integration scaffold in
`tests/integration/test_production_transports.py` that can be expanded when
real device credentials and lab targets are available.
