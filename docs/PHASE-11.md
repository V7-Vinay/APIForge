# Phase 11 — Testing

## Scope

Phase 11 establishes a deliberate testing pyramid for APIForge:

- deterministic unit tests
- API/database/Redis integration tests
- security regression tests
- browser end-to-end smoke coverage

Phase 11 does not change product behavior or introduce CI/CD/deployment automation; those belong to Phase 12.

## Backend test layers

### Unit

`backend/tests/test_phase11_unit.py` covers deterministic invariants without external services:

- RBAC permission matrix
- recursive secret redaction
- header/query redaction
- SSRF URL policy
- pagination metadata

### Integration

`backend/tests/test_phase11_integration.py` exercises the real FastAPI application through HTTP and verifies:

- authentication → workspace → collection workflow
- tenant isolation
- request credential non-disclosure
- audit-log authorization
- health contract

Existing phase-specific integration/security tests remain part of the suite.

## Browser E2E

Playwright is configured in `frontend/playwright.config.ts`.

Smoke test:

`frontend/e2e/smoke.spec.ts`

It seeds a user/workspace through the API, opens the actual frontend, authenticates through the UI, and verifies the authenticated workspace controls render.

Run:

```bash
cd frontend
npm install
npx playwright install chromium
npm run test:e2e
```

Environment variables:

- `E2E_BASE_URL` — frontend URL, default `http://127.0.0.1:5173`
- `E2E_API_BASE_URL` — backend API URL, default `http://127.0.0.1:8000/api/v1`

## Test commands

Backend unit tests:

```bash
cd backend
pytest -m unit -q
```

Backend integration/security tests:

```bash
cd backend
pytest -m 'integration or security' -q
```

Full backend suite:

```bash
cd backend
pytest -q
```

Frontend type/build check:

```bash
cd frontend
npm run build
```

Browser E2E:

```bash
cd frontend
npm run test:e2e
```

## Test philosophy

Tests should assert behavior, not merely status codes. Security tests must assert non-disclosure, tenant boundaries, and permission semantics. Integration tests use the actual FastAPI application and configured PostgreSQL/Redis services. Browser E2E tests cover only high-value user journeys; exhaustive business-rule coverage remains in backend tests.
