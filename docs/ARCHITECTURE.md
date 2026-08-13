# APIForge — System Architecture & Roadmap

This document outlines the system architecture, features, and implementation roadmap for APIForge, a collaborative API development platform.

---

## 1. System Architecture

APIForge is built as a production-ready, full-stack application leveraging modern, asynchronous technology stacks:

```text
       React / TypeScript / Vite (Frontend)
                       │
                       │ HTTP / REST
                       ▼
               FastAPI (Backend)
                 /          \
                /            \
               ▼              ▼
         PostgreSQL         Redis
        (Relational DB)   (Readiness Check)
```

- **Frontend**: Single Page Application (SPA) built using React, TypeScript, and Vite. All API requests are proxied internally through the Vite dev server to avoid CORS issues during local development.
- **Backend**: Asynchronous FastAPI service running on Uvicorn. Emits structured JSON logs for auditability.
- **PostgreSQL**: Serves as the primary database storing users, credential hashes, workspace resources, environment variables (encrypted at rest), and token families. Database schemas are managed using Alembic migrations.
- **Redis**: Serves strictly as a dependency checklist service verified for system readiness at `/api/v1/ready`. It does not store refresh token states or enforce rate limiting in this phase.

---

## 2. Completed Scope (Phases 1-8)

The project currently contains core infrastructure, security layers, multi-tenant workspace management, API request resources, environments, request execution, global search, and real-time collaboration:

### Phase 1 — Infrastructure
- **Docker Integration**: Multi-container setup with Postgres, Redis, backend (FastAPI), frontend (React) services, and Adminer DB viewer.
- **Connectivity & Monitoring**: Built-in health check and dependency readiness verification endpoints:
  - `/api/v1/health` checks backend process health.
  - `/api/v1/ready` checks relational database (Postgres) and caching layer (Redis) readiness.
- **Configuration**: Managed via environment variables (.env files) read dynamically by Pydantic settings.

### Phase 2 — Authentication & Identity
- **User Registration**: Users can register with unique email addresses, hashed in the database using the **Argon2** password hashing function.
- **JWT Authorization**:
  - Short-lived JSON Web Tokens (JWT) are used as access tokens. They expire in 30 minutes and are transmitted via the `Authorization: Bearer <token>` header.
  - **HttpOnly Refresh Cookies**: Long-lived refresh tokens expire in 30 days and are stored in secure, HttpOnly, SameSite cookies (`apiforge_refresh_token`) to mitigate XSS and CSRF risks.
- **Token Rotation & Revocation**:
  - Every refresh token usage rotates the token pair and checks for token reuse (revoking the entire token family if theft is detected).
  - Explicit logout revokes the current refresh token from Postgres and clears cookies.
- **Database Migrations**: Automatic table generation (`users` and `refresh_tokens` tables) via Alembic during container startup.

### Phase 3 — Multi-Tenant Workspaces & RBAC
- **Workspaces & Membership**:
  - Dedicated logical boundaries for user collaboration. Workspaces are uniquely identified by a slug and a UUID.
  - Creator of the workspace is automatically designated as the `OWNER`.
- **Role-Based Access Control (RBAC)**:
  - Centralized role-to-permission mapping (`app/core/permissions.py`) with roles: `OWNER`, `ADMIN`, `EDITOR`, `VIEWER`.
  - Roles govern capabilities like member management, resource creation/editing, and read-only views.
- **Tenant Isolation**:
  - Strong backend verification resolving membership based on the authenticated user ID and workspace ID.
  - Unauthorized workspace access attempts return `404 Not Found` to prevent metadata leakage.
- **Workspace Member Invitations**:
  - Secure invitation flow allowing `OWNER` or `ADMIN` members to invite new workspace collaborators by email.
  - Generates a cryptographically random token, storing only its SHA-256 hash in the database.
  - Restricts invitations to valid collaborator roles (`ADMIN`, `EDITOR`, `VIEWER`); direct `OWNER` assignment via invitation is blocked.
  - Enforces strict email verification on acceptance: the accepting user's logged-in email must match the invitation target email exactly.
  - Guarantees transaction-backed integrity when creating workspace memberships.

