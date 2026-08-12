import uuid

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.api_request import APIRequest
from app.models.collection import Collection
from app.models.folder import Folder
from app.schemas.resources import (
    CollectionCreate,
    CollectionUpdate,
    FolderCreate,
    FolderUpdate,
    RequestCreate,
    RequestUpdate,
)


class ResourceRuleError(Exception):
    pass


async def _next_position(session: AsyncSession, model, **filters) -> int:
    query = select(func.max(model.position)).filter_by(**filters)
    value = await session.scalar(query)
    return 0 if value is None else value + 1


async def create_collection(
    session: AsyncSession, *, workspace_id: uuid.UUID, payload: CollectionCreate
) -> Collection:
    collection = Collection(
        workspace_id=workspace_id,
        name=payload.name,
        description=payload.description,
        position=await _next_position(session, Collection, workspace_id=workspace_id),
    )
    session.add(collection)
    await session.commit()
    await session.refresh(collection)
    return collection


async def list_collections(
    session: AsyncSession, *, workspace_id: uuid.UUID
) -> list[Collection]:
    result = await session.scalars(
        select(Collection)
        .where(Collection.workspace_id == workspace_id)
        .order_by(Collection.position, Collection.created_at)
    )
    return list(result)


async def get_collection(session: AsyncSession, collection_id: uuid.UUID) -> Collection:
    collection = await session.get(Collection, collection_id)
    if collection is None:
        raise ResourceRuleError("Collection not found.")
    return collection


async def update_collection(
    session: AsyncSession, *, collection: Collection, payload: CollectionUpdate
) -> Collection:
    if payload.name is not None:
        collection.name = payload.name
    if payload.description is not None:
        collection.description = payload.description
    await session.commit()
    await session.refresh(collection)
    return collection


async def delete_collection(session: AsyncSession, *, collection: Collection) -> None:
    await session.delete(collection)
    await session.commit()


async def reorder_collection(
    session: AsyncSession, *, collection: Collection, position: int
) -> Collection:
    collection.position = position
    await session.commit()
    await session.refresh(collection)
    return collection


async def create_folder(
    session: AsyncSession, *, collection: Collection, payload: FolderCreate
) -> Folder:
    parent = None
    if payload.parent_id is not None:
        parent = await session.get(Folder, payload.parent_id)
        if parent is None or parent.collection_id != collection.id:
            raise ResourceRuleError(
                "The selected parent folder does not belong to this collection."
            )
    folder = Folder(
        collection_id=collection.id,
        parent_id=payload.parent_id,
        name=payload.name,
        position=await _next_position(
            session, Folder, collection_id=collection.id, parent_id=payload.parent_id
        ),
    )
    session.add(folder)
    await session.commit()
    await session.refresh(folder)
    return folder


async def list_folders(
    session: AsyncSession, *, collection_id: uuid.UUID
) -> list[Folder]:
    result = await session.scalars(
        select(Folder)
        .where(Folder.collection_id == collection_id)
        .order_by(Folder.position, Folder.created_at)
    )
    return list(result)


async def get_folder(session: AsyncSession, folder_id: uuid.UUID) -> Folder:
    folder = await session.get(Folder, folder_id)
    if folder is None:
        raise ResourceRuleError("Folder not found.")
    return folder


async def _is_descendant(
    session: AsyncSession, folder_id: uuid.UUID, possible_ancestor_id: uuid.UUID
) -> bool:
    current = await session.get(Folder, folder_id)
    visited: set[uuid.UUID] = set()
    while current and current.parent_id:
        if current.id in visited:
            return True
        visited.add(current.id)
        if current.parent_id == possible_ancestor_id:
            return True
        current = await session.get(Folder, current.parent_id)
    return False


