from datetime import datetime, timedelta, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import (
    ELEVATION_MINUTES,
    Auth,
    clear_login_cookie,
    get_auth,
    hash_password,
    login_throttle,
    start_session,
    verify_password,
)
from app.models.auth import Session
from app.models.family import Family
from app.models.user import User
from app.schemas.auth import (
    ElevateRequest,
    LoginRequest,
    PinLoginRequest,
    ProfileResponse,
    SetupRequest,
    SetupStatusResponse,
    UserResponse,
)

router = APIRouter()


def _me(user: User, session: Session, admin_unlocked: bool) -> UserResponse:
    out = UserResponse.model_validate(user)
    out.auth_method = session.auth_method
    out.admin_unlocked = admin_unlocked
    return out


def _device(request: Request) -> str:
    return request.headers.get("user-agent", "")


@router.get("/setup/status", response_model=SetupStatusResponse)
async def setup_status(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(func.count(Family.id)))
    return SetupStatusResponse(setup_complete=result.scalar() > 0)


@router.post("/setup", response_model=UserResponse)
async def setup(data: SetupRequest, request: Request, response: Response, db: AsyncSession = Depends(get_db)):
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
        pin_hash=hash_password(data.admin_pin) if data.admin_pin else None,
        role="admin",
    )
    db.add(user)
    await db.flush()

    session = await start_session(db, response, user, "password", _device(request))
    return _me(user, session, True)


@router.get("/profiles", response_model=List[ProfileResponse])
async def profiles(db: AsyncSession = Depends(get_db)):
    """Avatars for the sign-in picker. Public by design (the picker is shown before
    sign-in), so it returns nothing beyond what the picker displays."""
    result = await db.execute(
        select(User).where(User.is_deleted == False).order_by(User.display_name)  # noqa: E712
    )
    return [
        ProfileResponse(
            id=u.id,
            display_name=u.display_name,
            color_hex=u.color_hex,
            avatar_type=u.avatar_type,
            avatar_value=u.avatar_value,
            has_pin=bool(u.pin_hash),
        )
        for u in result.scalars().all()
    ]


@router.post("/login", response_model=UserResponse)
async def login(data: LoginRequest, request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    key = f"pw:{data.display_name.strip().lower()}"
    login_throttle.check(key)

    result = await db.execute(
        select(User).where(
            func.lower(User.display_name) == data.display_name.strip().lower(),
            User.is_deleted == False,  # noqa: E712
        )
    )
    user = result.scalars().first()
    if not user or not user.hashed_password or not verify_password(data.password, user.hashed_password):
        login_throttle.fail(key)
        raise HTTPException(status_code=401, detail="Invalid credentials")

    login_throttle.succeed(key)
    user.last_login_at = datetime.now(timezone.utc)
    session = await start_session(db, response, user, "password", _device(request))
    return _me(user, session, True)


@router.post("/login/pin", response_model=UserResponse)
async def pin_login(data: PinLoginRequest, request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    # One user per request (picked from the avatar grid); failures are counted per user.
    key = f"pin:{data.user_id}"
    login_throttle.check(key)

    user = await db.get(User, data.user_id)
    if not user or user.is_deleted or not user.pin_hash or not verify_password(data.pin, user.pin_hash):
        login_throttle.fail(key)
        raise HTTPException(status_code=401, detail="Invalid PIN")

    login_throttle.succeed(key)
    user.last_login_at = datetime.now(timezone.utc)
    session = await start_session(db, response, user, "pin", _device(request))
    return _me(user, session, False)


@router.post("/elevate", response_model=UserResponse)
async def elevate(data: ElevateRequest, auth: Auth = Depends(get_auth)):
    """Confirm the password on a PIN session to unlock admin actions for a while."""
    user, session = auth.user, auth.session
    key = f"pw:{user.display_name.strip().lower()}"
    login_throttle.check(key)
    if not user.hashed_password or not verify_password(data.password, user.hashed_password):
        login_throttle.fail(key)
        raise HTTPException(status_code=401, detail="Incorrect password")
    login_throttle.succeed(key)
    session.elevated_until = datetime.now(timezone.utc) + timedelta(minutes=ELEVATION_MINUTES)
    return _me(user, session, True)


@router.post("/logout")
async def logout(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    """Delete this browser's session (if the cookie is valid) and clear the cookie."""
    token = request.cookies.get("access_token")
    if token:
        try:
            auth = await get_auth(access_token=token, db=db)
            await db.delete(auth.session)
            await db.flush()
        except HTTPException:
            pass
    clear_login_cookie(response)
    return {"ok": True}


@router.get("/me", response_model=UserResponse)
async def me(auth: Auth = Depends(get_auth)):
    return _me(auth.user, auth.session, auth.admin_unlocked)
