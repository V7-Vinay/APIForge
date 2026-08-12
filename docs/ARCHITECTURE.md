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
        (Relational DB)   (Cache/Store)
```

- **Frontend**: Single Page Application (SPA) built using React, TypeScript, and Vite. All API requests are proxied internally through the Vite dev server to avoid CORS issues during local development.
- **Backend**: Asynchronous FastAPI service running on Uvicorn. Emits structured JSON logs for auditability.
- **PostgreSQL**: Serves as the primary database storing users, credential hashes, and token families. Database schemas are managed using Alembic migrations.
- **Redis**: Serves as the temporary store for refresh token states, rate limiting, and cache verification.

---

## 2. Completed Scope (Phases 1, 2 & 3)

The project currently contains core infrastructure, security layers, and multi-tenant workspace management:

### Phase 1 — Infrastructure
- **Docker Integration**: Multi-container setup with Postgres, Redis, backend (FastAPI), frontend (React) services, and Adminer DB viewer.
- **Connectivity & Monitoring**: Built-in health check and dependency readiness verification endpoints:
  - `/api/v1/health` checks backend process health.
  - `/api/v1/ready` checks relational database (Postgres) and caching layer (Redis) readiness.
- **Configuration**: Managed via environment variables (.env files) read dynamically by Pydantic settings.

### Phase 2 — Authentication & Identity
- **User Registration**: Users can register with unique email addresses, hashed in the database using the **Argon2** password hashing function.
- **JWT Authorization**:
  - Short-lived JSON Web Tokens (JWT) are used as access tokens. They expire in 15 minutes and are transmitted via the `Authorization: Bearer <token>` header.
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

---

## 4. Excluded Scope (Roadmap for Phase 4+)

To maintain a clean separation of concerns, the following features are **deliberately excluded** from the current implementation and are earmarked for Phase 4+:

1. **Collections**: Logical groupings of API requests.
2. **API Requests**: Request builder with customizable HTTP methods, headers, parameters, and bodies.
3. **Environments**: Variable management (e.g., base URL, auth keys) for API request testing.
4. **Request Execution**: Executing arbitrary HTTP requests from backend/frontend workers and recording responses.
5. **WebSockets**: Real-time collaborative syncing of workspace states and collaborative editing.
6. **Audit Logging**: Structured log record of actions performed on workspace resources.


