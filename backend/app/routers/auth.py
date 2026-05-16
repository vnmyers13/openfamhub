from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
    get_current_user,
    check_pin_rate_limit,
    record_pin_attempt,
)
from app.models.family import Family
from app.models.user import User
from app.schemas.auth import (
    SetupRequest,
    LoginRequest,
    PinLoginRequest,
    UserResponse,
    SetupStatusResponse,
)

router = APIRouter()


@router.get("/setup/status", response_model=SetupStatusResponse)
async def setup_status(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(func.count(Family.id)))
    count = result.scalar()
    return SetupStatusResponse(setup_complete=count > 0)


@router.post("/setup", response_model=UserResponse)
async def setup(data: SetupRequest, response: Response, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(func.count(Family.id)))
    if result.scalar() > 0:
        raise HTTPException(status_code=400, detail="Setup already completed")

    family = Family(name=data.family_name, timezone=data.timezone)
    db.add(family)
    await db.flush()

    user = User(
        family_id=family.id,
        display_name=data.admin_display_name,
        email=f"admin@{family.id[:8]}.local",
        hashed_password=hash_password(data.admin_password),
        role="admin",
    )
    db.add(user)
    await db.flush()

    token = create_access_token(user.id)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="strict",
        secure=True,
        max_age=2592000,
    )

    return UserResponse.model_validate(user)


@router.post("/login", response_model=UserResponse)
async def login(data: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(User).where(func.lower(User.display_name) == data.display_name.lower())
    )
    user = result.scalar_one_or_none()
    if not user or not user.hashed_password:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token(user.id)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="strict",
        secure=True,
        max_age=2592000,
    )

    user.last_login_at = datetime.now(timezone.utc)
    await db.flush()

    return UserResponse.model_validate(user)


@router.post("/login/pin", response_model=UserResponse)
async def pin_login(data: PinLoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    check_pin_rate_limit(data.user_id)

    result = await db.execute(select(User).where(User.id == data.user_id))
    user = result.scalar_one_or_none()
    if not user or not user.pin_hash:
        record_pin_attempt(data.user_id)
        raise HTTPException(status_code=401, detail="Invalid PIN")

    if not verify_password(data.pin, user.pin_hash):
        record_pin_attempt(data.user_id)
        raise HTTPException(status_code=401, detail="Invalid PIN")

    token = create_access_token(user.id)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="strict",
        secure=True,
        max_age=2592000,
    )

    user.last_login_at = datetime.now(timezone.utc)
    await db.flush()

    return UserResponse.model_validate(user)


@router.post("/logout")
async def logout(response: Response):
    response.set_cookie(key="access_token", value="", httponly=True, samesite="strict", secure=True, max_age=0)
    return {"ok": True}


@router.get("/me", response_model=UserResponse)
async def me(current_user=Depends(get_current_user)):
    return UserResponse.model_validate(current_user)
