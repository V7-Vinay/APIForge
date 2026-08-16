# APIForge Production Deployment Runbook

## Preflight

- Docker Engine and Compose v2 installed.
- PostgreSQL and Redis persistent storage available.
- TLS is terminated at a trusted reverse proxy/load balancer.
- `.env.production` is stored outside source control.
- Database backup and restore procedure has been tested.

## Configuration

```bash
cp .env.production.example .env.production
```

Set strong values for:

- `POSTGRES_PASSWORD`
- `JWT_SECRET_KEY`
- `ENVIRONMENT_ENCRYPTION_KEY`
- `CORS_ORIGINS`
- `ALLOWED_HOSTS`
- `BUILD_SHA`

For a public HTTPS deployment, use:

```text
COOKIE_SECURE=true
RATE_LIMIT_FAIL_OPEN=false
TRUST_PROXY_HEADERS=true
```

Only enable `TRUST_PROXY_HEADERS` when the backend is reachable exclusively through a trusted proxy that overwrites forwarding headers.

## Release

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml pull
docker compose --env-file .env.production -f docker-compose.prod.yml build --pull
docker compose --env-file .env.production -f docker-compose.prod.yml up -d
```

Migrations run before the backend starts serving traffic.

## Verification

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml ps
curl -f http://localhost/api/v1/health
curl -f http://localhost/api/v1/ready
```

Check logs:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml logs --tail=200 backend
```

## Rollback

1. Stop the current application deployment.
2. Deploy the previous known-good image/source revision.
3. Do not automatically downgrade database migrations.
4. If a migration is not backward compatible, restore from the tested database backup according to the incident runbook.

## Backups

Back up PostgreSQL regularly. Redis is used for ephemeral coordination/rate-limiting/presence state and should not be treated as the source of truth for application data.

## Security

- Never expose PostgreSQL or Redis directly to the public internet.
- Never commit production secrets.
- Keep the backend private behind the frontend/reverse proxy.
- Use HTTPS in production.
- Rotate credentials using an operational secret-management process.
- Review audit logs and rate-limit metrics during releases.
