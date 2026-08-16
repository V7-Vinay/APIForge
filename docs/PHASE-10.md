# Phase 10 — Audit & Security

## Scope

Phase 10 hardens the cumulative Phase 1–9 platform with audit logging, distributed Redis-backed rate limiting, security response headers, production configuration checks, and centralized secret redaction.

## Audit logging

`audit_logs` records security-relevant HTTP activity without storing request bodies or credentials. Each entry can include:

- authenticated actor
- workspace when present in the URL
- HTTP method/path/status
- resource type/id when identifiable
- client IP and user-agent
- request ID and redacted query metadata
- timestamp

Endpoint:

`GET /api/v1/workspaces/{workspace_id}/audit-logs`

Only OWNER and ADMIN can view workspace audit logs.

## Rate limiting

Redis-backed fixed-window limiting is distributed across backend instances. Current defaults:

- login: 10/min/IP
- registration: 5/min/IP
- refresh: 20/min/IP
- request execution: 30/min/user-or-IP
- general API traffic: 300/min/user-or-IP

The limiter returns HTTP 429 with `Retry-After` and rate-limit headers. It can fail open for availability via `RATE_LIMIT_FAIL_OPEN=true`.

## Security hardening

The backend now emits:

- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Referrer-Policy: no-referrer`
- restrictive `Permissions-Policy`
- HSTS in production
- `X-Request-ID` correlation headers

Trusted hosts are configurable with `ALLOWED_HOSTS`. Proxy forwarding headers are ignored unless `TRUST_PROXY_HEADERS=true`.

Production startup refuses insecure default JWT configuration, missing environment encryption keys, or insecure refresh-cookie configuration.

## Secret redaction

`backend/app/core/redaction.py` is the canonical redaction utility. It protects sensitive keys in mappings, JSON text, headers, and URL query strings. Execution history passes response headers/body/URL/error data through this redaction layer before persistence.
