from fastapi import APIRouter

router = APIRouter()


@router.get("/setup/status")
async def setup_status():
    return {"setup_complete": False}


@router.post("/login")
async def login():
    return {"token": None}


@router.post("/logout")
async def logout():
    return {"ok": True}


@router.get("/me")
async def me():
    return {"user": None}


@router.post("/pin/login")
async def pin_login():
    return {"token": None}
