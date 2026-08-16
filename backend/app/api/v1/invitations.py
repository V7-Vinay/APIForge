import uuid
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.api.workspace_dependencies import require_workspace_permission
from app.core.database import get_db
from app.core.permissions import Permission
from app.core.config import settings
from app.models.user import User
from app.models.workspace_member import WorkspaceMember
from app.schemas.invitation import (
    WorkspaceInvitationCreate,
    WorkspaceInvitationResponse,
)
from app.schemas.workspace import WorkspaceMemberResponse
from app.models.workspace import WorkspaceRole
from app.services.invitations import (
    create_invitation,
    accept_invitation,
    InvitationNotFoundError,
    InvitationExpiredError,
    InvitationAcceptedError,
    EmailMismatchError,
)
from app.services.workspaces import WorkspaceConflictError

router = APIRouter(tags=["invitations"])


@router.post(
    "/workspaces/{workspace_id}/invitations",
    response_model=WorkspaceInvitationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_workspace_invitation(
    workspace_id: uuid.UUID,
    payload: WorkspaceInvitationCreate,
    response: Response,
    actor_membership: WorkspaceMember = Depends(
        require_workspace_permission(Permission.MANAGE_MEMBERS)
    ),
    session: AsyncSession = Depends(get_db),
):
    try:
        invitation, plaintext_token = await create_invitation(
            session,
            workspace_id=workspace_id,
            email=payload.email,
            role=payload.role,
        )
        if settings.APP_ENV.lower() in {"development", "test", "testing"}:
            response.headers["X-Debug-Invitation-Token"] = plaintext_token
        return invitation
    except WorkspaceConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc


@router.post(
    "/invitations/{token}/accept",
    response_model=WorkspaceMemberResponse,
    status_code=status.HTTP_200_OK,
)
async def accept_workspace_invitation(
    token: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    try:
        member = await accept_invitation(
            session,
            token=token,
            current_user=current_user,
        )
        # Fetch the user to map WorkspaceMemberResponse correctly
        user = await session.get(User, member.user_id)
        return WorkspaceMemberResponse(
            id=member.id,
            user_id=user.id,
            name=user.name,
            email=user.email,
            role=WorkspaceRole(member.role),
            created_at=member.created_at,
        )
    except InvitationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except (InvitationExpiredError, InvitationAcceptedError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    except EmailMismatchError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)
        ) from exc
    except WorkspaceConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