async def update_folder(
    session: AsyncSession, *, folder: Folder, payload: FolderUpdate
) -> Folder:
    if payload.name is not None:
        folder.name = payload.name
    if payload.parent_id is not None:
        if payload.parent_id == folder.id:
            raise ResourceRuleError("A folder cannot be its own parent.")
        parent = await session.get(Folder, payload.parent_id)
        if parent is None or parent.collection_id != folder.collection_id:
            raise ResourceRuleError(
                "The selected parent folder does not belong to this collection."
            )
        if await _is_descendant(session, payload.parent_id, folder.id):
            raise ResourceRuleError(
                "A folder cannot be moved below one of its descendants."
            )
        folder.parent_id = payload.parent_id
    else:
        folder.parent_id = None
    await session.commit()
    await session.refresh(folder)
    return folder


async def delete_folder(session: AsyncSession, *, folder: Folder) -> None:
    # Move direct/descendant contents to collection root rather than silently deleting requests.
    result = await session.scalars(select(Folder).where(Folder.parent_id == folder.id))
    for child in result:
        child.parent_id = None
    requests = await session.scalars(
        select(APIRequest).where(APIRequest.folder_id == folder.id)
    )
    for request in requests:
        request.folder_id = None
    await session.delete(folder)
    await session.commit()


async def reorder_folder(
    session: AsyncSession, *, folder: Folder, position: int
) -> Folder:
    folder.position = position
    await session.commit()
    await session.refresh(folder)
    return folder


async def create_request(
    session: AsyncSession, *, collection: Collection, payload: RequestCreate
) -> APIRequest:
    if payload.folder_id is not None:
        folder = await session.get(Folder, payload.folder_id)
        if folder is None or folder.collection_id != collection.id:
            raise ResourceRuleError(
                "The selected folder does not belong to this collection."
            )
    request = APIRequest(
        collection_id=collection.id,
        folder_id=payload.folder_id,
        name=payload.name,
        description=payload.description,
        method=payload.method,
        url=payload.url,
        headers=[item.model_dump() for item in payload.headers],
        query_params=[item.model_dump() for item in payload.query_params],
        body=payload.body,
        auth_config=payload.auth_config.model_dump(),
        position=await _next_position(session, APIRequest, collection_id=collection.id),
    )
    session.add(request)
    await session.commit()
    await session.refresh(request)
    return request


async def list_requests(
    session: AsyncSession, *, collection_id: uuid.UUID
) -> list[APIRequest]:
    result = await session.scalars(
        select(APIRequest)
        .where(APIRequest.collection_id == collection_id)
        .order_by(APIRequest.position, APIRequest.created_at)
    )
    return list(result)


async def get_request(session: AsyncSession, request_id: uuid.UUID) -> APIRequest:
    request = await session.get(APIRequest, request_id)
    if request is None:
        raise ResourceRuleError("Request not found.")
    return request


async def update_request(
    session: AsyncSession, *, request: APIRequest, payload: RequestUpdate
) -> APIRequest:
    if payload.folder_id is not None:
        folder = await session.get(Folder, payload.folder_id)
        if folder is None or folder.collection_id != request.collection_id:
            raise ResourceRuleError(
                "The selected folder does not belong to this collection."
            )
    for field in ("name", "description", "method", "url", "body", "folder_id"):
        value = getattr(payload, field)
        if value is not None:
            setattr(request, field, value)
    if payload.headers is not None:
        request.headers = [item.model_dump() for item in payload.headers]
    if payload.query_params is not None:
        request.query_params = [item.model_dump() for item in payload.query_params]
    if payload.auth_config is not None:
        request.auth_config = payload.auth_config.model_dump()
    await session.commit()
    await session.refresh(request)
    return request


async def delete_request(session: AsyncSession, *, request: APIRequest) -> None:
    await session.delete(request)
    await session.commit()


async def reorder_request(
    session: AsyncSession, *, request: APIRequest, position: int
) -> APIRequest:
    request.position = position
    await session.commit()
    await session.refresh(request)
    return request
