import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.api.workspace_dependencies import (
    get_workspace,
    get_workspace_membership,
    require_workspace_permission,
)
from app.core.database import get_db
from app.core.permissions import Permission
from app.models.collection import Collection
from app.models.folder import Folder
from app.models.api_request import APIRequest
from app.models.user import User
from app.models.workspace import Workspace
from app.models.workspace_member import WorkspaceMember
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
from app.services.resources import (
    ResourceRuleError,
    create_collection,
    create_folder,
    create_request,
    delete_collection,
    delete_folder,
    delete_request,
    get_collection,
    get_folder,
    get_request,
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


def resource_not_found(exc: ResourceRuleError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post(
    "/workspaces/{workspace_id}/collections",
    response_model=CollectionResponse,
    status_code=201,
)
async def create_collection_endpoint(
    payload: CollectionCreate,
    workspace: Workspace = Depends(get_workspace),
    membership: WorkspaceMember = Depends(
        require_workspace_permission(Permission.MANAGE_COLLECTIONS)
    ),
    session: AsyncSession = Depends(get_db),
):
    return await create_collection(session, workspace_id=workspace.id, payload=payload)


@router.get(
    "/workspaces/{workspace_id}/collections", response_model=list[CollectionResponse]
)
async def list_collection_endpoint(
    workspace: Workspace = Depends(get_workspace),
    membership: WorkspaceMember = Depends(get_workspace_membership),
    session: AsyncSession = Depends(get_db),
):
    return await list_collections(session, workspace_id=workspace.id)


@router.get("/collections/{collection_id}", response_model=CollectionResponse)
async def get_collection_endpoint(
    collection_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    try:
        collection = await get_collection(session, collection_id)
    except ResourceRuleError as exc:
        raise resource_not_found(exc) from exc
    await _authorize_collection(session, collection, current_user.id)
    return collection


@router.patch("/collections/{collection_id}", response_model=CollectionResponse)
async def update_collection_endpoint(
    payload: CollectionUpdate,
    collection_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    collection = await _authorized_collection(
        session, collection_id, current_user.id, Permission.MANAGE_COLLECTIONS
    )
    return await update_collection(session, collection=collection, payload=payload)


@router.delete("/collections/{collection_id}", status_code=204)
async def delete_collection_endpoint(
    collection_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    collection = await _authorized_collection(
        session, collection_id, current_user.id, Permission.MANAGE_COLLECTIONS
    )
    await delete_collection(session, collection=collection)


@router.patch("/collections/{collection_id}/reorder", response_model=CollectionResponse)
async def reorder_collection_endpoint(
    payload: ReorderPayload,
    collection_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    collection = await _authorized_collection(
        session, collection_id, current_user.id, Permission.MANAGE_COLLECTIONS
    )
    return await reorder_collection(
        session, collection=collection, position=payload.position
    )


@router.post(
    "/collections/{collection_id}/folders",
    response_model=FolderResponse,
    status_code=201,
)
async def create_folder_endpoint(
    payload: FolderCreate,
    collection_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    collection = await _authorized_collection(
        session, collection_id, current_user.id, Permission.MANAGE_COLLECTIONS
    )
    try:
        return await create_folder(session, collection=collection, payload=payload)
    except ResourceRuleError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/collections/{collection_id}/folders", response_model=list[FolderResponse])
async def list_folder_endpoint(
    collection_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    collection = await _authorized_collection(
        session, collection_id, current_user.id, Permission.VIEW_WORKSPACE
    )
    return await list_folders(session, collection_id=collection.id)


@router.get("/folders/{folder_id}", response_model=FolderResponse)
async def get_folder_endpoint(
    folder_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    folder = await _get_authorized_folder(
        session, folder_id, current_user.id, Permission.VIEW_WORKSPACE
    )
    return folder


@router.patch("/folders/{folder_id}", response_model=FolderResponse)
async def update_folder_endpoint(
    payload: FolderUpdate,
    folder_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    folder = await _get_authorized_folder(
        session, folder_id, current_user.id, Permission.MANAGE_COLLECTIONS
    )
    try:
        return await update_folder(session, folder=folder, payload=payload)
    except ResourceRuleError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/folders/{folder_id}", status_code=204)
async def delete_folder_endpoint(
    folder_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    folder = await _get_authorized_folder(
        session, folder_id, current_user.id, Permission.MANAGE_COLLECTIONS
    )
    await delete_folder(session, folder=folder)


@router.patch("/folders/{folder_id}/reorder", response_model=FolderResponse)
async def reorder_folder_endpoint(
    payload: ReorderPayload,
    folder_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    folder = await _get_authorized_folder(
        session, folder_id, current_user.id, Permission.MANAGE_COLLECTIONS
    )
    return await reorder_folder(session, folder=folder, position=payload.position)


@router.post(
    "/collections/{collection_id}/requests",
    response_model=RequestResponse,
    status_code=201,
)
async def create_request_endpoint(
    payload: RequestCreate,
    collection_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    collection = await _authorized_collection(
        session, collection_id, current_user.id, Permission.EDIT_REQUESTS
    )
    try:
        return await create_request(session, collection=collection, payload=payload)
    except ResourceRuleError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get(
    "/collections/{collection_id}/requests", response_model=list[RequestResponse]
)
async def list_request_endpoint(
    collection_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    collection = await _authorized_collection(
        session, collection_id, current_user.id, Permission.VIEW_WORKSPACE
    )
    return await list_requests(session, collection_id=collection.id)


@router.get("/requests/{request_id}", response_model=RequestResponse)
async def get_request_endpoint(
    request_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    request = await _get_authorized_request(
        session, request_id, current_user.id, Permission.VIEW_WORKSPACE
    )
    return request


@router.patch("/requests/{request_id}", response_model=RequestResponse)
async def update_request_endpoint(
    payload: RequestUpdate,
    request_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    request = await _get_authorized_request(
        session, request_id, current_user.id, Permission.EDIT_REQUESTS
    )
    try:
        return await update_request(session, request=request, payload=payload)
    except ResourceRuleError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/requests/{request_id}", status_code=204)
async def delete_request_endpoint(
    request_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    request = await _get_authorized_request(
        session, request_id, current_user.id, Permission.EDIT_REQUESTS
    )
    await delete_request(session, request=request)


@router.patch("/requests/{request_id}/reorder", response_model=RequestResponse)
async def reorder_request_endpoint(
    payload: ReorderPayload,
    request_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    request = await _get_authorized_request(
        session, request_id, current_user.id, Permission.EDIT_REQUESTS
    )
    return await reorder_request(session, request=request, position=payload.position)


async def _authorize_collection(
    session: AsyncSession, collection: Collection, user_id: uuid.UUID
) -> WorkspaceMember:
    workspace = await session.get(Workspace, collection.workspace_id)
    membership = await session.scalar(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace.id,
            WorkspaceMember.user_id == user_id,
        )
    )
    if membership is None:
        raise HTTPException(status_code=404, detail="Collection not found.")
    return membership


async def _authorized_collection(
    session: AsyncSession,
    collection_id: uuid.UUID,
    user_id: uuid.UUID,
    permission: Permission,
) -> Collection:
    try:
        collection = await get_collection(session, collection_id)
    except ResourceRuleError as exc:
        raise resource_not_found(exc) from exc
    membership = await _authorize_collection(session, collection, user_id)
    from app.core.permissions import role_has_permission
    from app.models.workspace import WorkspaceRole

    if not role_has_permission(WorkspaceRole(membership.role), permission):
        raise HTTPException(
            status_code=403, detail="You do not have permission to perform this action."
        )
    return collection


async def _get_authorized_folder(
    session: AsyncSession,
    folder_id: uuid.UUID,
    user_id: uuid.UUID,
    permission: Permission,
) -> Folder:
    try:
        folder = await get_folder(session, folder_id)
    except ResourceRuleError as exc:
        raise resource_not_found(exc) from exc
    collection = await get_collection(session, folder.collection_id)
    await _authorized_collection(session, collection.id, user_id, permission)
    return folder


async def _get_authorized_request(
    session: AsyncSession,
    request_id: uuid.UUID,
    user_id: uuid.UUID,
    permission: Permission,
) -> APIRequest:
    try:
        request = await get_request(session, request_id)
    except ResourceRuleError as exc:
        raise resource_not_found(exc) from exc
    collection = await get_collection(session, request.collection_id)
    await _authorized_collection(session, collection.id, user_id, permission)
    return request
