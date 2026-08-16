# Changelog

All notable changes to the APIForge project will be documented in this file.

## [0.11.0] - 2026-08-16
### Added
- **Pytest Testing Pyramid**: Added Pytest config file `pytest.ini` with custom markers (unit, integration, security, e2e) and auto-asyncio test settings.
- **Deterministic Unit Tests**: Added `tests/test_phase11_unit.py` testing RBAC permission matrices, recursive credentials/secret redaction mappings, URL query parsing, and search pagination calculations.
- **Asynchronous Integration Tests**: Added `tests/test_phase11_integration.py` validating tenant separation rules, non-disclosure of Bearer/Basic Auth tokens in request responses, audit log entries, and health/readiness contracts.
- **Autouse Connection Teardowns**: Integrated autouse hooks in `conftest.py` ensuring database engine connection pools are cleanly closed on test exit to avoid event loop/asyncpg failures on Windows.
- **Playwright E2E Smoke Tests**: Added `playwright.config.ts` and `e2e/smoke.spec.ts` script logging in users via Chrome and asserting topbar controls, Docs/Audit panels, and search input layouts.

## [0.10.0] - 2026-08-15
### Added
- **Security Audit Logs**: Added persistent HTTP mutation activity log table `audit_logs` tracking user, action, method, path, status, IP, and correlation request ID. Exposes `GET /api/v1/workspaces/{workspace_id}/audit-logs` endpoint (restricted to OWNER/ADMIN).
- **Distributed Rate Limiting**: Added Redis-backed sliding/fixed-window rate limiter middleware with configurable endpoints (login: 10/min, registration: 5/min, refresh: 20/min, execution: 30/min, general: 300/min).
- **Security Headers & Hardening**: Injected secure response headers (`X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, HSTS in production, and custom `X-Request-ID` correlation context headers).
- **Production Startup Safety Checks**: Refuses app execution in production mode if default secrets (JWT_SECRET_KEY), insecure cookies, or missing environment encryption keys are detected.
- **Centralized Secret Redaction**: Added mapping, URL query, header, and body text sanitizers protecting sensitive keys, credential headers, and query strings. Sanitizes request execution history before database persistence.
- **Aesthetic Audit UI Panel**: Integrated responsive React collapsible Security Audit Log modal in the top header, rendering list logs with custom status badges.

## [0.9.0] - 2026-08-14
### Added
- **API Auto-Documentation**: Added OpenAPI 3.0.3 generator endpoint `GET /api/v1/workspaces/{workspace_id}/documentation/openapi.json` to dynamically build full-specification documentation from request definitions.
- **Documentation Summary**: Added summary metadata endpoint `GET /api/v1/workspaces/{workspace_id}/documentation/summary` listing workspace API statistics.
- **OpenAPI Import**: Added `/api/v1/workspaces/{workspace_id}/documentation/import` endpoint accepting OpenAPI 3.0.x and 3.1.x json specifications, auto-creating collection, folders, and request definitions.
- **Aesthetic Docs UI Panel**: Integrated responsive React collapsible Documentation panel in the top header, allowing users to view summary statistics, download the OpenAPI specification file, or upload an OpenAPI spec to import.
- **Credential Protection**: Ensured secrets and sensitive credential headers (Authorization, Cookie, etc.) are redacted from generated documentation, and basic/bearer schemes are imported without token payloads.

## [0.8.0] - 2026-08-13
### Added
- **Authenticated WebSockets**: Added `/api/v1/workspaces/{workspace_id}/collaboration` WebSocket router, performing JWT authentication as the first message payload.
- **Request-Level Presence**: Tracks active request editors connections, saving presence state (connection ID, user ID, name, request ID, last-seen) in Redis with a 30-second TTL.
- **Heartbeat presence**: Frontend clients send heartbeats every 10 seconds to keep connection presence alive.
- **Pub/Sub event fan-out**: REST mutations publish lightweight collection/folder and request updates (`COLLECTION_UPDATED`, `REQUEST_UPDATED`) to workspace collaboration channels in Redis. Other active clients receive the notification and trigger REST re-fetching.
- **Aesthetic presence UI**: Displays active request editors in the request editor top pane presence bar with connection status.

## [0.7.0] - 2026-08-13
### Added
- **Global Workspace Search**: Added `GET /api/v1/workspaces/{workspace_id}/search` combining Collections, Folders, and APIRequests with ILIKE query matching.
- **Database-Level Pagination**: Exposed paginated resource listings for Collections and APIRequests with offsets and metadata.
- **Workspace Bounds Enforcement**: Ensured search queries restrict returns exclusively to resources within the searched workspace.
- **Frontend Topbar Search**: Added interactive search inputs and dropdown menus matching the dark mode layout.

## [0.6.0] - 2026-08-13
### Added
- **Request Execution Engine**: Added controlled outbound HTTP request execution for persisted API request definitions.
- **SSRF and Network Protections**: Blocked outbound requests resolving to local, loopback, private, link-local, or reserved IP ranges.
- **Secure Redirect Controls**: Implemented check-on-redirect validations restricting redirect destinations to public domains.
- **Response Processing and Redaction**: Bounded upstream response payload sizes to prevent Denial of Service, and redacted sensitive headers (`Authorization`, `Cookie`, `x-api-key`, etc.) from execution logs.
- **Execution History Records**: Added persistent logging of request execution timing, status codes, response sizes, and success results.
- **Frontend Response Panel**: Added a sidebar response visualizer showing HTTP status, execution time, body output, and redacted headers.

## [0.5.0] - 2026-08-13
### Added
- **Workspace Environments**: Introduced workspace-scoped environments (like Development, Production) to separate configurations.
- **Variable Encryption at Rest**: Used Fernet symmetric encryption key for variables designated as secrets, persisting only ciphertext in PostgreSQL.
- **Variable Substitution & Resolution**: Supported placeholder format `{{VARIABLE_NAME}}` to resolve strings, masking secrets with asterisks (`********`) for normal view.
- **Tenant Isolation and RBAC**: Enforced role authorization checks on environment management and cross-workspace access attempts.
- **Alembic Database Migration**: Added migration `0005_environments` setting up tables with cascade deletions.
- **Frontend Environment UI**: Integrated dropdown environment selectors and variable additions within the workspace grid.

## [0.4.0] - 2026-08-12
### Added
- **Collections CRUD**: Introduced collections inside workspaces with positional sorting.
- **Nested Folders**: Added hierarchical folder trees with protection against circular parents and invalid multi-tenant collection assignments.
- **API Request Definitions**: Implemented persistent REST definitions storing headers, query params, request bodies, and auth configurations.
- **Hierarchical Authorization Validation**: Enforced that access checks traverse up to the collection's owning workspace and check the active member's role capabilities.
- **Initial Request-Builder UI**: Designed a comprehensive React sidebar panel showing workspaces, collections, folders, and request listings with an interactive definition editor.
- **Alembic Database Migration**: Created sequential schema migration `0004_collections_requests` establishing primary database tables and foreign keys.

## [0.3.1] - 2026-08-12
### Added
- **Workspace Member Invitations**: Introduced secure, email-scoped workspace invitation flows.
- **Secure Token Hashing**: Added cryptographic generation of random token IDs, persisting only their SHA-256 hashes.
- **Invitations API Routing**: Exposed creation (`POST /api/v1/workspaces/{id}/invitations`) and acceptance (`POST /api/v1/invitations/{token}/accept`) endpoints.
- **Invitation Validation Constraints**: Rejected duplicate memberships, duplicate pending invitations, and assignments to the `OWNER` role.
- **Security Check rules**: Enforced that the logged-in email of the accepting user must exactly match the invitation email (returns 403 on mismatch).
- **Alembic Migration**: Created DB migration `0003_invitations` to set up the `invitations` table with foreign key constraints.
- **Mocks Test Suite**: Wrote mock unit tests in `backend/tests/test_invitations.py` verifying E2E Happy/Unhappy path security boundaries.

## [0.3.0] - 2026-08-12
### Added
- **Multi-Tenant Workspaces**: Implemented workspaces uniquely identified by UUID and custom URL-friendly slug.
- **Membership Management**: Added workspace membership and user assignment.
- **Centralized RBAC permissions**: Defined roles (`OWNER`, `ADMIN`, `EDITOR`, `VIEWER`) and permission mappings in `app/core/permissions.py`.
- **Tenant-Isolation Guards**: Added backend dependencies to verify resource access and membership. Attempts to access non-member workspaces return a `404 Not Found` response.
- **Workspace API Routing**: Mounted workspace and member management endpoints under `/api/v1/workspaces`.
- **Alembic DB Migrations**: Created database migration `0002_workspaces` for workspace-related tables.
- **Permission Unit Tests**: Added unit tests checking the role permission matrix.

---

## [0.2.0] - 2026-08-11
### Added
- **User Authentication**: Registered accounts hashed using `Argon2` password hash function.
- **JWT Authorization**: Created rotating short-lived JWT access tokens and long-lived secure HttpOnly refresh token cookies.
- **Token Rotation & Revocation**: Handled active session rotation, reuse detection, and session logout revocation.
- **Alembic DB Migrations**: Created database migration `0001_auth` for `users` and `refresh_tokens`.
- **Minimal Frontend UI**: React application demonstrating user registration, login, profile view, and logout.

---

## [0.1.0] - 2026-08-10
### Added
- **Infrastructure Setup**: Configured multi-container development environment via Docker Compose (PostgreSQL, Redis, FastAPI, React + TS + Vite, Adminer).
- **Process Health checks**: Added `/api/v1/health` and `/api/v1/ready` endpoints with status checkers for PostgreSQL and Redis connection statuses.
- **Structured JSON logging**: Configured application-wide logging framework.
