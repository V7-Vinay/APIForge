import asyncio
import json
import uuid
from contextlib import suppress

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.redis import get_redis
from app.core.security import TokenError, decode_access_token
from app.models.api_request import APIRequest
from app.models.collection import Collection
from app.models.user import User
from app.models.workspace_member import WorkspaceMember
from app.schemas.collaboration import (
    CollaborationClientMessage,
    CollaborationEventType,
)
from app.services.collaboration import (
    event,
    list_presence,
    publish_workspace_event,
    refresh_presence,
    remove_presence,
    set_presence,
    workspace_channel,
)

router = APIRouter(tags=["collaboration"])
AUTH_TIMEOUT_SECONDS = 5


async def _authenticate(websocket: WebSocket, token: str) -> User | None:
    try:
        payload = decode_access_token(token)
        user_id = uuid.UUID(str(payload["sub"]))
    except (TokenError, KeyError, ValueError):
        return None

    async with AsyncSessionLocal() as session:
        return await session.scalar(select(User).where(User.id == user_id))


async def _workspace_membership(
    user_id: uuid.UUID, workspace_id: uuid.UUID
) -> WorkspaceMember | None:
    async with AsyncSessionLocal() as session:
        return await session.scalar(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == user_id,
            )
        )


async def _request_belongs_to_workspace(
    request_id: uuid.UUID, workspace_id: uuid.UUID
) -> bool:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(APIRequest.id)
            .join(Collection, APIRequest.collection_id == Collection.id)
            .where(
                APIRequest.id == request_id,
                Collection.workspace_id == workspace_id,
            )
        )
        return result.scalar_one_or_none() is not None


