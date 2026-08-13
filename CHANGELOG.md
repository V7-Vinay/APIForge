# Changelog

All notable changes to the APIForge project will be documented in this file.

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
