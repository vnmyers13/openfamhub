import uuid
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.user import User
from app.schemas.users import (
    CreateUserRequest,
    UpdateUserRequest,
    UserResponse,
)


async def list_users(db: AsyncSession, family_id: str) -> list[UserResponse]:
    result = await db.execute(
        select(User).where(User.family_id == family_id, User.is_deleted == False).order_by(User.display_name)
    )
    users = result.scalars().all()
    return [_user_to_response(u) for u in users]


async def create_user(db: AsyncSession, data: CreateUserRequest, family_id: str) -> UserResponse:
    email = data.email or f"user{uuid.uuid4().hex[:8]}@family.local"
    role = data.role or "member"
    user = User(
        family_id=family_id,
        display_name=data.display_name,
        email=email,
        role=role,
        color_hex=data.color_hex or "#4F46E5",
        ui_mode=data.ui_mode or "standard",
    )
    if data.password:
        user.hashed_password = hash_password(data.password)
    if data.pin:
        user.pin_hash = hash_password(data.pin)
    db.add(user)
    await db.flush()
    return _user_to_response(user)


async def get_user(db: AsyncSession, user_id: str, family_id: str) -> UserResponse | None:
    result = await db.execute(
        select(User).where(User.id == user_id, User.family_id == family_id, User.is_deleted == False)
    )
    user = result.scalar_one_or_none()
    if not user:
        return None
    return _user_to_response(user)


async def update_user(db: AsyncSession, user_id: str, data: UpdateUserRequest, family_id: str) -> UserResponse | None:
    result = await db.execute(
        select(User).where(User.id == user_id, User.family_id == family_id, User.is_deleted == False)
    )
    user = result.scalar_one_or_none()
    if not user:
        return None

    updates = {}
    if data.display_name is not None:
        updates["display_name"] = data.display_name
    if data.email is not None:
        updates["email"] = data.email
    if data.role is not None:
        updates["role"] = data.role
    if data.color_hex is not None:
        updates["color_hex"] = data.color_hex
    if data.ui_mode is not None:
        updates["ui_mode"] = data.ui_mode
    if data.password is not None:
        updates["hashed_password"] = hash_password(data.password)
    if data.pin is not None:
        updates["pin_hash"] = hash_password(data.pin)

    if updates:
        for k, v in updates.items():
            setattr(user, k, v)
        await db.flush()

    return _user_to_response(user)


async def delete_user(db: AsyncSession, user_id: str, family_id: str) -> bool:
    result = await db.execute(
        select(User).where(User.id == user_id, User.family_id == family_id, User.is_deleted == False)
    )
    user = result.scalar_one_or_none()
    if not user:
        return False
    user.is_deleted = True
    await db.flush()
    return True


async def set_pin(db: AsyncSession, user_id: str, pin: str, family_id: str) -> UserResponse | None:
    result = await db.execute(
        select(User).where(User.id == user_id, User.family_id == family_id, User.is_deleted == False)
    )
    user = result.scalar_one_or_none()
    if not user:
        return None
    user.pin_hash = hash_password(pin)
    await db.flush()
    return _user_to_response(user)


def _user_to_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        display_name=user.display_name,
        email=user.email if user.email else None,
        role=user.role,
        color_hex=user.color_hex,
        ui_mode=user.ui_mode,
        avatar_type=user.avatar_type,
        avatar_value=user.avatar_value,
        family_id=user.family_id,
        has_password=bool(user.hashed_password),
        has_pin=bool(user.pin_hash),
        last_login_at=user.last_login_at.isoformat() if user.last_login_at else None,
        created_at=user.created_at.isoformat() if user.created_at else None,
    )
