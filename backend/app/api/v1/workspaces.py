import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
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
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceRole
from app.models.workspace_member import WorkspaceMember
from app.schemas.workspace import (
    WorkspaceCreate,
    WorkspaceMemberResponse,
    WorkspaceMemberRoleUpdate,
    WorkspaceResponse,
    WorkspaceUpdate,
)
from app.services.workspaces import (
    WorkspaceConflictError,
    WorkspaceRuleError,
    create_workspace,
    delete_workspace,
    list_user_workspaces,
    remove_member,
    update_member_role,
    update_workspace,
)

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


@router.post("", response_model=WorkspaceResponse, status_code=status.HTTP_201_CREATED)
async def create(
    payload: WorkspaceCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    try:
        return await create_workspace(
            session,
            current_user=current_user,
            name=payload.name,
            slug=payload.slug,
        )
    except WorkspaceConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc


@router.get("", response_model=list[WorkspaceResponse])
async def list_workspaces(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    return await list_user_workspaces(session, user_id=current_user.id)


@router.get("/{workspace_id}", response_model=WorkspaceResponse)
async def get_one(workspace: Workspace = Depends(get_workspace)):
    return workspace


@router.patch("/{workspace_id}", response_model=WorkspaceResponse)
async def update(
    payload: WorkspaceUpdate,
    workspace: Workspace = Depends(get_workspace),
    membership: WorkspaceMember = Depends(
        require_workspace_permission(Permission.MANAGE_WORKSPACE)
    ),
    session: AsyncSession = Depends(get_db),
):
    return await update_workspace(session, workspace=workspace, name=payload.name)


@router.delete("/{workspace_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete(
    workspace: Workspace = Depends(get_workspace),
    membership: WorkspaceMember = Depends(
        require_workspace_permission(Permission.MANAGE_WORKSPACE)
    ),
    session: AsyncSession = Depends(get_db),
):
    if membership.role != WorkspaceRole.OWNER.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the owner can delete a workspace.",
        )
    await delete_workspace(session, workspace=workspace)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{workspace_id}/members", response_model=list[WorkspaceMemberResponse])
async def list_members(
    workspace: Workspace = Depends(get_workspace),
    membership: WorkspaceMember = Depends(get_workspace_membership),
    session: AsyncSession = Depends(get_db),
):
    result = await session.execute(
        select(WorkspaceMember, User)
        .join(User, User.id == WorkspaceMember.user_id)
        .where(WorkspaceMember.workspace_id == workspace.id)
        .order_by(WorkspaceMember.created_at.asc())
    )
    return [
        WorkspaceMemberResponse(
            id=member.id,
            user_id=user.id,
            name=user.name,
            email=user.email,
            role=WorkspaceRole(member.role),
            created_at=member.created_at,
        )
        for member, user in result.all()
    ]


@router.patch(
    "/{workspace_id}/members/{user_id}", response_model=WorkspaceMemberResponse
)
async def change_member_role(
    user_id: uuid.UUID,
    payload: WorkspaceMemberRoleUpdate,
    workspace: Workspace = Depends(get_workspace),
    actor_membership: WorkspaceMember = Depends(
        require_workspace_permission(Permission.MANAGE_MEMBERS)
    ),
    session: AsyncSession = Depends(get_db),
):
    if payload.role == WorkspaceRole.OWNER:
        raise HTTPException(
            status_code=400,
            detail="Ownership transfer is not supported in Phase 3.",
        )
    if user_id == workspace.created_by and payload.role != WorkspaceRole.OWNER:
        raise HTTPException(
            status_code=400, detail="The workspace creator remains the owner."
        )
    try:
        member = await update_member_role(
            session,
            workspace=workspace,
            target_user_id=user_id,
            new_role=payload.role,
        )
    except WorkspaceRuleError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    user = await session.get(User, member.user_id)
    return WorkspaceMemberResponse(
        id=member.id,
        user_id=user.id,
        name=user.name,
        email=user.email,
        role=WorkspaceRole(member.role),
        created_at=member.created_at,
    )


@router.delete(
    "/{workspace_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def remove_workspace_member(
    user_id: uuid.UUID,
    workspace: Workspace = Depends(get_workspace),
    actor_membership: WorkspaceMember = Depends(
        require_workspace_permission(Permission.MANAGE_MEMBERS)
    ),
    session: AsyncSession = Depends(get_db),
):
    try:
        await remove_member(session, workspace=workspace, target_user_id=user_id)
    except WorkspaceRuleError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
