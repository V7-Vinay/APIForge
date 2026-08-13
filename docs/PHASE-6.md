# APIForge — Phase 6: Request Execution Engine

Phase 6 adds controlled outbound HTTP execution for persisted API request definitions.

## Flow

Request -> workspace authorization -> environment resolution -> URL/IP security validation -> HTTP execution -> bounded response processing.

## Endpoint

`POST /api/v1/requests/{request_id}/execute`

Body:

```json
{"environment_id": "<uuid>"}
```

## Security controls

- Only `http` and `https` are accepted.
- URL credentials are rejected.
- Hostnames are resolved before connection and private/local/reserved/link-local/multicast ranges are blocked.
- `trust_env=False` prevents ambient proxy configuration from changing the outbound path.
- Redirects are disabled in the HTTP client and each redirect target is validated before following it.
- Request timeouts and maximum response size are configurable.
- Sensitive response headers are redacted from the API response.
- Upstream implementation details are not returned to clients.

## Scope boundary

Collection runners, WebSockets, and advanced monitoring remain outside this phase unless explicitly assigned by the master roadmap. (Note: Execution history database logging is included and implemented as part of request execution.)
