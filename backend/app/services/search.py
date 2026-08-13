import uuid
from math import ceil
from typing import Literal

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.api_request import APIRequest
from app.models.collection import Collection
from app.models.folder import Folder

RESOURCE_TYPES = {"collection", "folder", "request"}
SORT_FIELDS = {"name", "created_at", "updated_at", "position", "method"}


def _text_filter(query: str):
    pattern = f"%{query.strip()}%"
    return pattern


def _pagination(page: int, page_size: int, total: int) -> dict:
    total_pages = ceil(total / page_size) if total else 0
    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_previous": page > 1 and total_pages > 0,
    }


async def search_workspace(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    query: str | None,
    resource_type: str | None,
    collection_id: uuid.UUID | None,
    folder_id: uuid.UUID | None,
    method: str | None,
    page: int,
    page_size: int,
    sort_by: str,
    sort_order: str,
):
    from sqlalchemy import literal, union_all

    if resource_type and resource_type not in RESOURCE_TYPES:
        raise ValueError("Unsupported resource type.")
    if sort_by not in SORT_FIELDS:
        raise ValueError("Unsupported sort field.")
    if sort_order not in {"asc", "desc"}:
        raise ValueError("Unsupported sort order.")

    pattern = _text_filter(query) if query and query.strip() else None
    selects = []

    if resource_type in (None, "collection"):
        stmt = select(
            Collection.id.label("id"),
            literal("collection").label("resource_type"),
            Collection.name.label("name"),
            Collection.description.label("description"),
            Collection.id.label("collection_id"),
            literal(None).label("folder_id"),
            literal(None).label("method"),
            literal(None).label("url"),
            Collection.position.label("position"),
            Collection.created_at.label("created_at"),
            Collection.updated_at.label("updated_at"),
        ).where(Collection.workspace_id == workspace_id)
        if pattern:
            stmt = stmt.where(
                or_(
                    Collection.name.ilike(pattern),
                    Collection.description.ilike(pattern),
                )
            )
        selects.append(stmt)

    if resource_type in (None, "folder"):
        stmt = (
            select(
                Folder.id.label("id"),
                literal("folder").label("resource_type"),
                Folder.name.label("name"),
                literal(None).label("description"),
                Folder.collection_id.label("collection_id"),
                Folder.id.label("folder_id"),
                literal(None).label("method"),
                literal(None).label("url"),
                Folder.position.label("position"),
                Folder.created_at.label("created_at"),
                Folder.updated_at.label("updated_at"),
            )
            .join(Collection, Collection.id == Folder.collection_id)
            .where(Collection.workspace_id == workspace_id)
        )
        if collection_id:
            stmt = stmt.where(Folder.collection_id == collection_id)
        if pattern:
            stmt = stmt.where(Folder.name.ilike(pattern))
        selects.append(stmt)

    if resource_type in (None, "request"):
        stmt = (
            select(
                APIRequest.id.label("id"),
                literal("request").label("resource_type"),
                APIRequest.name.label("name"),
                APIRequest.description.label("description"),
                APIRequest.collection_id.label("collection_id"),
                APIRequest.folder_id.label("folder_id"),
                APIRequest.method.label("method"),
                APIRequest.url.label("url"),
                APIRequest.position.label("position"),
                APIRequest.created_at.label("created_at"),
                APIRequest.updated_at.label("updated_at"),
            )
            .join(Collection, Collection.id == APIRequest.collection_id)
            .where(Collection.workspace_id == workspace_id)
        )
        if collection_id:
            stmt = stmt.where(APIRequest.collection_id == collection_id)
        if folder_id:
            stmt = stmt.where(APIRequest.folder_id == folder_id)
        if method:
            stmt = stmt.where(APIRequest.method == method.upper())
        if pattern:
            stmt = stmt.where(
                or_(
                    APIRequest.name.ilike(pattern),
                    APIRequest.description.ilike(pattern),
                    APIRequest.url.ilike(pattern),
                    APIRequest.method.ilike(pattern),
                )
            )
        selects.append(stmt)

    if not selects:
        return [], _pagination(page, page_size, 0)

    combined = union_all(*selects).subquery("search_results")
    count_stmt = select(func.count()).select_from(combined)
    total = int(await session.scalar(count_stmt) or 0)

    order_column = getattr(combined.c, sort_by)
    order = order_column.desc() if sort_order == "desc" else order_column.asc()
    stmt = (
        select(combined)
        .order_by(order, combined.c.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await session.execute(stmt)).mappings().all()
    items = [dict(row) for row in rows]
    return items, _pagination(page, page_size, total)


async def paginate_collections(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    page: int,
    page_size: int,
    query: str | None,
    sort_by: str,
    sort_order: str,
):
    if sort_by not in {"name", "created_at", "updated_at", "position"}:
        raise ValueError("Unsupported sort field.")
    stmt = select(Collection).where(Collection.workspace_id == workspace_id)
    count_stmt = (
        select(func.count())
        .select_from(Collection)
        .where(Collection.workspace_id == workspace_id)
    )
    if query and query.strip():
        pattern = _text_filter(query)
        condition = or_(
            Collection.name.ilike(pattern), Collection.description.ilike(pattern)
        )
        stmt = stmt.where(condition)
        count_stmt = count_stmt.where(condition)
    column = getattr(Collection, sort_by)
    stmt = (
        stmt.order_by(
            column.desc() if sort_order == "desc" else column.asc(), Collection.id.asc()
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await session.scalars(stmt)).all()
    total = int(await session.scalar(count_stmt) or 0)
    return rows, _pagination(page, page_size, total)


async def paginate_requests(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    page: int,
    page_size: int,
    collection_id: uuid.UUID | None,
    folder_id: uuid.UUID | None,
    query: str | None,
    method: str | None,
    sort_by: str,
    sort_order: str,
):
    allowed_sort = {"name", "created_at", "updated_at", "position", "method", "url"}
    if sort_by not in allowed_sort:
        raise ValueError("Unsupported sort field.")
    stmt = (
        select(APIRequest)
        .join(Collection, Collection.id == APIRequest.collection_id)
        .where(Collection.workspace_id == workspace_id)
    )
    count_stmt = (
        select(func.count())
        .select_from(APIRequest)
        .join(Collection, Collection.id == APIRequest.collection_id)
        .where(Collection.workspace_id == workspace_id)
    )
    if collection_id:
        stmt = stmt.where(APIRequest.collection_id == collection_id)
        count_stmt = count_stmt.where(APIRequest.collection_id == collection_id)
    if folder_id:
        stmt = stmt.where(APIRequest.folder_id == folder_id)
        count_stmt = count_stmt.where(APIRequest.folder_id == folder_id)
    if method:
        condition = APIRequest.method == method.upper()
        stmt = stmt.where(condition)
        count_stmt = count_stmt.where(condition)
    if query and query.strip():
        pattern = _text_filter(query)
        condition = or_(
            APIRequest.name.ilike(pattern),
            APIRequest.description.ilike(pattern),
            APIRequest.url.ilike(pattern),
            APIRequest.method.ilike(pattern),
        )
        stmt = stmt.where(condition)
        count_stmt = count_stmt.where(condition)
    column = getattr(APIRequest, sort_by)
    stmt = (
        stmt.order_by(
            column.desc() if sort_order == "desc" else column.asc(), APIRequest.id.asc()
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await session.scalars(stmt)).all()
    total = int(await session.scalar(count_stmt) or 0)
    return rows, _pagination(page, page_size, total)
