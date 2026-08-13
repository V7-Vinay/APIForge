import json
import logging
import uuid
from datetime import datetime, timezone

from app.core.redis import get_redis
from app.schemas.collaboration import CollaborationEvent, CollaborationEventType

logger = logging.getLogger(__name__)

CHANNEL_PREFIX = "apiforge:collaboration:workspace:"
PRESENCE_PREFIX = "apiforge:presence:"
PRESENCE_TTL_SECONDS = 30


def workspace_channel(workspace_id: uuid.UUID) -> str:
    return f"{CHANNEL_PREFIX}{workspace_id}"


def presence_key(
    workspace_id: uuid.UUID, request_id: uuid.UUID, connection_id: str
) -> str:
    return f"{PRESENCE_PREFIX}{workspace_id}:{request_id}:{connection_id}"


async def publish_workspace_event(event: CollaborationEvent) -> None:
    """Publish best-effort realtime events without breaking the source mutation if Redis is unavailable."""
    try:
        await get_redis().publish(
            workspace_channel(event.workspace_id),
            event.model_dump_json(),
        )
    except Exception:
        logger.exception(
            "Failed to publish collaboration event",
            extra={
                "event_type": event.type.value,
                "workspace_id": str(event.workspace_id),
            },
        )


async def set_presence(
    *,
    workspace_id: uuid.UUID,
    request_id: uuid.UUID,
    connection_id: str,
    user_id: uuid.UUID,
    user_name: str,
) -> None:
    value = {
        "connection_id": connection_id,
        "user_id": str(user_id),
        "name": user_name,
        "request_id": str(request_id),
        "last_seen": datetime.now(timezone.utc).isoformat(),
    }
    await get_redis().set(
        presence_key(workspace_id, request_id, connection_id),
        json.dumps(value),
        ex=PRESENCE_TTL_SECONDS,
    )


async def refresh_presence(
    *, workspace_id: uuid.UUID, request_id: uuid.UUID, connection_id: str
) -> None:
    key = presence_key(workspace_id, request_id, connection_id)
    redis = get_redis()
    raw = await redis.get(key)
    if raw is None:
        return
    value = json.loads(raw)
    value["last_seen"] = datetime.now(timezone.utc).isoformat()
    await redis.set(key, json.dumps(value), ex=PRESENCE_TTL_SECONDS)


async def remove_presence(
    *, workspace_id: uuid.UUID, request_id: uuid.UUID, connection_id: str
) -> None:
    await get_redis().delete(presence_key(workspace_id, request_id, connection_id))


async def list_presence(
    *, workspace_id: uuid.UUID, request_id: uuid.UUID
) -> list[dict]:
    redis = get_redis()
    prefix = f"{PRESENCE_PREFIX}{workspace_id}:{request_id}:"
    items: list[dict] = []
    async for key in redis.scan_iter(match=f"{prefix}*", count=100):
        raw = await redis.get(key)
        if raw is None:
            continue
        try:
            items.append(json.loads(raw))
        except json.JSONDecodeError:
            continue
    items.sort(
        key=lambda item: (item.get("name", "").lower(), item.get("connection_id", ""))
    )
    return items


def event(
    *,
    event_type: CollaborationEventType,
    workspace_id: uuid.UUID,
    actor_id: uuid.UUID | None = None,
    request_id: uuid.UUID | None = None,
    resource_id: uuid.UUID | None = None,
    resource_type: str | None = None,
    payload: dict | None = None,
) -> CollaborationEvent:
    return CollaborationEvent(
        type=event_type,
        workspace_id=workspace_id,
        actor_id=actor_id,
        request_id=request_id,
        resource_id=resource_id,
        resource_type=resource_type,
        payload=payload or {},
    )
