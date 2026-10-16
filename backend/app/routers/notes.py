from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.events import queue_event
from app.core.security import get_current_user
from app.models.media import Media
from app.models.note import NoteBoard
from app.models.user import User
from app.schemas.notes import ImageItem, NoteBoardResponse, NoteBoardUpdate


router = APIRouter()


def response(board: NoteBoard) -> NoteBoardResponse:
    return NoteBoardResponse(id=board.id, title=board.title, items=(board.scene_json or {}).get("items", []), updated_by=board.updated_by)


async def board_for(db: AsyncSession, family_id: str) -> NoteBoard:
    board = (await db.execute(select(NoteBoard).where(NoteBoard.family_id == family_id))).scalar_one_or_none()
    if board is None:
        board = NoteBoard(family_id=family_id, title="Family notes", scene_json={"items": []})
        db.add(board)
        await db.flush()
    return board


@router.get("/board", response_model=NoteBoardResponse)
async def get_board(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    return response(await board_for(db, user.family_id))


@router.put("/board", response_model=NoteBoardResponse)
async def update_board(data: NoteBoardUpdate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    if user.role == "viewer":
        raise HTTPException(status_code=403, detail="Viewers can't edit family notes")
    image_ids = [item.media_id for item in data.items if isinstance(item, ImageItem)]
    if image_ids:
        valid = set((await db.execute(select(Media.id).where(
            Media.id.in_(image_ids), Media.family_id == user.family_id, Media.kind == "photo", Media.status == "ready",
        ))).scalars())
        if valid != set(image_ids):
            raise HTTPException(status_code=422, detail="Board photos must be ready family images")
    board = await board_for(db, user.family_id)
    board.title = data.title
    board.scene_json = {"items": [item.model_dump() for item in data.items]}
    board.updated_by = user.id
    await db.flush()
    queue_event(db, "notes_updated", {})
    return response(board)