### Phase 4 — Collections & API Request Definitions
- **Collections CRUD**: Hierarchical logical grouping of API requests. Creator/Editor/Admin/Owner roles can view; Admin/Owner can manage.
- **Nested Folders**: Allows directories inside collections, protecting against circular loops or cross-collection placement during re-assignment.
- **API Request Definitions**: Persistence of name, HTTP method, URL, headers, query parameters, body, and authentication config (None, Bearer, Basic).
- **Secrets Masking**: Plaintext credential secrets (tokens, passwords) are automatically masked in the API response schemas to prevent leakage, while remains available to the backend execution engine.
- **Deterministic Positioning**: Supports frontend position indexing for collections, folders, and requests reordering.
- **Tenant Isolation & RBAC checks**: Restricts resource access to users belonging to the parent workspace, enforcing strict role capabilities (VIEWERs cannot write or edit; EDITORs/ADMINs/OWNERs can mutate).
- **Initial Request-Builder UI**: SPA dashboard supporting workspace select, collection management, folder creation, request listing, and side-by-side edit panel.

### Phase 5 — Environment Management
- **Workspace Environments**: Introduced workspace-scoped environments (e.g. Development, Production) to configure workspace-wide request scopes.
- **Encrypted Variables at Rest**: Implemented secure Fernet cryptography to automatically encrypt secret values in PostgreSQL.
- **Variable Placeholders & Resolution**: Created parser targeting `{{VARIABLE_NAME}}` format to substitute variables, masking secret variables (`********`) except under a secure reveal endpoint.
- **Workspace Isolation & RBAC**: Enforced checks rejecting cross-workspace environment access. Mutation operations are restricted strictly to ADMIN+ roles (`MANAGE_ENVIRONMENTS` permission).
- **Alembic Database Migration**: Added migration version `0005_environments` setting up relational environments tables.
- **React Frontend Selector**: Connected environment and variable select/add actions to the header topbar and sidebar panels.

### Phase 6 — Request Execution Engine
- **Controlled Outbound Execution**: Added `POST /api/v1/requests/{request_id}/execute` to substitute variables and issue HTTP requests.
- **SSRF Prevention Controls**: Validates request hostnames against IP range list to reject connection attempts resolving to loopback, private, or reserved subnets.
- **Redirect Guards**: Rejects unvalidated redirect locations.
- **Response Bounds & Redaction**: Discards HTTP response payloads exceeding size limits, and sanitizes outgoing headers to redact secrets (`Authorization`, `Cookie`, etc.).
- **Execution History Logging**: Persists request runs database records. Sensitive tokens/passwords in URLs, headers, bodies, and error logs are automatically redacted before being saved in the database.

### Phase 7 — Search & Filtering
- **Cross-Resource Global Search**: Implemented `GET /api/v1/workspaces/{workspace_id}/search` utilizing SQL `UNION ALL` across collections, folders, and requests with case-insensitive `ilike` text pattern matching.
- **Database-Level Pagination**: Introduced paginated collections and requests endpoints using `OFFSET/LIMIT` alongside metadata parameters (`page`, `page_size`, `total_pages`, `has_next`, `has_previous`).
- **Workspace Bounds & RBAC**: Restricts queries to current workspace memberships, preventing cross-workspace leakage.
- **Top Bar Global Search Bar**: Integrated React-based search bar in the topbar with a list result dropdown.
- **Frontend Scopes Deferred**: The full filtering UI (resource type, collection, folder, method, pagination, sorting) is deferred and will be implemented in subsequent phases.

### Phase 8 — Real-Time Collaboration
- **Authenticated WebSockets**: Added `/api/v1/workspaces/{workspace_id}/collaboration` WebSocket router, performing JWT authentication as the first message payload.
- **Request-Level Presence**: Tracks active request editors connections, saving presence state (connection ID, user ID, name, request ID, last-seen) in Redis with a 30-second TTL.
- **Heartbeat presence**: Frontend clients send heartbeats every 10 seconds to keep connection presence alive.
- **Pub/Sub event fan-out**: REST mutations publish lightweight collection/folder and request updates (`COLLECTION_UPDATED`, `REQUEST_UPDATED`) to workspace collaboration channels in Redis. Other active clients receive the notification and trigger REST re-fetching.
- **Aesthetic presence UI**: Displays active request editors in the request editor top pane presence bar with connection status.

