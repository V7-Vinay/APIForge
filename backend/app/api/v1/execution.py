import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.api.workspace_dependencies import (
    authorize_request,
    authorize_execution_history,
)
from app.core.database import get_db
from app.core.permissions import Permission
from app.core.errors import ResourceNotFoundError, ForbiddenError
from app.models.collection import Collection
from app.models.environment import Environment
from app.models.execution_history import ExecutionHistory
from app.models.user import User
from app.models.workspace_member import WorkspaceMember
from app.schemas.execution import ExecuteRequest, ExecutionResponse
from app.schemas.execution_history import ExecutionHistoryResponse
from app.services.execution import (
    ExecutionRuleError,
    execute_request,
    record_execution_history,
)

router = APIRouter(tags=["execution"])


@router.post("/requests/{request_id}/execute", response_model=ExecutionResponse)
async def execute_request_endpoint(
    payload: ExecuteRequest,
    request = Depends(authorize_request(Permission.EXECUTE_REQUESTS)),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    environment = None
    if payload.environment_id is not None:
        environment = await session.get(Environment, payload.environment_id)
        if environment is None:
            raise ResourceNotFoundError("Environment not found.")
        collection = await session.get(Collection, request.collection_id)
        if environment.workspace_id != collection.workspace_id:
            raise ForbiddenError(
                "The selected environment does not belong to the request workspace."
            )
        membership = await session.scalar(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == environment.workspace_id,
                WorkspaceMember.user_id == current_user.id,
            )
        )
        if membership is None:
            raise ResourceNotFoundError("Environment not found.")

    collection = await session.get(Collection, request.collection_id)
    try:
        result = await execute_request(
            session,
            request=request,
            environment=environment,
            workspace_id=collection.workspace_id,
            user_id=current_user.id,
        )
    except ExecutionRuleError as exc:
        await record_execution_history(
            session,
            request=request,
            workspace_id=collection.workspace_id,
            user_id=current_user.id,
            environment=environment,
            result={
                "success": False,
                "method": request.method,
                "url": request.url,
                "status_code": None,
                "headers": {},
                "body": None,
                "content_type": None,
                "response_size_bytes": 0,
                "duration_ms": None,
                "error_code": exc.code,
                "error_message": str(exc),
            },
        )
        return ExecutionResponse(
            success=False,
            error_code=exc.code,
            error_message=str(exc),
        )
    except Exception:
        await record_execution_history(
            session,
            request=request,
            workspace_id=collection.workspace_id,
            user_id=current_user.id,
            environment=environment,
            result={
                "success": False,
                "method": request.method,
                "url": request.url,
                "status_code": None,
                "headers": {},
                "body": None,
                "content_type": None,
                "response_size_bytes": 0,
                "duration_ms": None,
                "error_code": "EXECUTION_ERROR",
                "error_message": "The request could not be executed.",
            },
        )
        return ExecutionResponse(
            success=False,
            error_code="EXECUTION_ERROR",
            error_message="The request could not be executed.",
        )
    return ExecutionResponse(**result)


@router.get(
    "/requests/{request_id}/history", response_model=list[ExecutionHistoryResponse]
)
async def list_request_history(
    limit: int = 50,
    request = Depends(authorize_execution_history(Permission.VIEW_HISTORY)),
    session: AsyncSession = Depends(get_db),
):
    limit = max(1, min(limit, 100))
    result = await session.scalars(
        select(ExecutionHistory)
        .where(ExecutionHistory.request_id == request.id)
        .order_by(ExecutionHistory.created_at.desc())
        .limit(limit)
    )
    return list(result)
