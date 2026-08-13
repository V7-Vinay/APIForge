import uuid

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.core.database import get_db
from app.core.permissions import Permission, role_has_permission
from app.core.errors import ResourceNotFoundError, ForbiddenError
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceRole
from app.models.workspace_member import WorkspaceMember
from app.models.collection import Collection
from app.models.folder import Folder
from app.models.api_request import APIRequest
from app.models.environment import Environment


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
        raise ResourceNotFoundError("Workspace not found.")
    return membership


def require_workspace_permission(permission: Permission):
    async def dependency(
        membership: WorkspaceMember = Depends(get_workspace_membership),
    ) -> WorkspaceMember:
        role = WorkspaceRole(membership.role)
        if not role_has_permission(role, permission):
            raise ForbiddenError("You do not have permission to perform this action.")
        return membership

    return dependency


async def get_workspace(
    workspace_id: uuid.UUID,
    membership: WorkspaceMember = Depends(get_workspace_membership),
    session: AsyncSession = Depends(get_db),
) -> Workspace:
    workspace = await session.get(Workspace, workspace_id)
    if workspace is None:
        raise ResourceNotFoundError("Workspace not found.")
    return workspace


def authorize_workspace(permission: Permission):
    async def dependency(
        workspace_id: uuid.UUID,
        current_user: User = Depends(get_current_user),
        session: AsyncSession = Depends(get_db),
    ) -> Workspace:
        membership = await session.scalar(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == current_user.id,
            )
        )
        if membership is None:
            raise ResourceNotFoundError("Workspace not found.")
        if not role_has_permission(WorkspaceRole(membership.role), permission):
            raise ForbiddenError("You do not have permission to perform this action.")
        workspace = await session.get(Workspace, workspace_id)
        if workspace is None:
            raise ResourceNotFoundError("Workspace not found.")
        return workspace
    return dependency


def authorize_collection(permission: Permission):
    async def dependency(
        collection_id: uuid.UUID,
        current_user: User = Depends(get_current_user),
        session: AsyncSession = Depends(get_db),
    ) -> Collection:
        collection = await session.get(Collection, collection_id)
        if collection is None:
            raise ResourceNotFoundError("Collection not found.")
        membership = await session.scalar(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == collection.workspace_id,
                WorkspaceMember.user_id == current_user.id,
            )
        )
        if membership is None:
            raise ResourceNotFoundError("Collection not found.")
        if not role_has_permission(WorkspaceRole(membership.role), permission):
            raise ForbiddenError("You do not have permission to perform this action.")
        return collection
    return dependency


def authorize_folder(permission: Permission):
    async def dependency(
        folder_id: uuid.UUID,
        current_user: User = Depends(get_current_user),
        session: AsyncSession = Depends(get_db),
    ) -> Folder:
        folder = await session.get(Folder, folder_id)
        if folder is None:
            raise ResourceNotFoundError("Folder not found.")
        collection = await session.get(Collection, folder.collection_id)
        if collection is None:
            raise ResourceNotFoundError("Folder not found.")
        membership = await session.scalar(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == collection.workspace_id,
                WorkspaceMember.user_id == current_user.id,
            )
        )
        if membership is None:
            raise ResourceNotFoundError("Folder not found.")
        if not role_has_permission(WorkspaceRole(membership.role), permission):
            raise ForbiddenError("You do not have permission to perform this action.")
        return folder
    return dependency


def authorize_request(permission: Permission):
    async def dependency(
        request_id: uuid.UUID,
        current_user: User = Depends(get_current_user),
        session: AsyncSession = Depends(get_db),
    ) -> APIRequest:
        request = await session.get(APIRequest, request_id)
        if request is None:
            raise ResourceNotFoundError("Request not found.")
        collection = await session.get(Collection, request.collection_id)
        if collection is None:
            raise ResourceNotFoundError("Request not found.")
        membership = await session.scalar(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == collection.workspace_id,
                WorkspaceMember.user_id == current_user.id,
            )
        )
        if membership is None:
            raise ResourceNotFoundError("Request not found.")
        if not role_has_permission(WorkspaceRole(membership.role), permission):
            raise ForbiddenError("You do not have permission to perform this action.")
        return request
    return dependency


def authorize_environment(permission: Permission):
    async def dependency(
        environment_id: uuid.UUID,
        current_user: User = Depends(get_current_user),
        session: AsyncSession = Depends(get_db),
    ) -> Environment:
        environment = await session.get(Environment, environment_id)
        if environment is None:
            raise ResourceNotFoundError("Environment not found.")
        membership = await session.scalar(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == environment.workspace_id,
                WorkspaceMember.user_id == current_user.id,
            )
        )
        if membership is None:
            raise ResourceNotFoundError("Environment not found.")
        if not role_has_permission(WorkspaceRole(membership.role), permission):
            raise ForbiddenError("You do not have permission to perform this action.")
        return environment
    return dependency


def authorize_execution_history(permission: Permission):
    async def dependency(
        request_id: uuid.UUID,
        current_user: User = Depends(get_current_user),
        session: AsyncSession = Depends(get_db),
    ) -> APIRequest:
        request = await session.get(APIRequest, request_id)
        if request is None:
            raise ResourceNotFoundError("Request not found.")
        collection = await session.get(Collection, request.collection_id)
        if collection is None:
            raise ResourceNotFoundError("Request not found.")
        membership = await session.scalar(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == collection.workspace_id,
                WorkspaceMember.user_id == current_user.id,
            )
        )
        if membership is None:
            raise ResourceNotFoundError("Request not found.")
        if not role_has_permission(WorkspaceRole(membership.role), permission):
            raise ForbiddenError("You do not have permission to perform this action.")
        return request
    return dependency


from app.models.environment import EnvironmentVariable

def authorize_variable(permission: Permission):
    async def dependency(
        variable_id: uuid.UUID,
        current_user: User = Depends(get_current_user),
        session: AsyncSession = Depends(get_db),
    ) -> EnvironmentVariable:
        variable = await session.get(EnvironmentVariable, variable_id)
        if variable is None:
            raise ResourceNotFoundError("Variable not found.")
        environment = await session.get(Environment, variable.environment_id)
        if environment is None:
            raise ResourceNotFoundError("Variable not found.")
        membership = await session.scalar(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == environment.workspace_id,
                WorkspaceMember.user_id == current_user.id,
            )
        )
        if membership is None:
            raise ResourceNotFoundError("Variable not found.")
        if not role_has_permission(WorkspaceRole(membership.role), permission):
            raise ForbiddenError("You do not have permission to perform this action.")
        return variable
    return dependency

