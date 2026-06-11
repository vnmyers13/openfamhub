from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_admin, hash_pin
from app.schemas.models import UserCreate, UserUpdate, UserResponse
from app.models import User

router = APIRouter()


@router.get("/profiles", response_model=list[UserResponse])
async def list_profiles(
    admin: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.is_active == True))  # noqa: E712
    users = result.scalars().all()
    return [
        UserResponse(
            id=u.id,
            name=u.name,
            avatar_emoji=u.avatar_emoji,
            role=u.role,
            is_active=u.is_active,
            last_login_at=u.last_login_at,
            created_at=str(u.created_at),
            updated_at=str(u.updated_at),
        )
        for u in users
    ]


@router.post("/profiles", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_profile(
    req: UserCreate,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    result = await db.execute(select(User).where(User.name == req.name, User.is_active == True))  # noqa: E712
    if result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Name already in use")

    user = User(
        name=req.name,
        avatar_emoji=req.avatar_emoji,
        pin_hash=hash_pin(req.pin),
        role=req.role,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

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


@router.patch("/profiles/{user_id}", response_model=UserResponse)
async def update_profile(
    user_id: str,
    req: UserUpdate,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    update_data = req.model_dump(exclude_unset=True)
    if "pin" in update_data:
        update_data["pin_hash"] = hash_pin(update_data.pop("pin"))

    for key, value in update_data.items():
        setattr(user, key, value)

    await db.flush()
    await db.refresh(user)

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


@router.delete("/profiles/{user_id}")
async def deactivate_profile(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user.is_active = False
    await db.flush()

    return {"message": "Profile deactivated"}
