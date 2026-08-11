# APIForge — Collaborative API Development Platform

APIForge is a production-oriented collaborative API development platform built using FastAPI, React, PostgreSQL, and Redis.

## Status: Phases 1 & 2 Completed

This repository houses the merged codebase of **Phase 1 (Infrastructure)** and **Phase 2 (Authentication & Identity)**.

### Core Features Installed:
- **Relational Backend**: FastAPI + SQLAlchemy (Async) running on Python 3.13.
- **Caching Layer**: Redis client integrated for state management and rate limiting.
- **Single Page Frontend**: React + TypeScript + Vite.
- **Secure Authentication**: User registration and login. Passwords hashed using Argon2.
- **Token Security**: Rotating JWT access tokens (15-minute expiration) and secure HttpOnly refresh token cookies (30-day expiration).
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

### Next Phase: Phase 3
Phase 3 will introduce workspaces, collections, custom environment variables, roles/permissions (RBAC), request execution, and WebSockets.
