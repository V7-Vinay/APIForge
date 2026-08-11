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

## 2. Completed Scope (Phases 1 & 2)

The project currently contains all core infrastructure and basic security layers:

### Phase 1 — Infrastructure
- **Docker Integration**: Multi-container setup with Postgres, Redis, backend (FastAPI), and frontend (React) services.
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

---

## 4. Excluded Scope (Roadmap for Phase 3+)

To maintain a clean separation of concerns, the following features have been **deliberately excluded** from the current implementation and are earmarked for Phase 3:

1. **Workspaces**: Dedicated team boundaries and collaborative settings.
2. **Role-Based Access Control (RBAC)**: Fine-grained permissions (Owners, Editors, Viewers) per workspace.
3. **Collections**: Logical groupings of API requests.
4. **API Requests**: Request builder with customizable HTTP methods, headers, parameters, and bodies.
5. **Environments**: Variable management (e.g., base URL, auth keys) for API request testing.
6. **Request Execution**: Executing arbitrary HTTP requests from backend/frontend workers and recording responses.
7. **WebSockets**: Real-time collaborative syncing of workspace states and collaborative editing.
