# APIForge — Phase 8: Real-Time Collaboration

## Objective

Add real-time collaboration without moving API resource persistence into WebSockets. REST remains the authoritative mutation path; WebSockets provide presence and low-latency change notifications.

## Implemented

### WebSocket endpoint

```text
WS /api/v1/workspaces/{workspace_id}/collaboration
```

The connection authenticates with the existing short-lived JWT through the first WebSocket message:

```json
{"type":"AUTH","token":"<access-token>"}
```

The token is intentionally not placed in the URL.

### Client messages

```text
AUTH
JOIN_REQUEST
LEAVE_REQUEST
PING
```

### Server events

```text
AUTHENTICATED
USER_JOINED_REQUEST
USER_LEFT_REQUEST
PRESENCE_SNAPSHOT
REQUEST_UPDATED
COLLECTION_UPDATED
ERROR
```

### Presence

Presence is scoped to a workspace/request pair. Each connection gets a unique connection ID and a Redis key with a 30-second TTL. Clients send heartbeats every 10 seconds. The server also refreshes presence snapshots periodically so expired connections disappear from the UI without requiring a database record.

No persistent presence table is introduced because presence is ephemeral state.

### Redis Pub/Sub

Each workspace has a collaboration channel:

```text
apiforge:collaboration:workspace:{workspace_id}
```

REST resource mutations publish lightweight events to that channel. Redis failures are treated as best-effort collaboration failures and do not roll back the already-committed database mutation.

### Resource events

Collection/folder mutations emit `COLLECTION_UPDATED`. Request mutations emit `REQUEST_UPDATED`. Event payloads contain resource identifiers and action metadata rather than full request definitions or credentials.

### Security

- JWT authentication is required before a socket becomes usable.
- Workspace membership is checked before subscription.
- Request joins verify that the request belongs to the authenticated workspace.
- Viewer members can observe collaboration/presence because they already have workspace read access.
- No credential/auth configuration is sent in collaboration event payloads.

## Architecture

```text
React
  │
  │ WebSocket: auth + presence
  ▼
FastAPI WebSocket endpoint
  │
  ├── JWT validation
  ├── workspace membership check
  ├── request membership check
  │
  ├──────────────► Redis Pub/Sub ◄──────────────┐
  │                                             │
  └── Redis TTL presence                        │
                                                │
        REST mutation ──► PostgreSQL            │
                │                                │
                └──── publish event ─────────────┘
```

## Design decisions

1. **REST remains authoritative**: WebSockets do not directly mutate collections or requests.
2. **Workspace-scoped Pub/Sub**: one channel provides a simple cross-instance fan-out boundary without introducing a message broker beyond Redis.
3. **Ephemeral presence in Redis**: presence should disappear automatically when a client stops heartbeating.
4. **Connection-level presence**: multiple browser tabs from the same user are represented independently.
5. **Lightweight events**: events carry IDs/actions, so clients re-fetch authoritative state through REST when needed.

## Verification

Run:

```bash
docker compose up --build
docker compose exec backend pytest -q
```

For manual collaboration verification:

1. Register/login as User A.
2. Open a workspace request in two browser windows.
3. Login as User A/B in the second window.
4. Select the same request.
5. Confirm the active user appears in the presence bar.
6. Edit/save the request from one window.
7. Confirm the other window refreshes the request.
8. Close a window and confirm the user disappears after the presence heartbeat/TTL window.
9. Verify a non-member cannot establish a usable collaboration session.
