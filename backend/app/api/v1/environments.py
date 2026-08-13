import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.api.workspace_dependencies import (
    authorize_workspace,
    authorize_environment,
    authorize_variable,
)
from app.core.database import get_db
from app.core.permissions import Permission
from app.core.errors import ConflictError, ValidationError
from app.models.environment import Environment, EnvironmentVariable
from app.models.user import User
from app.models.workspace import Workspace
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
    list_environments,
    list_variables,
    resolve_variables,
    update_environment,
    update_variable,
)

router = APIRouter(tags=["environments"])


def _handle_service_error(exc: EnvironmentRuleError):
    message = str(exc)
    if "already exists" in message:
        raise ConflictError(message)
    raise ValidationError(message)


@router.post(
    "/workspaces/{workspace_id}/environments",
    response_model=EnvironmentResponse,
    status_code=201,
)
async def create_environment_endpoint(
    payload: EnvironmentCreate,
    workspace: Workspace = Depends(authorize_workspace(Permission.MANAGE_ENVIRONMENTS)),
    session: AsyncSession = Depends(get_db),
):
    try:
        return await create_environment(
            session, workspace_id=workspace.id, payload=payload
        )
    except EnvironmentRuleError as exc:
        _handle_service_error(exc)


@router.get(
    "/workspaces/{workspace_id}/environments", response_model=list[EnvironmentResponse]
)
async def list_environment_endpoint(
    workspace: Workspace = Depends(authorize_workspace(Permission.VIEW_WORKSPACE)),
    session: AsyncSession = Depends(get_db),
):
    return await list_environments(session, workspace_id=workspace.id)


@router.get("/environments/{environment_id}", response_model=EnvironmentResponse)
async def get_environment_endpoint(
    environment: Environment = Depends(authorize_environment(Permission.VIEW_WORKSPACE)),
):
    return environment


@router.patch("/environments/{environment_id}", response_model=EnvironmentResponse)
async def update_environment_endpoint(
    payload: EnvironmentUpdate,
    environment: Environment = Depends(authorize_environment(Permission.MANAGE_ENVIRONMENTS)),
    session: AsyncSession = Depends(get_db),
):
    try:
        return await update_environment(
            session, environment=environment, payload=payload
        )
    except EnvironmentRuleError as exc:
        _handle_service_error(exc)


@router.delete("/environments/{environment_id}", status_code=204)
async def delete_environment_endpoint(
    environment: Environment = Depends(authorize_environment(Permission.MANAGE_ENVIRONMENTS)),
    session: AsyncSession = Depends(get_db),
):
    await delete_environment(session, environment=environment)


@router.post(
    "/environments/{environment_id}/variables",
    response_model=VariableResponse,
    status_code=201,
)
async def create_variable_endpoint(
    payload: VariableCreate,
    environment: Environment = Depends(authorize_environment(Permission.MANAGE_ENVIRONMENTS)),
    session: AsyncSession = Depends(get_db),
):
    try:
        return await create_variable(session, environment=environment, payload=payload)
    except EnvironmentRuleError as exc:
        _handle_service_error(exc)


@router.get(
    "/environments/{environment_id}/variables", response_model=list[VariableResponse]
)
async def list_variable_endpoint(
    environment: Environment = Depends(authorize_environment(Permission.VIEW_WORKSPACE)),
    session: AsyncSession = Depends(get_db),
):
    return await list_variables(session, environment_id=environment.id)


@router.get("/environment-variables/{variable_id}", response_model=VariableResponse)
async def get_variable_endpoint(
    variable: EnvironmentVariable = Depends(authorize_variable(Permission.VIEW_WORKSPACE)),
):
    return variable


@router.get(
    "/environment-variables/{variable_id}/reveal", response_model=VariableRevealResponse
)
async def reveal_variable_endpoint(
    variable: EnvironmentVariable = Depends(authorize_variable(Permission.MANAGE_ENVIRONMENTS)),
):
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
    variable: EnvironmentVariable = Depends(authorize_variable(Permission.MANAGE_ENVIRONMENTS)),
    session: AsyncSession = Depends(get_db),
):
    try:
        return await update_variable(session, variable=variable, payload=payload)
    except EnvironmentRuleError as exc:
        _handle_service_error(exc)


@router.delete("/environment-variables/{variable_id}", status_code=204)
async def delete_variable_endpoint(
    variable: EnvironmentVariable = Depends(authorize_variable(Permission.MANAGE_ENVIRONMENTS)),
    session: AsyncSession = Depends(get_db),
):
    await delete_variable(session, variable=variable)


@router.post("/environments/{environment_id}/resolve", response_model=ResolveResponse)
async def resolve_endpoint(
    payload: ResolveRequest,
    environment: Environment = Depends(authorize_environment(Permission.VIEW_WORKSPACE)),
    session: AsyncSession = Depends(get_db),
):
    try:
        return ResolveResponse(
            resolved_text=await resolve_variables(
                session,
                environment_id=environment.id,
                text=payload.text,
                reveal_secrets=False,
            )
        )
    except EnvironmentRuleError as exc:
        _handle_service_error(exc)
