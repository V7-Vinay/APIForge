import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.workspace_dependencies import require_workspace_permission
from app.core.database import get_db
from app.core.permissions import Permission
from app.models.audit_log import AuditLog
from app.models.workspace_member import WorkspaceMember
from app.schemas.audit import AuditLogResponse

router = APIRouter(tags=["audit"])


@router.get(
    "/workspaces/{workspace_id}/audit-logs",
    response_model=list[AuditLogResponse],
)
async def list_audit_logs(
    workspace_id: uuid.UUID,
    limit: int = Query(default=50, ge=1, le=100),
    before_id: uuid.UUID | None = None,
    membership: WorkspaceMember = Depends(
        require_workspace_permission(Permission.VIEW_AUDIT_LOGS)
    ),
    session: AsyncSession = Depends(get_db),
):
    query = (
        select(AuditLog)
        .where(AuditLog.workspace_id == workspace_id)
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .limit(limit)
    )
    if before_id is not None:
        cursor = await session.scalar(select(AuditLog.created_at).where(AuditLog.id == before_id))
        if cursor is not None:
            query = query.where(AuditLog.created_at < cursor)
    result = await session.scalars(query)
    return list(result)
