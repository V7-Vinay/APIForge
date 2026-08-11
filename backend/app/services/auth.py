import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.models.refresh_token import RefreshToken
from app.models.user import User


class AuthenticationError(Exception):
    pass


class ConflictError(Exception):
    pass


async def register_user(
    session: AsyncSession, *, name: str, email: str, password: str
) -> User:
    normalized = email.strip().lower()
    if await session.scalar(select(User).where(User.email == normalized)):
        raise ConflictError("An account with this email already exists.")
    user = User(
        name=name.strip(), email=normalized, password_hash=hash_password(password)
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def authenticate_user(
    session: AsyncSession, *, email: str, password: str
) -> User:
    user = await session.scalar(select(User).where(User.email == email.strip().lower()))
    if user is None or not verify_password(password, user.password_hash):
        raise AuthenticationError("Invalid email or password.")
    return user


async def issue_token_pair(
    session: AsyncSession, user: User, *, family_id: uuid.UUID | None = None
):
    access = create_access_token(user.id)
    raw_refresh = create_refresh_token()
    session.add(
        RefreshToken(
            user_id=user.id,
            family_id=family_id or uuid.uuid4(),
            token_hash=hash_refresh_token(raw_refresh),
            expires_at=datetime.now(timezone.utc)
            + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
    )
    await session.commit()
    return access, raw_refresh


async def rotate_refresh_token(session: AsyncSession, raw_token: str):
    stored = await session.scalar(
        select(RefreshToken).where(
            RefreshToken.token_hash == hash_refresh_token(raw_token)
        )
    )
    now = datetime.now(timezone.utc)
    if stored is None:
        raise AuthenticationError("Invalid refresh token.")
    if stored.revoked_at is not None:
        await session.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == stored.user_id)
            .values(revoked_at=now)
        )
        await session.commit()
        raise AuthenticationError("Refresh token reuse detected.")
    if stored.expires_at <= now:
        stored.revoked_at = now
        await session.commit()
        raise AuthenticationError("Refresh token expired.")
    user = await session.get(User, stored.user_id)
    if user is None:
        raise AuthenticationError("Invalid refresh token.")
    access = create_access_token(user.id)
    new_raw = create_refresh_token()
    replacement = RefreshToken(
        user_id=user.id,
        family_id=stored.family_id,
        token_hash=hash_refresh_token(new_raw),
        expires_at=now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    session.add(replacement)
    await session.flush()
    stored.revoked_at = now
    stored.replaced_by_id = replacement.id
    await session.commit()
    return user, access, new_raw


async def revoke_refresh_token(session: AsyncSession, raw_token: str | None):
    if not raw_token:
        return
    stored = await session.scalar(
        select(RefreshToken).where(
            RefreshToken.token_hash == hash_refresh_token(raw_token)
        )
    )
    if stored and stored.revoked_at is None:
        stored.revoked_at = datetime.now(timezone.utc)
        await session.commit()
