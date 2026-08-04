# Parser Framework

The parser framework converts raw transport output into structured intermediate
records without performing any vendor-specific logic.

## Components

- `backend/app/parsers/base.py` defines the abstract parser contract.
- `backend/app/parsers/context.py` carries source metadata and input format.
- `backend/app/parsers/result.py` stores structured parser output.
- `backend/app/parsers/registry.py` resolves parser implementations by name or
  supported input format.
- `backend/app/parsers/pipeline.py` coordinates parser selection and execution.
- `backend/app/parsers/exceptions.py` provides a typed exception hierarchy.

## Responsibilities

- Accept raw text, JSON, XML, or key/value payloads.
- Produce structured records for downstream normalization.
- Stay transport-independent and framework-agnostic.
- Avoid business rules and persistence concerns.

