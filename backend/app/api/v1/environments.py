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
from app.models.environment import Environment, EnvironmentVariable
from app.models.user import User
from app.models.workspace import Workspace
from app.models.workspace_member import WorkspaceMember
from app.schemas.environments import (
    EnvironmentCreate,
    EnvironmentResponse,
    EnvironmentUpdate,
    ResolveRequest,
    ResolveResponse,
    VariableCreate,
    VariableResponse,
    VariableRevealResponse,
    VariableUpdate,
)
from app.services.environments import (
    EnvironmentRuleError,
    create_environment,
    create_variable,
    delete_environment,
    delete_variable,
    decrypt_value,
    get_environment,
    get_variable,
    list_environments,
    list_variables,
    resolve_variables,
    update_environment,
    update_variable,
)

router = APIRouter(tags=["environments"])


def _error(exc: EnvironmentRuleError) -> HTTPException:
    message = str(exc)
    code = 409 if "already exists" in message else 400
    return HTTPException(status_code=code, detail=message)


async def _authorized_environment(
    session: AsyncSession,
    environment_id: uuid.UUID,
    user_id: uuid.UUID,
    permission: Permission,
) -> Environment:
    environment = await get_environment(session, environment_id)
    membership = await session.scalar(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == environment.workspace_id,
            WorkspaceMember.user_id == user_id,
        )
    )
    if membership is None:
        raise HTTPException(status_code=404, detail="Environment not found.")
    from app.core.permissions import role_has_permission
    from app.models.workspace import WorkspaceRole

    if not role_has_permission(WorkspaceRole(membership.role), permission):
        raise HTTPException(
            status_code=403, detail="You do not have permission to perform this action."
        )
    return environment


async def _authorized_variable(
    session: AsyncSession,
    variable_id: uuid.UUID,
    user_id: uuid.UUID,
    permission: Permission,
) -> EnvironmentVariable:
    variable = await get_variable(session, variable_id)
    await _authorized_environment(session, variable.environment_id, user_id, permission)
    return variable


@router.post(
    "/workspaces/{workspace_id}/environments",
    response_model=EnvironmentResponse,
    status_code=201,
)
async def create_environment_endpoint(
    payload: EnvironmentCreate,
    workspace: Workspace = Depends(get_workspace),
    membership: WorkspaceMember = Depends(
        require_workspace_permission(Permission.MANAGE_COLLECTIONS)
    ),
    session: AsyncSession = Depends(get_db),
):
    try:
        return await create_environment(
            session, workspace_id=workspace.id, payload=payload
        )
    except EnvironmentRuleError as exc:
        raise _error(exc) from exc


@router.get(
    "/workspaces/{workspace_id}/environments", response_model=list[EnvironmentResponse]
)
async def list_environment_endpoint(
    workspace: Workspace = Depends(get_workspace),
    membership: WorkspaceMember = Depends(get_workspace_membership),
    session: AsyncSession = Depends(get_db),
):
    return await list_environments(session, workspace_id=workspace.id)


@router.get("/environments/{environment_id}", response_model=EnvironmentResponse)
async def get_environment_endpoint(
    environment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    return await _authorized_environment(
        session, environment_id, current_user.id, Permission.VIEW_WORKSPACE
    )


@router.patch("/environments/{environment_id}", response_model=EnvironmentResponse)
async def update_environment_endpoint(
    payload: EnvironmentUpdate,
    environment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    environment = await _authorized_environment(
        session, environment_id, current_user.id, Permission.MANAGE_COLLECTIONS
    )
    try:
        return await update_environment(
            session, environment=environment, payload=payload
        )
    except EnvironmentRuleError as exc:
        raise _error(exc) from exc


@router.delete("/environments/{environment_id}", status_code=204)
async def delete_environment_endpoint(
    environment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    environment = await _authorized_environment(
        session, environment_id, current_user.id, Permission.MANAGE_COLLECTIONS
    )
    await delete_environment(session, environment=environment)


@router.post(
    "/environments/{environment_id}/variables",
    response_model=VariableResponse,
    status_code=201,
)
async def create_variable_endpoint(
    payload: VariableCreate,
    environment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    environment = await _authorized_environment(
        session, environment_id, current_user.id, Permission.EDIT_REQUESTS
    )
    try:
        return await create_variable(session, environment=environment, payload=payload)
    except EnvironmentRuleError as exc:
        raise _error(exc) from exc


@router.get(
    "/environments/{environment_id}/variables", response_model=list[VariableResponse]
)
async def list_variable_endpoint(
    environment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    await _authorized_environment(
        session, environment_id, current_user.id, Permission.VIEW_WORKSPACE
    )
    return await list_variables(session, environment_id=environment_id)


@router.get("/environment-variables/{variable_id}", response_model=VariableResponse)
async def get_variable_endpoint(
    variable_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    return await _authorized_variable(
        session, variable_id, current_user.id, Permission.VIEW_WORKSPACE
    )


@router.get(
    "/environment-variables/{variable_id}/reveal", response_model=VariableRevealResponse
)
async def reveal_variable_endpoint(
    variable_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    variable = await _authorized_variable(
        session, variable_id, current_user.id, Permission.EDIT_REQUESTS
    )
    return VariableRevealResponse(
        id=variable.id,
        environment_id=variable.environment_id,
        key=variable.key,
        is_secret=variable.is_secret,
        created_at=variable.created_at,
        updated_at=variable.updated_at,
        value=decrypt_value(variable.value_ciphertext),
    )


@router.patch("/environment-variables/{variable_id}", response_model=VariableResponse)
async def update_variable_endpoint(
    payload: VariableUpdate,
    variable_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    variable = await _authorized_variable(
        session, variable_id, current_user.id, Permission.EDIT_REQUESTS
    )
    try:
        return await update_variable(session, variable=variable, payload=payload)
    except EnvironmentRuleError as exc:
        raise _error(exc) from exc


@router.delete("/environment-variables/{variable_id}", status_code=204)
async def delete_variable_endpoint(
    variable_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    variable = await _authorized_variable(
        session, variable_id, current_user.id, Permission.EDIT_REQUESTS
    )
    await delete_variable(session, variable=variable)


@router.post("/environments/{environment_id}/resolve", response_model=ResolveResponse)
async def resolve_endpoint(
    payload: ResolveRequest,
    environment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    await _authorized_environment(
        session, environment_id, current_user.id, Permission.VIEW_WORKSPACE
    )
    try:
        return ResolveResponse(
            resolved_text=await resolve_variables(
                session,
                environment_id=environment_id,
                text=payload.text,
                reveal_secrets=False,
            )
        )
    except EnvironmentRuleError as exc:
        raise _error(exc) from exc