---

## 3. API Endpoints

### System Endpoints
| Method | Path | Description | Access |
|---|---|---|---|
| GET | `/` | API Root / Info | Public |
| GET | `/api/v1/health` | Process health check | Public |
| GET | `/api/v1/ready` | Dependency health check (PG/Redis) | Public |

### Authentication Endpoints
| Method | Path | Description | Access |
|---|---|---|---|
| POST | `/api/v1/auth/register` | Register a new user | Public |
| POST | `/api/v1/auth/login` | Authenticate credentials and return JWT & cookie | Public |
| POST | `/api/v1/auth/refresh` | Rotate JWT access token using the refresh cookie | Public |
| POST | `/api/v1/auth/logout` | Revoke token family and clear cookies | Public |
| GET | `/api/v1/auth/me` | Fetch active user information | Authenticated (JWT) |

### Workspace Endpoints
| Method | Path | Description | Access |
|---|---|---|---|
| POST | `/api/v1/workspaces` | Create a new workspace | Authenticated (JWT) |
| GET | `/api/v1/workspaces` | List active user's workspaces | Authenticated (JWT) |
| GET | `/api/v1/workspaces/{id}` | Get workspace details | Authenticated + Member (VIEWER+) |
| PATCH | `/api/v1/workspaces/{id}` | Update workspace details (name) | Authenticated + Member (ADMIN+) |
| DELETE | `/api/v1/workspaces/{id}` | Delete workspace | Authenticated + Owner |
| GET | `/api/v1/workspaces/{id}/members` | List workspace members | Authenticated + Member (VIEWER+) |
| PATCH | `/api/v1/workspaces/{id}/members/{user_id}` | Change member role | Authenticated + Member (ADMIN+) |
| DELETE | `/api/v1/workspaces/{id}/members/{user_id}` | Remove member from workspace | Authenticated + Member (ADMIN+) |

### Invitation Endpoints
| Method | Path | Description | Access |
|---|---|---|---|
| POST | `/api/v1/workspaces/{workspace_id}/invitations` | Create a workspace invitation | Authenticated + Member (ADMIN+) |
| POST | `/api/v1/invitations/{token}/accept` | Accept a workspace invitation | Authenticated (matching email) |

### Collections, Folders & Requests Endpoints
| Method | Path | Description | Access |
|---|---|---|---|
| POST | `/api/v1/workspaces/{workspace_id}/collections` | Create a collection | Authenticated + Member (ADMIN+) |
| GET | `/api/v1/workspaces/{workspace_id}/collections` | List workspace collections | Authenticated + Member (VIEWER+) |
| GET | `/api/v1/collections/{id}` | Get collection details | Authenticated + Member (VIEWER+) |
| PATCH | `/api/v1/collections/{id}` | Update collection details | Authenticated + Member (ADMIN+) |
| DELETE | `/api/v1/collections/{id}` | Delete collection | Authenticated + Member (ADMIN+) |
| PATCH | `/api/v1/collections/{id}/reorder` | Update collection position index | Authenticated + Member (ADMIN+) |
| POST | `/api/v1/collections/{id}/folders` | Create a folder in a collection | Authenticated + Member (ADMIN+) |
| GET | `/api/v1/collections/{id}/folders` | List folders in a collection | Authenticated + Member (VIEWER+) |
| GET | `/api/v1/folders/{id}` | Get folder details | Authenticated + Member (VIEWER+) |
| PATCH | `/api/v1/folders/{id}` | Update folder details (name/parent) | Authenticated + Member (ADMIN+) |
| DELETE | `/api/v1/folders/{id}` | Delete folder (children moved to root) | Authenticated + Member (ADMIN+) |
| PATCH | `/api/v1/folders/{id}/reorder` | Update folder position index | Authenticated + Member (ADMIN+) |
| POST | `/api/v1/collections/{id}/requests` | Create request definition in collection | Authenticated + Member (EDITOR+) |
| GET | `/api/v1/collections/{id}/requests` | List requests in a collection | Authenticated + Member (VIEWER+) |
| GET | `/api/v1/requests/{id}` | Get request definition details | Authenticated + Member (VIEWER+) |
| PATCH | `/api/v1/requests/{id}` | Update request details | Authenticated + Member (EDITOR+) |
| DELETE | `/api/v1/requests/{id}` | Delete request definition | Authenticated + Member (EDITOR+) |
| PATCH | `/api/v1/requests/{id}/reorder` | Update request position index | Authenticated + Member (EDITOR+) |
| POST | `/api/v1/requests/{id}/execute` | Execute request definition | Authenticated + Member (EDITOR+) |

