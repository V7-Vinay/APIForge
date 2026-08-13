# APIForge — Collaborative API Development Platform

APIForge is a production-oriented collaborative API development platform built using FastAPI, React, PostgreSQL, and Redis.

## Status: Phase 5 Completed

This repository houses the merged codebase of **Phase 1 (Infrastructure)**, **Phase 2 (Authentication & Identity)**, **Phase 3 (Multi-Tenant Workspaces & RBAC)**, **Phase 4 (Collections & Request definitions)**, and **Phase 5 (Environment Management)**.

### Core Features Installed:
- **Relational Backend**: FastAPI + SQLAlchemy (Async) running on Python 3.12.
- **Caching Layer**: Redis client integrated for state management and rate limiting.
- **Single Page Frontend**: React + TypeScript + Vite.
- **Secure Authentication**: User registration and login. Passwords hashed using Argon2.
- **Token Security**: Rotating JWT access tokens (30-minute expiration) and secure HttpOnly refresh token cookies (30-day expiration).
- **Multi-Tenant Workspaces & RBAC**: Logical workspace boundaries with role capabilities (`OWNER`, `ADMIN`, `EDITOR`, `VIEWER`).
- **Workspace Member Invitations**: Safe email-matching invitation workflow using SHA-256 hashed cryptotokens.
- **Collections & Nested Folders**: Organized request groups supporting nested folder hierarchy with position indices.
- **API Request Definitions**: Persistence of HTTP headers, parameters, body payloads, and auth configurations.
- **Workspace Environments & Variables**: Environment CRUD with values encrypted at rest using Fernet symmetric encryption.
- **Variable Syntax & Safe Resolution**: Syntax `{{VARIABLE_NAME}}` resolved on-demand and secret values masked.
- **Auto Migrations**: DB migrations managed via Alembic and executed on startup.
- **Health & Readiness Endpoints**: Automated check services at `/api/v1/health` and `/api/v1/ready`.

---

## Getting Started

### Prerequisites
- Docker & Docker Compose installed on the host.

### Local Deployment

To run the entire stack locally:

1. Clone or unpack the repository.
2. Initialize environment variables:
   ```bash
   cp .env.example .env
   ```
3. Boot the Docker containers:
   ```bash
   docker compose up --build
   ```

Once containers are running, the application can be accessed at:
- **Frontend SPA**: `http://localhost:5173`
- **FastAPI Core Docs**: `http://localhost:8000/docs`
- **Health Verification**: `http://localhost:8000/api/v1/health`
- **Readiness Verification**: `http://localhost:8000/api/v1/ready`

---

## Project Structure & Roadmap

Detailed architecture and structural schemas are available in [docs/ARCHITECTURE.md](file:///c:/Users/HP/Desktop/Desktop/WEB%20PROJECT/APIForge/docs/ARCHITECTURE.md).

### Next Phase: Phase 6
Phase 6 will introduce HTTP request execution, client/worker engines, SSRF/network validation, and execution history.

