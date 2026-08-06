# REST API

The REST API exposes the existing job framework, orchestration engine, and immutable history repositories through a thin service layer.

## Design principles

- Reuse the existing job framework and orchestration engine for business execution.
- Keep the API layer thin by translating HTTP requests into existing domain objects.
- Return typed response models and standardised error payloads.
- Support pagination and filtering for list endpoints.

## Routes

- POST /api/v1/jobs/discovery
- GET /api/v1/jobs/{id}
- DELETE /api/v1/jobs/{id}
- GET /api/v1/jobs
- GET /api/v1/history/discovery-runs
- GET /api/v1/findings
- GET /api/v1/findings/{id}
- GET /api/v1/devices/{id}/history
- GET /api/v1/comparison/{run_id}
- GET /api/v1/compliance/{run_id}
- GET /api/v1/health
- GET /api/v1/metrics
- GET /api/v1/version

## Payloads

- `POST /api/v1/jobs/discovery` accepts a `DiscoveryJobRequest` payload with collector contexts, optional policies, metadata, priority, and timeout.
- Responses are typed with Pydantic models such as `JobSubmissionResponse`, `JobStatusResponse`, `JobListResponse`, `DiscoveryRunListResponse`, `FindingsListResponse`, `FindingResponse`, `DeviceHistoryResponse`, `ComparisonResultResponse`, and `ComplianceSummaryResponse`.

## API documentation

- Interactive OpenAPI UI: `/docs`
- ReDoc: `/redoc`
- Raw OpenAPI schema: `/openapi.json`
