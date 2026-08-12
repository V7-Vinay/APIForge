import uuid

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.core.database import get_db
from app.core.permissions import Permission, role_has_permission
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceRole
from app.models.workspace_member import WorkspaceMember


async def get_workspace_membership(
    workspace_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> WorkspaceMember:
    membership = await session.scalar(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == current_user.id,
        )
    )
    if membership is None:
        # Return 404 rather than exposing whether the workspace exists.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found."
        )
    return membership


def require_workspace_permission(permission: Permission):
    async def dependency(
        membership: WorkspaceMember = Depends(get_workspace_membership),
    ) -> WorkspaceMember:
        role = WorkspaceRole(membership.role)
        if not role_has_permission(role, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action.",
            )
        return membership

    return dependency


async def get_workspace(
    workspace_id: uuid.UUID,
    membership: WorkspaceMember = Depends(get_workspace_membership),
    session: AsyncSession = Depends(get_db),
) -> Workspace:
    workspace = await session.get(Workspace, workspace_id)
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found."
        )
    return workspace
