# Frontend foundation

## Architecture

The frontend is a React + TypeScript + Vite application that consumes the existing FastAPI backend through a typed API client. The dashboard experience is implemented as a route-level view that uses the centralized API layer and reusable dashboard components.

## Directory structure

- src/api: centralized HTTP client and typed dashboard API helpers
- src/components: shared UI components and dashboard-specific cards/sections
- src/lib: authentication context and protected-route handling
- src/pages: route-level views, including the operations dashboard
- src/routes: route metadata
- src/services: application service wrappers
- src/types: shared request/response contracts
- src/styles: styling entry points

## Operations Dashboard

### API dependencies

The dashboard consumes the following backend endpoints:

- GET /api/v1/dashboard/kpis
- GET /api/v1/dashboard/trends

### Response mapping

- KPI cards map from the dashboard KPI summary contract fields such as total_devices, discovery_success_pct, findings_total, and reachable_devices.
- Trend cards map from the dashboard trends envelope using discovery_success_trend, device_count_trend, findings_count_trend, and drift_trend.
- Platform status uses latest_run_id, latest_run_started_at, and latest_run_finished_at from the KPI response, while the frontend status section remains clearly separated from platform operational data.

### State handling

The dashboard distinguishes between loading, ready, empty, and error states. Empty responses render a deliberate empty state rather than a fake chart. API failures render an inline error state with a retry action.

### Testing strategy

Frontend tests cover KPI loading, KPI success, KPI empty state, KPI API failure, trend loading, trend success, trend empty state, trend API failure, dashboard composition, retry behavior, navigation links, and authenticated access.

## Authentication

Authentication uses the backend /auth/login and /auth/me endpoints via a bearer token stored in browser local storage.

## Environment variables

- VITE_API_BASE_URL: API base URL for the FastAPI backend.

## Development

- npm install
- npm run dev
- npm run build
- npm run test
