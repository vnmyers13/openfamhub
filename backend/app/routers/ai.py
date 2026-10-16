from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.calendar_event import CalendarEvent
from app.models.chores import ChoreTemplate, Todo
from app.models.user import User
from app.schemas.ai import DraftRequest, DraftResponse
from app.services import ai

router = APIRouter()


async def _context(db: AsyncSession, user: User) -> dict:
    events = (await db.execute(select(CalendarEvent).where(CalendarEvent.family_id == user.family_id,
        CalendarEvent.is_deleted == False).limit(100))).scalars().all()  # noqa: E712
    chores = (await db.execute(select(ChoreTemplate).where(ChoreTemplate.family_id == user.family_id,
        ChoreTemplate.is_active == True).limit(100))).scalars().all()  # noqa: E712
    todos = (await db.execute(select(Todo).where(Todo.family_id == user.family_id).limit(100))).scalars().all()
    return {"family_id": user.family_id, "user_id": user.id, "role": user.role,
            "events": [{"id": e.id, "title": e.title, "start_dt": e.start_dt.isoformat(), "end_dt": e.end_dt.isoformat()} for e in events],
            "chores": [{"id": c.id, "title": c.title} for c in chores],
            "todos": [{"id": t.id, "title": t.title} for t in todos]}


@router.post("/draft", response_model=DraftResponse, response_model_exclude_none=True)
async def create_draft(data: DraftRequest, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    context = await _context(db, user)
    try:
        result = await ai.draft(data.request, context)
    except ai.Unavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    allowed = {kind: {item["id"] for item in context[f"{kind}s"]} for kind in ("event", "chore", "todo")}
    if result.action.operation == "update" and result.action.target_id not in allowed[result.action.kind]:
        raise HTTPException(status_code=422, detail="The local AI chose an item outside your family context.")
    return result
