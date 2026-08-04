# Normalization Framework

The normalization framework converts structured parser records into canonical
snapshot entities used by the rest of the platform.

## Components

- `backend/app/normalization/engine.py` orchestrates validation, rule
  execution, and mapping.
- `backend/app/normalization/mapper.py` transforms parser records into
  immutable snapshot entities.
- `backend/app/normalization/registry.py` stores pluggable normalization rules.
- `backend/app/normalization/rules.py` defines the rule protocol.
- `backend/app/normalization/validator.py` validates parser output and
  normalized snapshots.

## Responsibilities

- Consume structured parser output only.
- Emit canonical snapshot models only.
- Keep rules pluggable and vendor-neutral.
- Avoid compliance, persistence, and device communication concerns.

