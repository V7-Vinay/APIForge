import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.workspace_dependencies import get_workspace, get_workspace_membership
from app.core.database import get_db
from app.models.workspace import Workspace
from app.models.workspace_member import WorkspaceMember
from app.schemas.resources import CollectionResponse, RequestResponse
from app.schemas.search import (
    PaginatedCollectionResponse,
    PaginatedRequestResponse,
    SearchResponse,
)
from app.services.search import (
    paginate_collections,
    paginate_requests,
    search_workspace,
)

router = APIRouter(tags=["search"])


def _pagination_payload(items, meta):
    return {"items": items, **meta}


@router.get("/workspaces/{workspace_id}/search", response_model=SearchResponse)
async def search_endpoint(
    workspace: Workspace = Depends(get_workspace),
    membership: WorkspaceMember = Depends(get_workspace_membership),
    q: str | None = Query(default=None, max_length=200),
    resource_type: str | None = Query(default=None),
    collection_id: uuid.UUID | None = Query(default=None),
    folder_id: uuid.UUID | None = Query(default=None),
    method: str | None = Query(default=None),
    page: int = Query(default=1, ge=1, le=10_000),
    page_size: int = Query(default=20, ge=1, le=100),
    sort_by: str = Query(default="name"),
    sort_order: str = Query(default="asc"),
    session: AsyncSession = Depends(get_db),
):
    try:
        items, meta = await search_workspace(
            session,
            workspace_id=workspace.id,
            query=q,
            resource_type=resource_type,
            collection_id=collection_id,
            folder_id=folder_id,
            method=method,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _pagination_payload(items, meta)


@router.get(
    "/workspaces/{workspace_id}/collections/page",
    response_model=PaginatedCollectionResponse,
)
async def paginated_collections_endpoint(
    workspace: Workspace = Depends(get_workspace),
    membership: WorkspaceMember = Depends(get_workspace_membership),
    q: str | None = Query(default=None, max_length=200),
    page: int = Query(default=1, ge=1, le=10_000),
    page_size: int = Query(default=20, ge=1, le=100),
    sort_by: str = Query(default="position"),
    sort_order: str = Query(default="asc"),
    session: AsyncSession = Depends(get_db),
):
    try:
        items, meta = await paginate_collections(
            session,
            workspace_id=workspace.id,
            page=page,
            page_size=page_size,
            query=q,
            sort_by=sort_by,
            sort_order=sort_order,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _pagination_payload(
        [CollectionResponse.model_validate(x).model_dump() for x in items], meta
    )


@router.get(
    "/workspaces/{workspace_id}/requests/page", response_model=PaginatedRequestResponse
)
async def paginated_requests_endpoint(
    workspace: Workspace = Depends(get_workspace),
    membership: WorkspaceMember = Depends(get_workspace_membership),
    q: str | None = Query(default=None, max_length=200),
    collection_id: uuid.UUID | None = Query(default=None),
    folder_id: uuid.UUID | None = Query(default=None),
    method: str | None = Query(default=None),
    page: int = Query(default=1, ge=1, le=10_000),
    page_size: int = Query(default=20, ge=1, le=100),
    sort_by: str = Query(default="position"),
    sort_order: str = Query(default="asc"),
    session: AsyncSession = Depends(get_db),
):
    try:
        items, meta = await paginate_requests(
            session,
            workspace_id=workspace.id,
            page=page,
            page_size=page_size,
            collection_id=collection_id,
            folder_id=folder_id,
            query=q,
            method=method,
            sort_by=sort_by,
            sort_order=sort_order,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _pagination_payload(
        [RequestResponse.model_validate(x).model_dump() for x in items], meta
    )
