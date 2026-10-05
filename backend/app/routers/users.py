from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import PASSWORD_REQUIRED, Auth, get_auth, get_current_user, require_role
from app.models.user import User
from app.schemas.users import (
    CreateUserRequest,
    SetPinRequest,
    UpdateUserRequest,
    UserResponse,
)
from app.services import users as users_service

router = APIRouter()


def _authorize_change(auth: Auth, user_id: str, action: str) -> None:
    """Anyone may change their own profile. Changing someone else's needs an admin
    whose session may do admin actions (password sign-in or recent elevation)."""
    if auth.user.id == user_id:
        return
    if auth.user.role != "admin":
        raise HTTPException(status_code=403, detail=f"Cannot {action} other users")
    if not auth.admin_unlocked:
        raise HTTPException(status_code=403, detail=PASSWORD_REQUIRED)


@router.get("/", response_model=List[UserResponse])
async def list_users(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await users_service.list_users(db, current_user.family_id)


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    data: CreateUserRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    try:
        return await users_service.create_user(db, data, current_user.family_id)
    except users_service.DuplicateNameError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "admin" and current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Cannot view other users")
    user = await users_service.get_user(db, user_id, current_user.family_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    data: UpdateUserRequest,
    db: AsyncSession = Depends(get_db),
    auth: Auth = Depends(get_auth),
):
    _authorize_change(auth, user_id, "update")
    if auth.user.role != "admin" and data.role is not None:
        raise HTTPException(status_code=403, detail="Cannot change role")
    try:
        user = await users_service.update_user(
            db, user_id, data, auth.user.family_id, current_session_id=auth.session.id
        )
    except users_service.DuplicateNameError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.delete("/{user_id}")
async def delete_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    ok = await users_service.delete_user(db, user_id, current_user.family_id)
    if not ok:
        raise HTTPException(status_code=404, detail="User not found")
    return {"ok": True}


@router.post("/{user_id}/pin", response_model=UserResponse)
async def set_pin(
    user_id: str,
    data: SetPinRequest,
    db: AsyncSession = Depends(get_db),
    auth: Auth = Depends(get_auth),
):
    _authorize_change(auth, user_id, "set the PIN for")
    user = await users_service.set_pin(db, user_id, data.pin, auth.user.family_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user
