# OpenAPI coverage

The FastAPI application exposes OpenAPI at `/docs`, provides a ReDoc UI at `/redoc`, and exposes the raw OpenAPI schema at `/openapi.json`.

## Covered areas

- Health, version, and metrics endpoints
- Discovery job submission and lifecycle handling
- Discovery history retrieval
- Findings and device history endpoints
- Comparison and compliance result retrieval

## Notes

The API uses typed Pydantic models for request validation and response serialization, and it returns structured errors for invalid requests and missing resources.
