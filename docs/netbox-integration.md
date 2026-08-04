# NetBox Integration

Milestone 3 establishes the source-of-truth boundary between Network Operations
Platform and NetBox Community v4.6.7.

## Goals

- Treat NetBox as the only source of truth.
- Keep the integration read-only.
- Normalize NetBox REST payloads into canonical inventory models.
- Cache NetBox responses without making Redis mandatory.
- Keep collectors, compliance, and reporting out of this layer.

## Layering

1. `backend/app/integrations/netbox/client.py`
2. `backend/app/integrations/netbox/service.py`
3. `backend/app/inventory/mapper.py`
4. `backend/app/services/inventory.py`

## Data Flow

- `NetBoxClient` handles auth, retries, pagination, rate limits, and error translation.
- `NetBoxService` fetches validated NetBox payload collections.
- `InventoryMapper` converts NetBox payloads into immutable canonical entities.
- `InventoryService` caches and returns canonical inventory snapshots.

## Validation Rules

- Missing required fields raise validation errors.
- Unexpected collection shapes raise validation errors.
- Invalid payload types raise validation errors.
- Version mismatches raise a dedicated integration error.

## Notes

- The integration is read-only.
- The framework does not persist inventory to PostgreSQL yet.
- Redis is optional; a memory fallback keeps the application operational if Redis is unavailable.

