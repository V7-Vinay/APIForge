from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.dependencies import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserResponse
from app.services.auth import (
    AuthenticationError,
    ConflictError,
    authenticate_user,
    issue_token_pair,
    register_user,
    revoke_refresh_token,
    rotate_refresh_token,
)

router = APIRouter(prefix="/auth", tags=["authentication"])


def set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path=f"{settings.API_V1_PREFIX}/auth",
    )


def clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        path=f"{settings.API_V1_PREFIX}/auth",
    )


@router.post("/register", response_model=UserResponse, status_code=201)
async def register(payload: RegisterRequest, session: AsyncSession = Depends(get_db)):
    try:
        return await register_user(
            session,
            name=payload.name,
            email=str(payload.email),
            password=payload.password,
        )
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest, response: Response, session: AsyncSession = Depends(get_db)
):
    try:
        user = await authenticate_user(
            session, email=str(payload.email), password=payload.password
        )
        access, refresh = await issue_token_pair(session, user)
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=401, detail=str(exc), headers={"WWW-Authenticate": "Bearer"}
        ) from exc
    set_refresh_cookie(response, refresh)
    return TokenResponse(
        access_token=access, expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    response: Response,
    refresh_token: str | None = Cookie(
        default=None, alias=settings.REFRESH_COOKIE_NAME
    ),
    session: AsyncSession = Depends(get_db),
):
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Refresh token required.")
    try:
        _, access, new_refresh = await rotate_refresh_token(session, refresh_token)
    except AuthenticationError as exc:
        clear_refresh_cookie(response)
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    set_refresh_cookie(response, new_refresh)
    return TokenResponse(
        access_token=access, expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    refresh_token: str | None = Cookie(
        default=None, alias=settings.REFRESH_COOKIE_NAME
    ),
    session: AsyncSession = Depends(get_db),
):
    await revoke_refresh_token(session, refresh_token)
    clear_refresh_cookie(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=UserResponse)
async def me(current_user=Depends(get_current_user)):
    return current_user
