from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import (
    verify_pin, create_access_token, get_current_user, check_pin_rate_limit
)
from app.schemas.models import LoginRequest, TokenResponse, UserResponse, ProfileResponse
from app.models import User

router = APIRouter()


@router.get("/profiles", response_model=list[ProfileResponse])
async def list_profiles(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.is_active == True))  # noqa: E712
    users = result.scalars().all()
    return [
        ProfileResponse(
            id=u.id,
            name=u.name,
            avatar_emoji=u.avatar_emoji,
            is_active=u.is_active,
        )
        for u in users
    ]


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.is_active == True))  # noqa: E712
    users = result.scalars().all()

    target_user = None
    for user in users:
        if verify_pin(req.pin, user.pin_hash):
            target_user = user
            break

    if target_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect PIN",
        )

    if not check_pin_rate_limit(target_user.id):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many attempts. Try again in 60 seconds.",
        )

    from datetime import datetime, timezone
    target_user.last_login_at = datetime.now(timezone.utc).isoformat()
    await db.flush()

    token = create_access_token(target_user.id, target_user.role)
    return TokenResponse(
        access_token=token,
        user=UserResponse(
            id=target_user.id,
            name=target_user.name,
            avatar_emoji=target_user.avatar_emoji,
            role=target_user.role,
            is_active=target_user.is_active,
            last_login_at=target_user.last_login_at,
            created_at=str(target_user.created_at),
            updated_at=str(target_user.updated_at),
        ),
    )


@router.post("/logout")
async def logout(current_user: dict = Depends(get_current_user)):
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    user_id = current_user["sub"]
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return UserResponse(
        id=user.id,
        name=user.name,
        avatar_emoji=user.avatar_emoji,
        role=user.role,
        is_active=user.is_active,
        last_login_at=user.last_login_at,
        created_at=str(user.created_at),
        updated_at=str(user.updated_at),
    )
