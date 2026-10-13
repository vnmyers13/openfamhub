"""To-dos: one-off family tasks with an optional assignee and due date.
No repeat and no points (that's what chores are for)."""
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import case, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.chores import Todo
from app.models.user import User
from app.routers.chores import check_member, deny_viewers
from app.schemas.chores import TodoCreate, TodoResponse, TodoUpdate

router = APIRouter()


def to_response(t: Todo) -> TodoResponse:
    return TodoResponse(id=t.id, title=t.title, notes=t.notes, assigned_to=t.assigned_to, due_date=t.due_date,
                        done=t.completed_at is not None, completed_at=t.completed_at, completed_by=t.completed_by,
                        created_by=t.created_by, created_at=t.created_at)


async def load(db: AsyncSession, user: User, todo_id: str) -> Todo:
    todo = await db.get(Todo, todo_id)
    if todo is None or todo.family_id != user.family_id:
        raise HTTPException(status_code=404, detail="To-do not found")
    return todo


@router.get("", response_model=List[TodoResponse])
async def list_todos(include_done: bool = False, db: AsyncSession = Depends(get_db),
                     user: User = Depends(get_current_user)):
    query = select(Todo).where(Todo.family_id == user.family_id)
    if not include_done:
        query = query.where(Todo.completed_at.is_(None))
    # Dated ones first, soonest first; then undated, oldest first.
    query = query.order_by(case((Todo.due_date.is_(None), 1), else_=0), Todo.due_date, Todo.created_at)
    return [to_response(t) for t in (await db.execute(query)).scalars().all()]


@router.post("", response_model=TodoResponse, status_code=201)
async def create_todo(data: TodoCreate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    deny_viewers(user)
    await check_member(db, user.family_id, data.assigned_to)
    todo = Todo(family_id=user.family_id, title=data.title, notes=data.notes, assigned_to=data.assigned_to,
                due_date=data.due_date, created_by=user.id)
    db.add(todo)
    await db.flush()
    await db.refresh(todo)
    return to_response(todo)


@router.patch("/{todo_id}", response_model=TodoResponse)
async def update_todo(todo_id: str, data: TodoUpdate, db: AsyncSession = Depends(get_db),
                      user: User = Depends(get_current_user)):
    deny_viewers(user)
    todo = await load(db, user, todo_id)
    fields = data.model_dump(exclude_unset=True)
    done = fields.pop("done", None)
    if "assigned_to" in fields:
        await check_member(db, user.family_id, fields["assigned_to"])
    for key, value in fields.items():
        setattr(todo, key, value)
    if done is True and todo.completed_at is None:
        todo.completed_at, todo.completed_by = datetime.now(timezone.utc), user.id
    elif done is False:
        todo.completed_at = todo.completed_by = None
    await db.flush()
    await db.refresh(todo)
    return to_response(todo)


@router.delete("/{todo_id}")
async def delete_todo(todo_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    todo = await load(db, user, todo_id)
    if user.role != "admin" and todo.created_by != user.id:
        raise HTTPException(status_code=403, detail="Only whoever added it (or an admin) can delete it")
    await db.delete(todo)
    await db.flush()
    return {"ok": True}
