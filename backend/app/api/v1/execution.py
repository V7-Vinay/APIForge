import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.core.database import get_db
from app.core.permissions import Permission, role_has_permission
from app.models.api_request import APIRequest
from app.models.collection import Collection
from app.models.environment import Environment
from app.models.user import User
from app.models.workspace import WorkspaceRole
from app.models.workspace_member import WorkspaceMember
from app.schemas.execution import ExecuteRequest, ExecutionResponse
from app.services.execution import ExecutionRuleError, execute_request

router = APIRouter(tags=["execution"])


async def _authorized_request(
    session: AsyncSession, request_id: uuid.UUID, user_id: uuid.UUID
) -> APIRequest:
    request = await session.get(APIRequest, request_id)
    if request is None:
        raise HTTPException(status_code=404, detail="Request not found.")
    collection = await session.get(Collection, request.collection_id)
    if collection is None:
        raise HTTPException(status_code=404, detail="Request not found.")
    membership = await session.scalar(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == collection.workspace_id,
            WorkspaceMember.user_id == user_id,
        )
    )
    if membership is None:
        raise HTTPException(status_code=404, detail="Request not found.")
    if not role_has_permission(
        WorkspaceRole(membership.role), Permission.EXECUTE_REQUESTS
    ):
        raise HTTPException(
            status_code=403, detail="You do not have permission to execute requests."
        )
    return request


@router.post("/requests/{request_id}/execute", response_model=ExecutionResponse)
async def execute_request_endpoint(
    request_id: uuid.UUID,
    payload: ExecuteRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    request = await _authorized_request(session, request_id, current_user.id)
    environment = None
    if payload.environment_id is not None:
        environment = await session.get(Environment, payload.environment_id)
        if environment is None:
            raise HTTPException(status_code=404, detail="Environment not found.")
        collection = await session.get(Collection, request.collection_id)
        if environment.workspace_id != collection.workspace_id:
            raise HTTPException(
                status_code=403,
                detail="The selected environment does not belong to the request workspace.",
            )
        membership = await session.scalar(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == environment.workspace_id,
                WorkspaceMember.user_id == current_user.id,
            )
        )
        if membership is None:
            raise HTTPException(status_code=404, detail="Environment not found.")

    try:
        result = await execute_request(
            session, request=request, environment=environment
        )
    except ExecutionRuleError as exc:
        return ExecutionResponse(
            success=False,
            error_code=exc.code,
            error_message=str(exc),
        )
    except Exception:
        # Never leak upstream/client internals to API consumers.
        return ExecutionResponse(
            success=False,
            error_code="EXECUTION_ERROR",
            error_message="The request could not be executed.",
        )
    return ExecutionResponse(**result)
