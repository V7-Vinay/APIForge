import re
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.workspace import Workspace, WorkspaceRole
from app.models.workspace_member import WorkspaceMember


class WorkspaceConflictError(Exception):
    pass


class WorkspaceRuleError(Exception):
    pass


async def create_workspace(
    session: AsyncSession, *, current_user: User, name: str, slug: str
) -> Workspace:
    normalized_slug = slug.strip().lower()
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", normalized_slug):
        raise WorkspaceConflictError("Invalid workspace slug.")

    existing = await session.scalar(
        select(Workspace).where(Workspace.slug == normalized_slug)
    )
    if existing is not None:
        raise WorkspaceConflictError("A workspace with this slug already exists.")

    workspace = Workspace(
        name=name.strip(),
        slug=normalized_slug,
        created_by=current_user.id,
    )
    session.add(workspace)
    await session.flush()

    session.add(
        WorkspaceMember(
            workspace_id=workspace.id,
            user_id=current_user.id,
            role=WorkspaceRole.OWNER.value,
        )
    )
    await session.commit()
    await session.refresh(workspace)
    return workspace


async def list_user_workspaces(
    session: AsyncSession, *, user_id: uuid.UUID
) -> list[Workspace]:
    result = await session.scalars(
        select(Workspace)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
        .where(WorkspaceMember.user_id == user_id)
        .order_by(Workspace.created_at.desc())
    )
    return list(result)


async def update_workspace(
    session: AsyncSession, *, workspace: Workspace, name: str | None
) -> Workspace:
    if name is not None:
        workspace.name = name.strip()
    await session.commit()
    await session.refresh(workspace)
    return workspace


async def delete_workspace(session: AsyncSession, *, workspace: Workspace) -> None:
    await session.delete(workspace)
    await session.commit()


async def update_member_role(
    session: AsyncSession,
    *,
    workspace: Workspace,
    target_user_id: uuid.UUID,
    new_role: WorkspaceRole,
) -> WorkspaceMember:
    target = await session.scalar(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace.id,
            WorkspaceMember.user_id == target_user_id,
        )
    )
    if target is None:
        raise WorkspaceRuleError("Workspace member not found.")

    if target.role == WorkspaceRole.OWNER.value and new_role != WorkspaceRole.OWNER:
        # Owner role changes are deliberately handled by the service instead of
        # allowing an update that could leave the workspace without an owner.
        owners = await session.scalars(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace.id,
                WorkspaceMember.role == WorkspaceRole.OWNER.value,
            )
        )
        if len(list(owners)) <= 1:
            raise WorkspaceRuleError("A workspace must always have an owner.")

    target.role = new_role.value
    await session.commit()
    await session.refresh(target)
    return target


async def remove_member(
    session: AsyncSession,
    *,
    workspace: Workspace,
    target_user_id: uuid.UUID,
) -> None:
    target = await session.scalar(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace.id,
            WorkspaceMember.user_id == target_user_id,
        )
    )
    if target is None:
        raise WorkspaceRuleError("Workspace member not found.")
    if target.role == WorkspaceRole.OWNER.value:
        raise WorkspaceRuleError("The workspace owner cannot be removed.")
    await session.delete(target)
    await session.commit()
