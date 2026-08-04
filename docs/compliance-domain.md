# Compliance Domain Model

The compliance domain model represents the reusable data structures used by
future compliance evaluation and reporting components.

## Components

- `backend/app/compliance/domain/entities.py` defines the immutable entity base
  class.
- `backend/app/compliance/domain/value_objects.py` defines the immutable value
  object base class.
- `backend/app/compliance/domain/enums.py` defines shared compliance enums.
- `backend/app/compliance/rules/base.py` defines the rule entity.
- `backend/app/compliance/rules/metadata.py` defines rule metadata.
- `backend/app/compliance/rules/registry.py` provides rule registration.
- `backend/app/compliance/policies/models.py` defines policies and baselines.
- `backend/app/compliance/findings/evidence.py` defines evidence records.
- `backend/app/compliance/findings/severity.py` defines severity levels.
- `backend/app/compliance/findings/models.py` defines findings and
  recommendations.
- `backend/app/compliance/comparison/models.py` defines comparison targets and
  metrics.
- `backend/app/compliance/comparison/result.py` defines comparison results.

## Design Notes

- All models are immutable dataclasses.
- No evaluation or comparison logic is embedded in the domain objects.
- Rules, policies, findings, and evidence are all reusable and vendor-neutral.
- Comparison results carry domain state only; future engines can populate them.

