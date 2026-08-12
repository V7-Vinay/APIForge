# APIForge — Phase 1

## Objective

Establish a reproducible local infrastructure foundation without implementing application-domain features.

## Included

- Docker Compose
- PostgreSQL
- Redis
- FastAPI
- React + TypeScript + Vite
- Environment configuration
- Structured JSON logging
- PostgreSQL connectivity
- Redis connectivity
- `/api/v1/health`
- `/api/v1/ready`

## Deliberately excluded

- Authentication
- JWT
- Workspaces
- RBAC
- Collections
- Requests
- Request execution
- Environments
- WebSockets
- Background workers
- Application data models

Those belong to later phases.

## Verification

From the repository root:

```bash
cp .env.example .env
docker compose up --build
```

Then verify:

```text
Frontend: http://localhost:5173
API docs: http://localhost:8000/docs
Health:   http://localhost:8000/api/v1/health
Ready:    http://localhost:8000/api/v1/ready
```

The readiness endpoint must report PostgreSQL and Redis as `ok`.

## Phase 1 acceptance criteria

- All required containers start successfully.
- Backend can connect to PostgreSQL.
- Backend can connect to Redis.
- Frontend loads.
- Frontend can reach backend health endpoint.
- `/health` reports process health.
- `/ready` reports dependency readiness.
- Configuration is environment-driven.
- Logs are emitted as JSON.
- No authentication or domain features are introduced.
