"""Books (Phase 8): everyone's reading lists and the family library.

- GET /books?shelf=mine|family|everyone. Everyone in the family can see
  everyone's lists ("what's Kid reading?"); viewers can't change anything.
- Personal books are changed by their owner or an admin. Library books
  (owner_id null) can be picked up by anyone: moving one to "reading" or
  "finished" makes you its reader. Editing or removing a library book is
  for whoever added it, or an admin. (v0.29's UI called shared-library
  writes its backend never had.)
- Finishing a book credits its reader BOOK_POINTS once ever, as a ledger
  row keyed by book and reader, so finishing it again can't pay twice.
"""
from datetime import datetime, timezone
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.events import queue_event
from app.core.security import get_current_user
from app.models.chores import PointsEntry
from app.models.family_info import Book
from app.models.user import User
from app.schemas.family_info import BookCreate, BookResponse, BookUpdate
from app.services import rewards as rewards_svc

router = APIRouter()

BOOK_POINTS = 50


def to_book(b: Book, awarded: bool = False) -> BookResponse:
    return BookResponse(id=b.id, title=b.title, author=b.author, notes=b.notes, status=b.status, owner_id=b.owner_id,
                        reader_id=b.reader_id, finished_at=b.finished_at, added_by=b.added_by, points_awarded=awarded)


def deny_viewers(user: User) -> None:
    if user.role == "viewer":
        raise HTTPException(status_code=403, detail="Viewers can't change books")


async def load_book(db: AsyncSession, user: User, book_id: str) -> Book:
    book = await db.get(Book, book_id)
    if book is None or book.family_id != user.family_id:
        raise HTTPException(status_code=404, detail="Book not found")
    return book


def can_edit(book: Book, user: User) -> bool:
    if user.role == "admin":
        return True
    return book.owner_id == user.id if book.owner_id else book.added_by == user.id


async def set_status(db: AsyncSession, book: Book, status: str, user: User) -> bool:
    """Apply a status change; returns True if it earned points."""
    if book.owner_id is None and status != "want_to_read":
        book.reader_id = user.id  # picking up a library book
    elif book.owner_id is None:
        book.reader_id = None  # back on the shelf
    else:
        book.reader_id = book.owner_id
    book.status = status
    book.finished_at = datetime.now(timezone.utc) if status == "finished" else None
    if status != "finished" or not book.reader_id:
        return False
    reader = await db.get(User, book.reader_id)
    if reader is None or reader.role == "viewer":
        return False
    source_id = f"{book.id}:{book.reader_id}"
    paid = (await db.execute(
        select(func.count()).select_from(PointsEntry)
        .where(PointsEntry.source_type == "book", PointsEntry.source_id == source_id)
    )).scalar()
    if paid:
        return False
    db.add(PointsEntry(family_id=book.family_id, user_id=book.reader_id, delta=BOOK_POINTS,
                       reason=f"Finished reading: {book.title}", source_type="book", source_id=source_id,
                       created_at=datetime.now(timezone.utc)))
    await db.flush()
    await rewards_svc.award_badges(db, book.family_id, book.reader_id)
    queue_event(db, "rewards_updated", {})
    return True


@router.get("", response_model=List[BookResponse])
async def list_books(shelf: Literal["mine", "family", "everyone"] = "everyone", user_id: Optional[str] = None,
                     db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    query = select(Book).where(Book.family_id == user.family_id)
    if shelf == "mine":
        query = query.where(Book.owner_id == (user_id or user.id))
    elif shelf == "family":
        query = query.where(Book.owner_id.is_(None))
    rows = (await db.execute(query)).scalars().all()
    order = {"reading": 0, "want_to_read": 1, "finished": 2}
    return [to_book(b) for b in sorted(rows, key=lambda b: (order.get(b.status, 9), b.title.lower()))]


@router.post("", response_model=BookResponse, status_code=201)
async def add_book(data: BookCreate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    deny_viewers(user)
    book = Book(family_id=user.family_id, owner_id=user.id if data.shelf == "mine" else None, title=data.title,
                author=(data.author or "").strip() or None, notes=data.notes, status="want_to_read", added_by=user.id)
    db.add(book)
    await db.flush()
    awarded = await set_status(db, book, data.status, user) if data.status != "want_to_read" else False
    await db.flush()
    queue_event(db, "books_updated", {})
    return to_book(book, awarded)


@router.patch("/{book_id}", response_model=BookResponse)
async def update_book(book_id: str, data: BookUpdate, db: AsyncSession = Depends(get_db),
                      user: User = Depends(get_current_user)):
    deny_viewers(user)
    book = await load_book(db, user, book_id)
    details = {k: v for k, v in data.model_dump(exclude_unset=True).items() if k != "status"}
    if details and not can_edit(book, user):
        raise HTTPException(status_code=403, detail="Only whoever added it (or an admin) can change its details")
    if data.status is not None and book.owner_id is not None and book.owner_id != user.id and user.role != "admin":
        raise HTTPException(status_code=403, detail="That's on someone else's list")
    for key, value in details.items():
        if key == "title" and value is None:
            continue
        if key == "author":
            value = (value or "").strip() or None
        setattr(book, key, value)
    awarded = False
    if data.status is not None and data.status != book.status:
        awarded = await set_status(db, book, data.status, user)
    await db.flush()
    queue_event(db, "books_updated", {})
    return to_book(book, awarded)


@router.delete("/{book_id}")
async def delete_book(book_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    deny_viewers(user)
    book = await load_book(db, user, book_id)
    if not can_edit(book, user):
        raise HTTPException(status_code=403, detail="Only whoever added it (or an admin) can remove it")
    await db.delete(book)  # points already earned stay in the ledger
    await db.flush()
    queue_event(db, "books_updated", {})
    return {"message": "Removed"}
