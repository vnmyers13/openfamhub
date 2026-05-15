from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_users():
    return {"users": []}


@router.post("/")
async def create_user():
    return {"user": None}


@router.get("/{user_id}")
async def get_user(user_id: str):
    return {"user": None}


@router.patch("/{user_id}")
async def update_user(user_id: str):
    return {"user": None}


@router.delete("/{user_id}")
async def delete_user(user_id: str):
    return {"ok": True}


@router.post("/{user_id}/pin")
async def set_pin(user_id: str):
    return {"ok": True}


@router.post("/switch")
async def switch_user():
    return {"token": None}
