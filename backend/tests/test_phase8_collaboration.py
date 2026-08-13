import uuid

import pytest

from app.api.v1.router import api_router
from app.schemas.collaboration import (
    CollaborationClientMessage,
    CollaborationEventType,
)
from app.services.collaboration import (
    CHANNEL_PREFIX,
    PRESENCE_PREFIX,
    event,
    presence_key,
    workspace_channel,
)


def test_collaboration_websocket_route_is_registered():
    paths = {
        getattr(route, "path", None)
        for route in api_router.routes
        if getattr(route, "path", None)
    }
    assert "/workspaces/{workspace_id}/collaboration" in paths


def test_event_envelope_is_safe_and_structured():
    workspace_id = uuid.uuid4()
    request_id = uuid.uuid4()
    actor_id = uuid.uuid4()
    collaboration_event = event(
        event_type=CollaborationEventType.REQUEST_UPDATED,
        workspace_id=workspace_id,
        actor_id=actor_id,
        request_id=request_id,
        resource_id=request_id,
        resource_type="request",
        payload={"action": "updated", "collection_id": str(uuid.uuid4())},
    )

    assert collaboration_event.type == CollaborationEventType.REQUEST_UPDATED
    assert collaboration_event.workspace_id == workspace_id
    assert collaboration_event.actor_id == actor_id
    assert collaboration_event.request_id == request_id
    assert collaboration_event.payload["action"] == "updated"
    assert "password" not in collaboration_event.model_dump_json().lower()
    assert "token" not in collaboration_event.model_dump_json().lower()


def test_collaboration_client_messages_are_restricted_to_protocol_actions():
    message = CollaborationClientMessage(type="JOIN_REQUEST", request_id=uuid.uuid4())
    assert message.type == "JOIN_REQUEST"

    with pytest.raises(ValueError):
        CollaborationClientMessage(type="DELETE_REQUEST")


def test_workspace_and_presence_keys_are_scoped():
    workspace_id = uuid.uuid4()
    request_id = uuid.uuid4()
    connection_id = uuid.uuid4().hex

    assert workspace_channel(workspace_id) == f"{CHANNEL_PREFIX}{workspace_id}"
    assert presence_key(workspace_id, request_id, connection_id) == (
        f"{PRESENCE_PREFIX}{workspace_id}:{request_id}:{connection_id}"
    )
