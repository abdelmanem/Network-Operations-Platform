# Compliance Evaluation Engine

Milestone 14 introduces policy evaluation on top of comparison differences. The
engine transforms inventory drift into immutable compliance decisions with risk,
severity, evidence, and remediation guidance.

## Inputs

- `InventoryComparisonResult`
- `Difference` records
- compliance `Policy` objects
- compliance `Rule` objects
- temporary exceptions and approved waivers

## Outputs

- `EvaluationDecision`
- per-rule `RuleEvaluationResult` records
- risk score
- compliance score
- severity
- compliance status
- recommendations
- evidence
- evaluation metrics

## Supported Rule Types

- `equals`
- `not_equals`
- `exists`
- `missing`
- `regex`
- `contains`
- `greater_than`
- `less_than`
- `version_compare`
- `boolean_compare`

## Policy Scoping

Policy and rule tags can scope evaluation by:

- `site:<name>`
- `role:<device-role>`
- `platform:<platform>`

Only enabled policies with matching tags contribute rules. Duplicate rule keys
are evaluated once per policy evaluation.

## Exceptions and Waivers

`EvaluationException` supports:

- subject-specific waivers
- rule-specific waivers
- temporary exceptions with expiration
- approved waiver metadata

Expired exceptions do not apply.

## Scoring

Rules can define an explicit `risk_score` in `expected_state`. If omitted, risk
is derived from the comparison difference type. Compliance score is calculated as
`100 - average risk`, clamped to `0..100`.

## Out of Scope

- REST API
- Web UI
- Reports
- Scheduling
- Notifications

## Testing

Tests cover rule execution, policy scoping, exception handling, risk scoring,
registry behavior, and a golden policy fixture.
