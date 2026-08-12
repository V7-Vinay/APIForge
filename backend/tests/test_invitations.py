import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
import pytest

from app.models.invitation import WorkspaceInvitation
from app.models.user import User
from app.models.workspace import WorkspaceRole
from app.models.workspace_member import WorkspaceMember
from app.services.invitations import (
    create_invitation,
    accept_invitation,
    InvitationNotFoundError,
    InvitationExpiredError,
    InvitationAcceptedError,
    EmailMismatchError,
)
from app.services.workspaces import WorkspaceConflictError


@pytest.mark.asyncio
async def test_create_invitation_happy_path():
    session = AsyncMock()
    session.add = MagicMock()
    # Mock checks (member check -> None, pending invitation check -> None)
    session.scalar.side_effect = [None, None]

    workspace_id = uuid.uuid4()
    email = "test_user@example.com"
    role = WorkspaceRole.EDITOR

    invitation, plaintext_token = await create_invitation(
        session, workspace_id=workspace_id, email=email, role=role
    )

    assert invitation is not None
    assert plaintext_token is not None
    assert invitation.email == "test_user@example.com"
    assert invitation.role == "EDITOR"
    assert invitation.workspace_id == workspace_id
    assert invitation.token_hash == hashlib.sha256(plaintext_token.encode()).hexdigest()
    assert invitation.expires_at > datetime.now(timezone.utc)
    assert invitation.accepted_at is None

    session.add.assert_called_once()
    session.commit.assert_called_once()
    session.refresh.assert_called_once_with(invitation)


@pytest.mark.asyncio
async def test_create_invitation_already_member():
    session = AsyncMock()
    # Mock member check to return a member
    session.scalar.side_effect = [WorkspaceMember()]

    with pytest.raises(WorkspaceConflictError) as exc_info:
        await create_invitation(
            session,
            workspace_id=uuid.uuid4(),
            email="already@example.com",
            role=WorkspaceRole.EDITOR,
        )
    assert "already a member" in str(exc_info.value)


@pytest.mark.asyncio
async def test_create_invitation_pending_exists():
    session = AsyncMock()
    # Mock checks (member check -> None, pending invitation check -> existing invitation)
    session.scalar.side_effect = [None, WorkspaceInvitation()]

    with pytest.raises(WorkspaceConflictError) as exc_info:
        await create_invitation(
            session,
            workspace_id=uuid.uuid4(),
            email="pending@example.com",
            role=WorkspaceRole.EDITOR,
        )
    assert "pending invitation already exists" in str(exc_info.value)


@pytest.mark.asyncio
async def test_accept_invitation_happy_path():
    session = AsyncMock()
    session.add = MagicMock()
    user_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    email = "accept_user@example.com"

    current_user = User(id=user_id, email=email, name="Accept User")
    plaintext_token = "some_secure_token"
    token_hash = hashlib.sha256(plaintext_token.encode()).hexdigest()

    invitation = WorkspaceInvitation(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        email=email,
        role=WorkspaceRole.VIEWER.value,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(days=1),
        accepted_at=None,
    )
    session.scalar.return_value = invitation

    member = await accept_invitation(
        session, token=plaintext_token, current_user=current_user
    )

    assert member is not None
    assert member.workspace_id == workspace_id
    assert member.user_id == user_id
    assert member.role == WorkspaceRole.VIEWER.value
    assert invitation.accepted_at is not None

    session.add.assert_called_once()
    session.commit.assert_called_once()
    session.refresh.assert_called_once_with(member)


@pytest.mark.asyncio
async def test_accept_invitation_not_found():
    session = AsyncMock()
    session.scalar.return_value = None

    current_user = User(id=uuid.uuid4(), email="user@example.com", name="User")
    with pytest.raises(InvitationNotFoundError) as exc_info:
        await accept_invitation(
            session, token="unknown_token", current_user=current_user
        )
    assert "not found" in str(exc_info.value)


@pytest.mark.asyncio
async def test_accept_invitation_already_accepted():
    session = AsyncMock()
    email = "user@example.com"
    invitation = WorkspaceInvitation(
        workspace_id=uuid.uuid4(),
        email=email,
        role=WorkspaceRole.VIEWER.value,
        accepted_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(days=1),
    )
    session.scalar.return_value = invitation

    current_user = User(id=uuid.uuid4(), email=email, name="User")
    with pytest.raises(InvitationAcceptedError) as exc_info:
        await accept_invitation(session, token="token", current_user=current_user)
    assert "already been accepted" in str(exc_info.value)


@pytest.mark.asyncio
async def test_accept_invitation_expired():
    session = AsyncMock()
    email = "user@example.com"
    invitation = WorkspaceInvitation(
        workspace_id=uuid.uuid4(),
        email=email,
        role=WorkspaceRole.VIEWER.value,
        accepted_at=None,
        expires_at=datetime.now(timezone.utc) - timedelta(days=1),
    )
    session.scalar.return_value = invitation

    current_user = User(id=uuid.uuid4(), email=email, name="User")
    with pytest.raises(InvitationExpiredError) as exc_info:
        await accept_invitation(session, token="token", current_user=current_user)
    assert "expired" in str(exc_info.value)


@pytest.mark.asyncio
async def test_accept_invitation_email_mismatch():
    session = AsyncMock()
    invitation = WorkspaceInvitation(
        workspace_id=uuid.uuid4(),
        email="alice@example.com",
        role=WorkspaceRole.VIEWER.value,
        accepted_at=None,
        expires_at=datetime.now(timezone.utc) + timedelta(days=1),
    )
    session.scalar.return_value = invitation

    current_user = User(id=uuid.uuid4(), email="bob@example.com", name="Bob")
    with pytest.raises(EmailMismatchError) as exc_info:
        await accept_invitation(session, token="token", current_user=current_user)
    assert "does not match" in str(exc_info.value)


@pytest.mark.asyncio
async def test_accept_invitation_transactional_rollback():
    session = AsyncMock()
    session.add = MagicMock()
    email = "alice@example.com"
    invitation = WorkspaceInvitation(
        workspace_id=uuid.uuid4(),
        email=email,
        role=WorkspaceRole.VIEWER.value,
        accepted_at=None,
        expires_at=datetime.now(timezone.utc) + timedelta(days=1),
    )
    session.scalar.return_value = invitation
    # Force commit to fail
    session.commit.side_effect = Exception("DB error")

    current_user = User(id=uuid.uuid4(), email=email, name="Alice")
    with pytest.raises(Exception) as exc_info:
        await accept_invitation(session, token="token", current_user=current_user)
    assert "DB error" in str(exc_info.value)

    # Verify rollback was executed
    session.rollback.assert_called_once()