### Environment & Variable Endpoints
| Method | Path | Description | Access |
|---|---|---|---|
| POST | `/api/v1/workspaces/{workspace_id}/environments` | Create an environment | Authenticated + Member (ADMIN+) |
| GET | `/api/v1/workspaces/{workspace_id}/environments` | List workspace environments | Authenticated + Member (VIEWER+) |
| GET | `/api/v1/environments/{environment_id}` | Get environment details | Authenticated + Member (VIEWER+) |
| PATCH | `/api/v1/environments/{environment_id}` | Update environment details | Authenticated + Member (ADMIN+) |
| DELETE | `/api/v1/environments/{environment_id}` | Delete environment | Authenticated + Member (ADMIN+) |
| POST | `/api/v1/environments/{environment_id}/variables` | Create environment variable | Authenticated + Member (ADMIN+) |
| GET | `/api/v1/environments/{environment_id}/variables` | List variables in environment | Authenticated + Member (VIEWER+) |
| GET | `/api/v1/environment-variables/{variable_id}` | Get environment variable details | Authenticated + Member (VIEWER+) |
| GET | `/api/v1/environment-variables/{variable_id}/reveal` | Reveal secret variable value | Authenticated + Member (ADMIN+) |
| PATCH | `/api/v1/environment-variables/{variable_id}` | Update environment variable | Authenticated + Member (ADMIN+) |
| DELETE | `/api/v1/environment-variables/{variable_id}` | Delete environment variable | Authenticated + Member (ADMIN+) |
| POST | `/api/v1/environments/{environment_id}/resolve` | Resolve variable placeholders in text | Authenticated + Member (VIEWER+) |

### Search & Pagination Endpoints
| Method | Path | Description | Access |
|---|---|---|---|
| GET | `/api/v1/workspaces/{workspace_id}/search` | Global workspace resource search | Authenticated + Member (VIEWER+) |
| GET | `/api/v1/workspaces/{workspace_id}/collections/page` | Paginated collections listing | Authenticated + Member (VIEWER+) |
| GET | `/api/v1/workspaces/{workspace_id}/requests/page` | Paginated requests listing | Authenticated + Member (VIEWER+) |
| GET | `/api/v1/requests/{request_id}/history` | Retrieve request execution history | Authenticated + Member (VIEWER+) |

### WebSocket Collaboration Endpoints
| Method | Path | Description | Access |
|---|---|---|---|
| WS | `/api/v1/workspaces/{workspace_id}/collaboration` | WebSocket presence and change events endpoint | Authenticated + Member (VIEWER+) |

---

## 4. Real-Time Collaboration Architecture (Phase 8)

To avoid competing mutation paths, REST remains the authoritative transport for updating resources (collections, folders, requests). WebSockets are used strictly for presence and lightweight mutation event fan-out:
- **Transport**: Standard JSON WebSockets over `/api/v1/workspaces/{workspace_id}/collaboration`.
- **Authentication**: JWT token sent in the first socket message (`{"type":"AUTH","token":"<JWT>"}`).
- **Ephemeral Presence**: Scoped to workspace and active request. Tracked in Redis using connection-level keys with a 30-second TTL. Clients heartbeat every 10 seconds.
- **Pub/Sub Fan-out**: Redis Pub/Sub channel `apiforge:collaboration:workspace:{workspace_id}` distributes resource updates (`REQUEST_UPDATED`, `COLLECTION_UPDATED`) to all connected workspace members.
- **Data Flow**: When a client receives a mutation event from Pub/Sub, it re-fetches authoritative resource data from the REST API. Event payloads only carry IDs and metadata, never credentials or sensitive variables.

---

To maintain a clean separation of concerns, the following features are **deliberately excluded** from the current implementation and are earmarked for Phase 9+:

1. **Auto-Documentation**: OpenAPI-compatible schema documentation generation from workspace request definitions.