@router.websocket("/workspaces/{workspace_id}/collaboration")
async def collaboration_socket(websocket: WebSocket, workspace_id: uuid.UUID) -> None:
    await websocket.accept()
    user: User | None = None
    current_request_id: uuid.UUID | None = None
    connection_id = uuid.uuid4().hex
    pubsub = None

    try:
        try:
            raw_auth = await asyncio.wait_for(
                websocket.receive_json(), timeout=AUTH_TIMEOUT_SECONDS
            )
            auth_message = CollaborationClientMessage.model_validate(raw_auth)
        except (asyncio.TimeoutError, ValueError, TypeError, json.JSONDecodeError):
            await websocket.close(code=1008, reason="Authentication required.")
            return

        if auth_message.type != "AUTH" or not auth_message.token:
            await websocket.close(code=1008, reason="Authentication required.")
            return

        user = await _authenticate(websocket, auth_message.token)
        if user is None:
            await websocket.close(code=1008, reason="Invalid access token.")
            return

        membership = await _workspace_membership(user.id, workspace_id)
        if membership is None:
            await websocket.close(code=1008, reason="Workspace access denied.")
            return

        await websocket.send_json(
            event(
                event_type=CollaborationEventType.AUTHENTICATED,
                workspace_id=workspace_id,
                actor_id=user.id,
                payload={"connection_id": connection_id},
            ).model_dump(mode="json")
        )

        pubsub = get_redis().pubsub()
        await pubsub.subscribe(workspace_channel(workspace_id))

        async def receive_client() -> dict:
            return await websocket.receive_json()

        async def receive_event() -> dict:
            message = await pubsub.get_message(
                ignore_subscribe_messages=True, timeout=1.0
            )
            if message is None:
                return {"type": "__timeout__"}
            data = message.get("data")
            if isinstance(data, bytes):
                data = data.decode()
            return {"type": "__event__", "data": data}

        presence_refresh_at = asyncio.get_running_loop().time()

        while True:
            client_task = asyncio.create_task(receive_client())
            event_task = asyncio.create_task(receive_event())
            done, pending = await asyncio.wait(
                {client_task, event_task}, return_when=asyncio.FIRST_COMPLETED
            )
            for task in pending:
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task

            completed = done.pop()
            message = completed.result()

            if message.get("type") == "__timeout__":
                now = asyncio.get_running_loop().time()
                if current_request_id is not None and now - presence_refresh_at >= 10:
                    snapshot = await list_presence(
                        workspace_id=workspace_id, request_id=current_request_id
                    )
                    await websocket.send_json(
                        event(
                            event_type=CollaborationEventType.PRESENCE_SNAPSHOT,
                            workspace_id=workspace_id,
                            actor_id=user.id,
                            request_id=current_request_id,
                            payload={"users": snapshot},
                        ).model_dump(mode="json")
                    )
                    presence_refresh_at = now
                continue

            if message.get("type") == "__event__":
                try:
                    payload = json.loads(message["data"])
                except (TypeError, json.JSONDecodeError):
                    continue
                if payload.get("actor_id") == str(user.id) and payload.get("type") in {
                    CollaborationEventType.USER_JOINED_REQUEST.value,
                    CollaborationEventType.USER_LEFT_REQUEST.value,
                }:
                    continue
                await websocket.send_json(payload)
                continue

            try:
                client_message = CollaborationClientMessage.model_validate(message)
            except ValueError:
                await websocket.send_json(
                    event(
                        event_type=CollaborationEventType.ERROR,
                        workspace_id=workspace_id,
                        actor_id=user.id,
                        payload={
                            "code": "INVALID_MESSAGE",
                            "message": "Unsupported collaboration message.",
                        },
                    ).model_dump(mode="json")
                )
                continue

            if client_message.type == "PING":
                if current_request_id is not None:
                    await refresh_presence(
                        workspace_id=workspace_id,
                        request_id=current_request_id,
                        connection_id=connection_id,
                    )
                    presence_refresh_at = asyncio.get_running_loop().time()
                await websocket.send_json(
                    event(
                        event_type=CollaborationEventType.AUTHENTICATED,
                        workspace_id=workspace_id,
                        actor_id=user.id,
                        payload={"heartbeat": True},
                    ).model_dump(mode="json")
                )
                continue

            if client_message.type == "LEAVE_REQUEST":
                if current_request_id is not None:
                    await remove_presence(
                        workspace_id=workspace_id,
                        request_id=current_request_id,
                        connection_id=connection_id,
                    )
                    await publish_workspace_event(
                        event(
                            event_type=CollaborationEventType.USER_LEFT_REQUEST,
                            workspace_id=workspace_id,
                            actor_id=user.id,
                            request_id=current_request_id,
                            payload={"user_name": user.name},
                        )
                    )
                    current_request_id = None
                continue

            if client_message.type == "JOIN_REQUEST":
                request_id = client_message.request_id
                if request_id is None or not await _request_belongs_to_workspace(
                    request_id, workspace_id
                ):
                    await websocket.send_json(
                        event(
                            event_type=CollaborationEventType.ERROR,
                            workspace_id=workspace_id,
                            actor_id=user.id,
                            payload={
                                "code": "REQUEST_NOT_FOUND",
                                "message": "Request not found.",
                            },
                        ).model_dump(mode="json")
                    )
                    continue

                if current_request_id is not None and current_request_id != request_id:
                    await remove_presence(
                        workspace_id=workspace_id,
                        request_id=current_request_id,
                        connection_id=connection_id,
                    )
                    await publish_workspace_event(
                        event(
                            event_type=CollaborationEventType.USER_LEFT_REQUEST,
                            workspace_id=workspace_id,
                            actor_id=user.id,
                            request_id=current_request_id,
                            payload={"user_name": user.name},
                        )
                    )

                current_request_id = request_id
                await set_presence(
                    workspace_id=workspace_id,
                    request_id=request_id,
                    connection_id=connection_id,
                    user_id=user.id,
                    user_name=user.name,
                )
                snapshot = await list_presence(
                    workspace_id=workspace_id, request_id=request_id
                )
                await websocket.send_json(
                    event(
                        event_type=CollaborationEventType.PRESENCE_SNAPSHOT,
                        workspace_id=workspace_id,
                        actor_id=user.id,
                        request_id=request_id,
                        payload={"users": snapshot},
                    ).model_dump(mode="json")
                )
                await publish_workspace_event(
                    event(
                        event_type=CollaborationEventType.USER_JOINED_REQUEST,
                        workspace_id=workspace_id,
                        actor_id=user.id,
                        request_id=request_id,
                        payload={
                            "user_id": str(user.id),
                            "user_name": user.name,
                            "connection_id": connection_id,
                        },
                    )
                )

    except WebSocketDisconnect:
        pass
    finally:
        if current_request_id is not None and user is not None:
            with suppress(Exception):
                await remove_presence(
                    workspace_id=workspace_id,
                    request_id=current_request_id,
                    connection_id=connection_id,
                )
                await publish_workspace_event(
                    event(
                        event_type=CollaborationEventType.USER_LEFT_REQUEST,
                        workspace_id=workspace_id,
                        actor_id=user.id,
                        request_id=current_request_id,
                        payload={"user_name": user.name},
                    )
                )
        if pubsub is not None:
            with suppress(Exception):
                await pubsub.unsubscribe(workspace_channel(workspace_id))
                await pubsub.aclose()
