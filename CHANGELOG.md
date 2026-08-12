# Changelog

All notable changes to the APIForge project will be documented in this file.

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
