# APIForge — Phase 4: Collections & Requests

## Objective

Introduce the core API organization model: collections, nested folders, and persisted API request definitions.

## Included

- Collections CRUD
- Nested folders
- API request definitions
- Request headers/query parameters/body/auth configuration
- Deterministic positions
- Request/folder/collection authorization
- Tenant isolation
- Cross-collection hierarchy validation
- Alembic migration
- Initial request-builder UI

## Deliberately excluded

- Environment variables and variable resolution
- Actual HTTP execution
- SSRF/network validation
- Execution history
- WebSockets
- Search
- Documentation generation

## Important security invariant

A collection/folder/request is never accessible merely because its ID is known. The resource is resolved back to its owning workspace and the authenticated user's workspace membership/permission is checked.

## Verification

```bash
cp .env.example .env
docker compose up --build
```

Then verify `/api/v1/health`, `/api/v1/ready`, and `/docs`.

The backend migration should advance to `0003_collections_requests`.

### Core workflow

1. Register/login.
2. Create a workspace.
3. Create a collection.
4. Create a root folder and nested folder.
5. Create a request inside the collection/folder.
6. Update the request.
7. List the collection's requests.
8. Verify a VIEWER cannot mutate resources.
9. Verify a non-member cannot access resources by UUID.
10. Verify a folder from another collection cannot be attached to a request.

## Phase boundary

Phase 4 stores request definitions only. It does not execute them. `POST /requests/{id}/execute` is intentionally not implemented until Phase 6.
