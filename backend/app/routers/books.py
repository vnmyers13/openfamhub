from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.schemas.models import BookCreate, BookUpdate, BookStatusUpdate, BookResponse
from app.models import Book, RewardPointsLedger, User

router = APIRouter()


def _book_response(book: Book) -> BookResponse:
    return BookResponse(
        id=book.id,
        title=book.title,
        author=book.author,
        status=book.status,
        notes=book.notes,
        created_by_id=book.user_id,
        created_at=str(book.created_at),
        updated_at=str(book.updated_at),
    )


@router.post("/", response_model=BookResponse, status_code=status.HTTP_201_CREATED)
async def create_book(
    data: BookCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    book = Book(
        user_id=current_user["sub"],
        title=data.title,
        author=data.author,
        status=data.status,
        notes=data.notes,
    )
    db.add(book)
    await db.flush()
    await db.refresh(book)
    return _book_response(book)


@router.get("/", response_model=list[BookResponse])
async def get_my_books(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    result = await db.execute(
        select(Book)
        .where(Book.user_id == current_user["sub"])
        .order_by(Book.status, Book.title)
    )
    books = result.scalars().all()
    return [_book_response(b) for b in books]


@router.patch("/{book_id}", response_model=BookResponse)
async def update_book(
    book_id: str,
    data: BookUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    result = await db.execute(select(Book).where(Book.id == book_id, Book.user_id == current_user["sub"]))
    book = result.scalar_one_or_none()
    if book is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(book, key, value)

    await db.flush()
    await db.refresh(book)
    return _book_response(book)


@router.patch("/{book_id}/status", response_model=BookResponse)
async def update_book_status(
    book_id: str,
    data: BookStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    result = await db.execute(select(Book).where(Book.id == book_id, Book.user_id == current_user["sub"]))
    book = result.scalar_one_or_none()
    if book is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")

    old_status = book.status
    book.status = data.status
    await db.flush()
    await db.refresh(book)

    # Auto-award points when status changes to "completed"
    if data.status == "completed" and old_status != "completed":
        ledger = RewardPointsLedger(
            user_id=book.user_id,
            points=50,
            type="book_completion",
            reference_id=book.id,
            description=f"Completed book: {book.title}",
        )
        db.add(ledger)

    await db.commit()
    await db.refresh(book)
    return _book_response(book)


@router.delete("/{book_id}")
async def delete_book(
    book_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    result = await db.execute(select(Book).where(Book.id == book_id, Book.user_id == current_user["sub"]))
    book = result.scalar_one_or_none()
    if book is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")
    await db.delete(book)
    await db.commit()
    return {"detail": "Book deleted"}


# ─── Shared endpoints (all users can read, admin can write) ───


@router.get("/shared", response_model=list[BookResponse])
async def get_shared_books(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    result = await db.execute(
        select(Book, User)
        .join(User, Book.user_id == User.id)
        .order_by(Book.status, User.name, Book.title)
    )
    rows = result.all()
    return [
        BookResponse(
            id=b.id,
            title=b.title,
            author=b.author,
            status=b.status,
            notes=b.notes,
            created_by_id=b.user_id,
            created_at=str(b.created_at),
            updated_at=str(b.updated_at),
        )
        for b, u in rows
    ]
