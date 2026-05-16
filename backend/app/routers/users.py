from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import create_access_token, get_current_user, require_role
from app.models.user import User
from app.schemas.users import (
    CreateUserRequest,
    SwitchUserRequest,
    SetPinRequest,
    UpdateUserRequest,
    UserResponse,
)
from app.services import users as users_service

router = APIRouter()


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
    return await users_service.create_user(db, data, current_user.family_id)


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
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "admin" and current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Cannot update other users")
    if current_user.role != "admin" and data.role is not None:
        raise HTTPException(status_code=403, detail="Cannot change role")
    user = await users_service.update_user(db, user_id, data, current_user.family_id)
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
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "admin" and current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Cannot set pin for other users")
    user = await users_service.set_pin(db, user_id, data.pin, current_user.family_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.post("/switch")
async def switch_user(
    data: SwitchUserRequest,
    current_user: User = Depends(require_role("admin")),
):
    token = create_access_token(data.user_id)
    return {"token": token}
