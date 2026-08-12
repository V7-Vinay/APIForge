import hashlib
import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.invitation import WorkspaceInvitation
from app.models.user import User
from app.models.workspace_member import WorkspaceMember
from app.models.workspace import WorkspaceRole
from app.services.workspaces import WorkspaceConflictError

logger = logging.getLogger("app")


class InvitationNotFoundError(Exception):
    pass


class InvitationExpiredError(Exception):
    pass


class InvitationAcceptedError(Exception):
    pass


class EmailMismatchError(Exception):
    pass


async def create_invitation(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    email: str,
    role: WorkspaceRole,
) -> tuple[WorkspaceInvitation, str]:
    normalized_email = email.strip().lower()

    # Check if already a member
    existing_member = await session.scalar(
        select(WorkspaceMember)
        .join(User, User.id == WorkspaceMember.user_id)
        .where(
            WorkspaceMember.workspace_id == workspace_id,
            User.email == normalized_email,
        )
    )
    if existing_member is not None:
        raise WorkspaceConflictError("User is already a member of this workspace.")

    # Check if duplicate active pending invitation exists
    now = datetime.now(timezone.utc)
    existing_invitation = await session.scalar(
        select(WorkspaceInvitation).where(
            WorkspaceInvitation.workspace_id == workspace_id,
            WorkspaceInvitation.email == normalized_email,
            WorkspaceInvitation.accepted_at == None,
            WorkspaceInvitation.expires_at > now,
        )
    )
    if existing_invitation is not None:
        raise WorkspaceConflictError(
            "A pending invitation already exists for this email."
        )

    # Generate token and token hash
    plaintext_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(plaintext_token.encode()).hexdigest()

    expires_at = now + timedelta(days=settings.INVITATION_EXPIRE_DAYS)

    invitation = WorkspaceInvitation(
        workspace_id=workspace_id,
        email=normalized_email,
        role=role.value,
        token_hash=token_hash,
        expires_at=expires_at,
    )
    session.add(invitation)
    await session.commit()
    await session.refresh(invitation)

    if settings.APP_ENV == "development":
        logger.info(
            f"Invitation created: http://localhost:8000/api/v1/invitations/{plaintext_token}/accept"
        )

    return invitation, plaintext_token


async def accept_invitation(
    session: AsyncSession,
    *,
    token: str,
    current_user: User,
) -> WorkspaceMember:
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    invitation = await session.scalar(
        select(WorkspaceInvitation).where(WorkspaceInvitation.token_hash == token_hash)
    )
    if invitation is None:
        raise InvitationNotFoundError("Invitation not found.")

    if invitation.accepted_at is not None:
        raise InvitationAcceptedError("Invitation has already been accepted.")

    now = datetime.now(timezone.utc)
    if invitation.expires_at <= now:
        raise InvitationExpiredError("Invitation has expired.")

    if current_user.email != invitation.email:
        raise EmailMismatchError("Authenticated email does not match invitation email.")

    # Transactional integrity block
    try:
        member = WorkspaceMember(
            workspace_id=invitation.workspace_id,
            user_id=current_user.id,
            role=invitation.role,
        )
        session.add(member)
        invitation.accepted_at = now
        await session.commit()
        await session.refresh(member)
        return member
    except Exception:
        await session.rollback()
        raise
