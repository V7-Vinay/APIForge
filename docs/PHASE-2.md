# APIForge — Phase 2: Authentication

## Objective
Implement secure identity without introducing workspace/RBAC/business features.

## Included
- User registration
- Argon2 password hashing
- JWT access tokens
- HttpOnly refresh-token cookie
- Refresh-token persistence as hashes
- Refresh-token rotation
- Refresh-token revocation
- Refresh-token reuse detection
- Protected `/auth/me`
- Alembic migration
- Minimal frontend auth flow

## Flow
```text
Register → Argon2 hash → PostgreSQL
Login → verify password → access JWT + refresh cookie
Protected request → Bearer JWT → current user
Refresh → validate old token → revoke → issue new pair
```

## Endpoints
```text
POST /api/v1/auth/register
POST /api/v1/auth/login
POST /api/v1/auth/refresh
POST /api/v1/auth/logout
GET  /api/v1/auth/me
```

## Verification
```bash
docker compose up --build
```
Open `http://localhost:5173`, register, log in, and confirm the authenticated user is shown.

## Deliberately excluded
Workspaces, RBAC, invitations, collections, API requests, environments, request execution, and WebSockets.
