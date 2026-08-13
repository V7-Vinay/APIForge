import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.api.workspace_dependencies import (
    authorize_workspace,
    authorize_collection,
    authorize_folder,
    authorize_request,
)
from app.core.database import get_db
from app.core.permissions import Permission
from app.core.errors import ResourceNotFoundError, ValidationError
from app.models.collection import Collection
from app.models.folder import Folder
from app.models.api_request import APIRequest
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.resources import (
    CollectionCreate,
    CollectionResponse,
    CollectionUpdate,
    FolderCreate,
    FolderResponse,
    FolderUpdate,
    RequestCreate,
    RequestResponse,
    RequestUpdate,
    ReorderPayload,
)
from app.schemas.collaboration import CollaborationEventType
from app.services.collaboration import event, publish_workspace_event
from app.services.resources import (
    ResourceRuleError,
    create_collection,
    create_folder,
    create_request,
    delete_collection,
    delete_folder,
    delete_request,
    list_collections,
    list_folders,
    list_requests,
    reorder_collection,
    reorder_folder,
    reorder_request,
    update_collection,
    update_folder,
    update_request,
)

router = APIRouter(tags=["collections", "folders", "requests"])


def _handle_service_error(exc: ResourceRuleError):
    raise ValidationError(str(exc))


@router.post(
    "/workspaces/{workspace_id}/collections",
    response_model=CollectionResponse,
    status_code=201,
)
async def create_collection_endpoint(
    payload: CollectionCreate,
    workspace: Workspace = Depends(authorize_workspace(Permission.MANAGE_COLLECTIONS)),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    created = await create_collection(
        session, workspace_id=workspace.id, payload=payload
    )
    await publish_workspace_event(
        event(
            event_type=CollaborationEventType.COLLECTION_UPDATED,
            workspace_id=workspace.id,
            actor_id=current_user.id,
            resource_id=created.id,
            resource_type="collection",
            payload={"action": "created", "collection_id": str(created.id)},
        )
    )
    return created


@router.get(
    "/workspaces/{workspace_id}/collections", response_model=list[CollectionResponse]
)
async def list_collection_endpoint(
    workspace: Workspace = Depends(authorize_workspace(Permission.VIEW_WORKSPACE)),
    session: AsyncSession = Depends(get_db),
):
    return await list_collections(session, workspace_id=workspace.id)


@router.get("/collections/{collection_id}", response_model=CollectionResponse)
async def get_collection_endpoint(
    collection: Collection = Depends(authorize_collection(Permission.VIEW_WORKSPACE)),
):
    return collection


@router.patch("/collections/{collection_id}", response_model=CollectionResponse)
async def update_collection_endpoint(
    payload: CollectionUpdate,
    collection: Collection = Depends(
        authorize_collection(Permission.MANAGE_COLLECTIONS)
    ),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    updated = await update_collection(session, collection=collection, payload=payload)
    await publish_workspace_event(
        event(
            event_type=CollaborationEventType.COLLECTION_UPDATED,
            workspace_id=collection.workspace_id,
            actor_id=current_user.id,
            resource_id=collection.id,
            resource_type="collection",
            payload={"action": "updated", "collection_id": str(collection.id)},
        )
    )
    return updated


@router.delete("/collections/{collection_id}", status_code=204)
async def delete_collection_endpoint(
    collection: Collection = Depends(
        authorize_collection(Permission.MANAGE_COLLECTIONS)
    ),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    workspace_id = collection.workspace_id
    collection_id = collection.id
    await delete_collection(session, collection=collection)
    await publish_workspace_event(
        event(
            event_type=CollaborationEventType.COLLECTION_UPDATED,
            workspace_id=workspace_id,
            actor_id=current_user.id,
            resource_id=collection_id,
            resource_type="collection",
            payload={"action": "deleted", "collection_id": str(collection_id)},
        )
    )


@router.patch("/collections/{collection_id}/reorder", response_model=CollectionResponse)
async def reorder_collection_endpoint(
    payload: ReorderPayload,
    collection: Collection = Depends(
        authorize_collection(Permission.MANAGE_COLLECTIONS)
    ),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    updated = await reorder_collection(
        session, collection=collection, position=payload.position
    )
    await publish_workspace_event(
        event(
            event_type=CollaborationEventType.COLLECTION_UPDATED,
            workspace_id=collection.workspace_id,
            actor_id=current_user.id,
            resource_id=collection.id,
            resource_type="collection",
            payload={"action": "reordered", "collection_id": str(collection.id)},
        )
    )
    return updated


@router.post(
    "/collections/{collection_id}/folders",
    response_model=FolderResponse,
    status_code=201,
)
async def create_folder_endpoint(
    payload: FolderCreate,
    collection: Collection = Depends(
        authorize_collection(Permission.MANAGE_COLLECTIONS)
    ),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    try:
        created = await create_folder(session, collection=collection, payload=payload)
        await publish_workspace_event(
            event(
                event_type=CollaborationEventType.COLLECTION_UPDATED,
                workspace_id=collection.workspace_id,
                actor_id=current_user.id,
                resource_id=created.id,
                resource_type="folder",
                payload={
                    "action": "created",
                    "collection_id": str(collection.id),
                    "folder_id": str(created.id),
                },
            )
        )
        return created
    except ResourceRuleError as exc:
        _handle_service_error(exc)


@router.get("/collections/{collection_id}/folders", response_model=list[FolderResponse])
async def list_folder_endpoint(
    collection: Collection = Depends(authorize_collection(Permission.VIEW_WORKSPACE)),
    session: AsyncSession = Depends(get_db),
):
    return await list_folders(session, collection_id=collection.id)


@router.get("/folders/{folder_id}", response_model=FolderResponse)
async def get_folder_endpoint(
    folder: Folder = Depends(authorize_folder(Permission.VIEW_WORKSPACE)),
):
    return folder


@router.patch("/folders/{folder_id}", response_model=FolderResponse)
async def update_folder_endpoint(
    payload: FolderUpdate,
    folder: Folder = Depends(authorize_folder(Permission.MANAGE_COLLECTIONS)),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    try:
        collection = await session.get(Collection, folder.collection_id)
        updated = await update_folder(session, folder=folder, payload=payload)
        await publish_workspace_event(
            event(
                event_type=CollaborationEventType.COLLECTION_UPDATED,
                workspace_id=(
                    collection.workspace_id
                    if collection
                    else folder.collection.workspace_id
                ),
                actor_id=current_user.id,
                resource_id=folder.id,
                resource_type="folder",
                payload={
                    "action": "updated",
                    "collection_id": str(folder.collection_id),
                    "folder_id": str(folder.id),
                },
            )
        )
        return updated
    except ResourceRuleError as exc:
        _handle_service_error(exc)


@router.delete("/folders/{folder_id}", status_code=204)
async def delete_folder_endpoint(
    folder: Folder = Depends(authorize_folder(Permission.MANAGE_COLLECTIONS)),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    collection = await session.get(Collection, folder.collection_id)
    workspace_id = (
        collection.workspace_id if collection else folder.collection.workspace_id
    )
    folder_id = folder.id
    collection_id = folder.collection_id
    await delete_folder(session, folder=folder)
    await publish_workspace_event(
        event(
            event_type=CollaborationEventType.COLLECTION_UPDATED,
            workspace_id=workspace_id,
            actor_id=current_user.id,
            resource_id=folder_id,
            resource_type="folder",
            payload={
                "action": "deleted",
                "collection_id": str(collection_id),
                "folder_id": str(folder_id),
            },
        )
    )


@router.patch("/folders/{folder_id}/reorder", response_model=FolderResponse)
async def reorder_folder_endpoint(
    payload: ReorderPayload,
    folder: Folder = Depends(authorize_folder(Permission.MANAGE_COLLECTIONS)),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    collection = await session.get(Collection, folder.collection_id)
    updated = await reorder_folder(session, folder=folder, position=payload.position)
    await publish_workspace_event(
        event(
            event_type=CollaborationEventType.COLLECTION_UPDATED,
            workspace_id=(
                collection.workspace_id
                if collection
                else folder.collection.workspace_id
            ),
            actor_id=current_user.id,
            resource_id=folder.id,
            resource_type="folder",
            payload={
                "action": "reordered",
                "collection_id": str(folder.collection_id),
                "folder_id": str(folder.id),
            },
        )
    )
    return updated


@router.post(
    "/collections/{collection_id}/requests",
    response_model=RequestResponse,
    status_code=201,
)
async def create_request_endpoint(
    payload: RequestCreate,
    collection: Collection = Depends(authorize_collection(Permission.EDIT_REQUESTS)),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    try:
        created = await create_request(session, collection=collection, payload=payload)
        await publish_workspace_event(
            event(
                event_type=CollaborationEventType.REQUEST_UPDATED,
                workspace_id=collection.workspace_id,
                actor_id=current_user.id,
                request_id=created.id,
                resource_id=created.id,
                resource_type="request",
                payload={
                    "action": "created",
                    "collection_id": str(collection.id),
                    "request_id": str(created.id),
                },
            )
        )
        return created
    except ResourceRuleError as exc:
        _handle_service_error(exc)


@router.get(
    "/collections/{collection_id}/requests", response_model=list[RequestResponse]
)
async def list_request_endpoint(
    collection: Collection = Depends(authorize_collection(Permission.VIEW_WORKSPACE)),
    session: AsyncSession = Depends(get_db),
):
    return await list_requests(session, collection_id=collection.id)


@router.get("/requests/{request_id}", response_model=RequestResponse)
async def get_request_endpoint(
    request: APIRequest = Depends(authorize_request(Permission.VIEW_WORKSPACE)),
):
    return request


@router.patch("/requests/{request_id}", response_model=RequestResponse)
async def update_request_endpoint(
    payload: RequestUpdate,
    request: APIRequest = Depends(authorize_request(Permission.EDIT_REQUESTS)),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    try:
        collection = await session.get(Collection, request.collection_id)
        updated = await update_request(session, request=request, payload=payload)
        await publish_workspace_event(
            event(
                event_type=CollaborationEventType.REQUEST_UPDATED,
                workspace_id=(
                    collection.workspace_id
                    if collection
                    else request.collection.workspace_id
                ),
                actor_id=current_user.id,
                request_id=request.id,
                resource_id=request.id,
                resource_type="request",
                payload={
                    "action": "updated",
                    "collection_id": str(request.collection_id),
                    "request_id": str(request.id),
                },
            )
        )
        return updated
    except ResourceRuleError as exc:
        _handle_service_error(exc)


@router.delete("/requests/{request_id}", status_code=204)
async def delete_request_endpoint(
    request: APIRequest = Depends(authorize_request(Permission.EDIT_REQUESTS)),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    collection = await session.get(Collection, request.collection_id)
    request_id = request.id
    collection_id = request.collection_id
    await delete_request(session, request=request)
    await publish_workspace_event(
        event(
            event_type=CollaborationEventType.REQUEST_UPDATED,
            workspace_id=(
                collection.workspace_id
                if collection
                else request.collection.workspace_id
            ),
            actor_id=current_user.id,
            request_id=request_id,
            resource_id=request_id,
            resource_type="request",
            payload={
                "action": "deleted",
                "collection_id": str(collection_id),
                "request_id": str(request_id),
            },
        )
    )


@router.patch("/requests/{request_id}/reorder", response_model=RequestResponse)
async def reorder_request_endpoint(
    payload: ReorderPayload,
    request: APIRequest = Depends(authorize_request(Permission.EDIT_REQUESTS)),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    collection = await session.get(Collection, request.collection_id)
    updated = await reorder_request(session, request=request, position=payload.position)
    await publish_workspace_event(
        event(
            event_type=CollaborationEventType.REQUEST_UPDATED,
            workspace_id=(
                collection.workspace_id
                if collection
                else request.collection.workspace_id
            ),
            actor_id=current_user.id,
            request_id=request.id,
            resource_id=request.id,
            resource_type="request",
            payload={
                "action": "reordered",
                "collection_id": str(request.collection_id),
                "request_id": str(request.id),
            },
        )
    )
    return updated
