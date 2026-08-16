import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.workspace_dependencies import get_workspace, get_workspace_membership, require_workspace_permission
from app.core.database import get_db
from app.core.permissions import Permission
from app.models.workspace import Workspace
from app.models.workspace_member import WorkspaceMember
from app.schemas.documentation import DocumentationSummary, OpenAPIImportRequest
from app.services.documentation import DocumentationRuleError, generate_openapi, import_openapi
from app.services.collaboration import event, publish_workspace_event
from app.schemas.collaboration import CollaborationEventType

router = APIRouter(tags=["documentation"])


@router.get("/workspaces/{workspace_id}/documentation/openapi.json")
async def export_openapi_endpoint(
    workspace: Workspace = Depends(get_workspace),
    membership: WorkspaceMember = Depends(get_workspace_membership),
    session: AsyncSession = Depends(get_db),
):
    spec = await generate_openapi(session, workspace_id=workspace.id, title=workspace.name)
    return JSONResponse(content=spec, headers={"Content-Disposition": 'attachment; filename="openapi.json"'})


@router.get("/workspaces/{workspace_id}/documentation/summary", response_model=DocumentationSummary)
async def documentation_summary_endpoint(
    workspace: Workspace = Depends(get_workspace),
    membership: WorkspaceMember = Depends(get_workspace_membership),
    session: AsyncSession = Depends(get_db),
):
    spec = await generate_openapi(session, workspace_id=workspace.id, title=workspace.name)
    paths = spec.get("paths", {})
    tags = spec.get("tags", [])
    return DocumentationSummary(
        title=spec["info"]["title"],
        version=spec["info"]["version"],
        collection_count=spec.get("x-apiforge", {}).get("collection_count", len(tags)),
        folder_count=spec.get("x-apiforge", {}).get("folder_count", 0),
        request_count=sum(len([m for m in item if m in {"get", "post", "put", "patch", "delete", "head", "options"}]) for item in paths.values()),
    )


@router.post("/workspaces/{workspace_id}/documentation/import", status_code=201)
async def import_openapi_endpoint(
    payload: OpenAPIImportRequest,
    workspace: Workspace = Depends(get_workspace),
    membership: WorkspaceMember = Depends(require_workspace_permission(Permission.MANAGE_COLLECTIONS)),
    session: AsyncSession = Depends(get_db),
):
    try:
        collection, folder_count, request_count = await import_openapi(
            session,
            workspace_id=workspace.id,
            spec=payload.spec,
            collection_name=payload.collection_name,
        )
    except DocumentationRuleError as exc:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await publish_workspace_event(event(
        event_type=CollaborationEventType.COLLECTION_UPDATED,
        workspace_id=workspace.id,
        actor_id=membership.user_id,
        resource_id=collection.id,
        resource_type="collection",
        payload={"action": "imported", "collection_id": str(collection.id), "request_count": request_count},
    ))
    return {"collection_id": collection.id, "collection_name": collection.name, "folder_count": folder_count, "request_count": request_count}
