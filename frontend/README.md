# Frontend foundation

## Architecture

The frontend is a React + TypeScript + Vite application that consumes the existing FastAPI backend through a typed API client.

## Directory structure

- src/app: application shell and route composition
- src/api: centralized HTTP client and typed API helpers
- src/auth: authentication context and protected route handling
- src/components: shared UI components
- src/layouts: shell/layout components
- src/pages: route-level views
- src/routes: route metadata
- src/hooks: reusable hooks
- src/types: shared request/response contracts
- src/styles: styling entry points

## Authentication

Authentication uses the backend /auth/login and /auth/me endpoints via a bearer token stored in browser local storage.

## Environment variables

- VITE_API_BASE_URL: API base URL for the FastAPI backend.

## Development

- npm install
- npm run dev
- npm run build
- npm run test
