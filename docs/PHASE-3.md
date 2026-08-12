# APIForge — Phase 3: Multi-Tenant Workspaces + RBAC

## Objective

Introduce workspace ownership, membership, role-based permissions, and backend-enforced tenant isolation.

## Implemented

- Workspaces
- Workspace membership
- OWNER / ADMIN / EDITOR / VIEWER roles
- Permission matrix
- Workspace creation with automatic owner membership
- Workspace listing for current user
- Workspace read/update/delete
- Member listing
- Member role changes
- Member removal
- Backend membership dependency
- Backend permission dependency
- Alembic migration
- RBAC unit tests

## Tenant-isolation invariant

Every workspace-scoped endpoint resolves the current user's membership using both:

- authenticated user ID
- workspace ID

A caller cannot access another workspace merely by changing the workspace UUID.

For non-members, the API returns `404 Workspace not found` rather than confirming that a protected workspace exists.

## Role permissions

- OWNER: all permissions
- ADMIN: manage members and workspace resources, but not workspace deletion
- EDITOR: manage collections/requests, execute requests, edit documentation
- VIEWER: read workspace/history only

The role-to-permission mapping lives in `app/core/permissions.py` so authorization rules are centralized rather than scattered through route handlers.

## Run

```bash
cp .env.example .env
docker compose up --build
```

The backend runs migrations before starting.

## Verify

1. Register user A.
2. Login as user A.
3. Create a workspace.
4. Confirm the creator appears as `OWNER`.
5. Register user B.
6. Login as user B.
7. Attempt to access user A's workspace ID as user B — expect `404`.
8. Add/member-management endpoints can be exercised after a membership exists.
9. Verify viewer/editor/admin permission boundaries using the API docs.

## Deliberately excluded

- Invitations
- Collections
- API requests
- Environments
- Request execution
- WebSockets
- Audit logging

Those belong to later phases.
