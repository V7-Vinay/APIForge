# APIForge — Phase 9: Documentation

## Objective

Generate useful API documentation from the request definitions already stored in APIForge and support OpenAPI 3.x import/export without importing or exposing stored credentials.

## Implemented

### Documentation export

```text
GET /api/v1/workspaces/{workspace_id}/documentation/openapi.json
GET /api/v1/workspaces/{workspace_id}/documentation/summary
```

The generated document is OpenAPI 3.0.3 and contains:

- workspace title/version metadata
- collection-based tags
- request paths and HTTP methods
- descriptions and operation IDs
- query/header parameters
- request bodies with safe examples
- bearer/basic security schemes
- response documentation placeholders

Authentication credentials are never exported. Stored Authorization/Cookie/API-key style headers are also excluded from generated documentation.

### OpenAPI import

```text
POST /api/v1/workspaces/{workspace_id}/documentation/import
```

Accepts OpenAPI 3.0.x and 3.1.x JSON documents.

Import behavior:

- creates one collection
- creates folders from the first operation tag
- creates persisted API request definitions
- imports query/header parameters
- imports request-body examples where available
- derives bearer/basic authentication configuration
- never imports bearer tokens, basic passwords, or other credentials
- uses a single database transaction for the import

Import requires `MANAGE_COLLECTIONS` because it creates collections, folders, and requests.

## Security invariants

1. Documentation export requires workspace membership.
2. Documentation import requires the workspace collection-management permission.
3. Credentials are never included in exported OpenAPI documents.
4. Credential-bearing headers are excluded from exported documentation.
5. Imported authentication schemes contain no credentials; users configure them separately in APIForge.
6. REST remains the source of truth for persisted resources.
7. Successful imports publish a lightweight collaboration event.

## Design decisions

- **Generated OpenAPI rather than hand-authored Markdown:** APIForge already stores structured request definitions, so OpenAPI is a machine-readable documentation contract and can be rendered by standard tooling.
- **JSON first:** OpenAPI JSON is deterministic and requires no additional YAML parser. YAML import/export can be added later without changing the domain model.
- **No credential export:** documentation is not a secret transport mechanism.
- **Import as resource creation:** imported operations become normal APIForge requests, so existing execution, RBAC, search, and collaboration flows continue to work.
