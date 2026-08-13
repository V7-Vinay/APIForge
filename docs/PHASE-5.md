# APIForge — Phase 5: Environment Management

## Objective

Introduce workspace-scoped environments and variables for request configuration and safe variable resolution.

## Included

- Environment CRUD
- Environment variables CRUD
- Secret values encrypted at rest
- Variable syntax: `{{VARIABLE_NAME}}`
- Variable resolution endpoint
- Tenant isolation and RBAC
- Alembic migration

## Deliberately excluded

- Actual HTTP execution
- Environment-aware request execution
- SSRF/network validation
- Execution history
- WebSockets
- Background workers
- Search

## Security model

Environment values are encrypted at rest. Normal variable listings never return values. A dedicated reveal endpoint requires edit-level request permission. The resolve endpoint masks secret values rather than revealing them.

Cross-workspace environment access is rejected even when an ID is known.

## Verification

1. Start the stack.
2. Register/login.
3. Create a workspace.
4. Create `Development` and `Production` environments.
5. Add `BASE_URL=https://api.example.com` to Development.
6. Add a secret variable such as `API_TOKEN`.
7. Resolve `{{BASE_URL}}/users` and verify substitution.
8. Resolve `{{API_TOKEN}}` and verify the secret is masked.
9. Verify VIEWER cannot mutate variables.
10. Verify another workspace cannot access the environment by UUID.

Phase 5 does not execute requests. Execution remains Phase 6.
