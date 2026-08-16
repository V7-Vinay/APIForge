# APIForge — Phase 12: Productionization

## Scope

Phase 12 hardens the cumulative APIForge system for repeatable production-style deployment. It covers:

- optimized production containers
- non-root backend execution
- immutable frontend static image served by Nginx
- production Docker Compose
- health checks and dependency ordering
- database pool tuning
- graceful application shutdown
- request correlation in structured logs
- Prometheus-compatible HTTP metrics
- CI for backend tests, frontend builds, and browser E2E
- production configuration template and deployment runbook

Phase 12 does not add new product functionality.

## Production topology

```text
Browser
  |
  v
Nginx / frontend :80
  |---------------------> static React SPA
  |
  +---- /api/* ---------> FastAPI
  |                         |
  |                         +---- PostgreSQL
  |                         +---- Redis
  |
  +---- WebSocket --------> FastAPI collaboration endpoint
```

## Deployment

1. Copy `.env.production.example` to `.env.production`.
2. Replace every placeholder secret with a strong random value.
3. Set `CORS_ORIGINS` and `ALLOWED_HOSTS` to the real deployment values.
4. Put the frontend service behind a TLS terminator/load balancer in public deployments.
5. Set `COOKIE_SECURE=true` and keep `RATE_LIMIT_FAIL_OPEN=false`.
6. Set `BUILD_SHA` to the release commit SHA.
7. Start with:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml up -d --build
```

8. Verify:

```bash
curl http://localhost/api/v1/health
curl http://localhost/api/v1/ready
curl http://localhost/metrics
```

The backend port is intentionally not published by `docker-compose.prod.yml`; public traffic enters through Nginx.

## Secrets

Generate a Fernet key with:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Generate a JWT secret with a password generator or:

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

Do not commit `.env.production`.

## Observability

Structured JSON logs include `request_id`. The application exposes a dependency-free Prometheus-compatible `/metrics` endpoint when `METRICS_ENABLED=true`.

Metrics are process-local. For multiple backend instances, scrape every instance and aggregate at the monitoring layer.

Recommended production alerts:

- readiness failures
- sustained HTTP 5xx rate
- elevated request latency
- Redis unavailable
- PostgreSQL unavailable
- repeated 429 responses
- execution security violations

## CI/CD

`.github/workflows/ci.yml` runs:

1. backend dependency installation and migrations
2. complete pytest suite
3. frontend `npm ci` and production build
4. Playwright Chromium installation
5. browser E2E smoke tests

Deployment is intentionally not automatic in this phase. A real production deployment should add a protected release environment, secret management, image registry, database backup/restore policy, and controlled rollout strategy.
