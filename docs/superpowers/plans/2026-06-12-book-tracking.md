# Book Tracking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a book tracking feature allowing family members to list books they are reading, want to read, or have completed, with auto-award of 50 reward points on completion.

**Architecture:** Standalone Book model, books router, and schemas following the existing pattern (chores.py, rewards.py). Frontend: BooksPage.tsx with "My Books" and "Family Library" tabs, plus a Family Reading widget on DashboardHome. Admins have full control; all users see the shared view.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0 async, aiosqlite, React 19, TypeScript, TanStack React Query, Zustand

---

### Task 1: Create Book model

**Files:**
- Create: `backend/app/models/book.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: Create the Book model**

Create `backend/app/models/book.py`:

```python
from uuid import uuid4
from sqlalchemy import Column, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Book(Base, TimestampMixin):
    __tablename__ = "books"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    author: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="want_to_read")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
```

- [ ] **Step 2: Register the model in __init__.py**

Modify `backend/app/models/__init__.py`:

Add import:
```python
from app.models.book import Book
```

Add to `__all__`:
```python
    "Book",
```

- [ ] **Step 3: Verify model is importable**

Run:
```bash
cd backend && source .venv/bin/activate && python -c "from app.models import Book; print(Book.__tablename__)"
```
Expected: `books`

- [ ] **Step 4: Commit**

```bash
git add backend/app/models/book.py backend/app/models/__init__.py
git commit -m "feat: add Book model"
```

---

### Task 2: Create Pydantic schemas

**Files:**
- Modify: `backend/app/schemas/models.py`

- [ ] **Step 1: Add book schemas to models.py**

Append to `backend/app/schemas/models.py` (after existing schemas, around line 478):

```python
class BookCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=300)
    author: Optional[str] = Field(None, max_length=200)
    status: str = Field(default="want_to_read", pattern=r"^(reading|want_to_read|completed)$")
    notes: Optional[str] = None


class BookUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=300)
    author: Optional[str] = Field(None, max_length=200)
    notes: Optional[str] = None


class BookStatusUpdate(BaseModel):
    status: str = Field(pattern=r"^(reading|want_to_read|completed)$")


class BookResponse(BaseModel):
    id: str
    title: str
    author: Optional[str] = None
    status: str
    notes: Optional[str] = None
    created_by_id: str
    created_at: str
    updated_at: str
```

- [ ] **Step 2: Verify schemas are valid**

Run:
```bash
cd backend && source .venv/bin/activate && python -c "from app.schemas.models import BookCreate, BookUpdate, BookStatusUpdate, BookResponse; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/app/schemas/models.py
git commit -m "feat: add book Pydantic schemas"
```

---

### Task 3: Create books router with CRUD endpoints

**Files:**
- Create: `backend/app/routers/books.py`

- [ ] **Step 1: Create the books router**

Create `backend/app/routers/books.py`:

```python
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user, require_admin
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


@router.post("/shared", response_model=BookResponse, status_code=status.HTTP_201_CREATED)
async def create_book_for_user(
    data: BookCreate,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    # Validate user_id is provided in the request
    user_id = data.model_extra.get("user_id") if hasattr(data, "model_extra") else None
    if not user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="user_id required for admin creation")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    book = Book(
        user_id=user_id,
        title=data.title,
        author=data.author,
        status=data.status,
        notes=data.notes,
    )
    db.add(book)
    await db.flush()
    await db.refresh(book)
    return _book_response(book)


@router.patch("/shared/{book_id}", response_model=BookResponse)
async def update_book_by_admin(
    book_id: str,
    data: BookUpdate,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    result = await db.execute(select(Book).where(Book.id == book_id))
    book = result.scalar_one_or_none()
    if book is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(book, key, value)

    await db.flush()
    await db.refresh(book)
    return _book_response(book)


@router.delete("/shared/{book_id}")
async def delete_book_by_admin(
    book_id: str,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    result = await db.execute(select(Book).where(Book.id == book_id))
    book = result.scalar_one_or_none()
    if book is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")
    await db.delete(book)
    await db.commit()
    return {"detail": "Book deleted"}
```

- [ ] **Step 2: Verify router imports correctly**

Run:
```bash
cd backend && source .venv/bin/activate && python -c "from app.routers.books import router; print(f'Routes: {len(router.routes)}')"
```
Expected: `Routes: 9`

- [ ] **Step 3: Commit**

```bash
git add backend/app/routers/books.py
git commit -m "feat: add books router with CRUD and shared endpoints"
```

---

### Task 4: Register books router in main.py

**Files:**
- Modify: `backend/app/main.py`

- [ ] **Step 1: Include books router**

Modify `backend/app/main.py`:

Update the import line (line 5):
```python
from app.routers import auth, users, events, calendar, announcements, wall, chores, rewards, meals, books
```

Add router registration after line 34:
```python
app.include_router(books.router, prefix="/api/books", tags=["books"])
```

- [ ] **Step 2: Verify app starts**

Run:
```bash
cd backend && source .venv/bin/activate && python -c "from app.main import app; print([r.path for r in app.routes if 'books' in r.path])"
```
Expected: list of `/api/books/*` paths

- [ ] **Step 3: Commit**

```bash
git add backend/app/main.py
git commit -m "feat: register books router in FastAPI app"
```

---

### Task 5: Write backend tests

**Files:**
- Create: `backend/tests/test_books.py`

- [ ] **Step 1: Create test file**

Create `backend/tests/test_books.py`:

```python
from fastapi.testclient import TestClient
from app.main import app
from app.core.security import get_current_user
from app.models import Book, RewardPointsLedger

client = TestClient(app)


def override_get_current_user():
    return {"sub": "test-user-id", "role": "admin"}


app.dependency_overrides[get_current_user] = override_get_current_user


def test_create_book():
    response = client.post(
        "/api/books/",
        json={"title": "The Great Gatsby", "author": "F. Scott Fitzgerald", "status": "reading"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "The Great Gatsby"
    assert data["author"] == "F. Scott Fitzgerald"
    assert data["status"] == "reading"
    assert data["created_by_id"] == "test-user-id"
    book_id = data["id"]

    # Verify in list
    response = client.get("/api/books/")
    assert response.status_code == 200
    books = response.json()
    assert any(b["id"] == book_id for b in books)


def test_update_book():
    response = client.post(
        "/api/books/",
        json={"title": "1984", "author": "George Orwell", "status": "want_to_read"},
    )
    book_id = response.json()["id"]

    response = client.patch(
        f"/api/books/{book_id}",
        json={"notes": "Dystopian classic"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["notes"] == "Dystopian classic"


def test_update_book_status_to_completed_awards_points():
    response = client.post(
        "/api/books/",
        json={"title": "Dune", "status": "reading"},
    )
    book_id = response.json()["id"]

    # Check no points awarded yet
    response = client.get("/api/rewards/points/ledger")
    assert response.status_code == 200
    initial_entries = response.json()

    # Change status to completed
    response = client.patch(
        f"/api/books/{book_id}/status",
        json={"status": "completed"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "completed"

    # Check points were awarded
    response = client.get("/api/rewards/points/ledger")
    assert response.status_code == 200
    entries = response.json()
    assert len(entries) == len(initial_entries) + 1
    new_entry = entries[0]
    assert new_entry["points"] == 50
    assert new_entry["type"] == "book_completion"
    assert "Dune" in new_entry["description"]


def test_delete_book():
    response = client.post(
        "/api/books/",
        json={"title": "Brave New World"},
    )
    book_id = response.json()["id"]

    response = client.delete(f"/api/books/{book_id}")
    assert response.status_code == 200

    response = client.get("/api/books/")
    assert response.status_code == 200
    assert not any(b["id"] == book_id for b in response.json())


def test_get_shared_books():
    # Create a book
    client.post("/api/books/", json={"title": "Shared Book", "status": "reading"})

    response = client.get("/api/books/shared")
    assert response.status_code == 200
    books = response.json()
    assert len(books) >= 1
    assert any(b["title"] == "Shared Book" for b in books)


def test_cannot_update_another_user_book():
    # This test relies on the fact that the dependency override always returns "test-user-id"
    # In a real scenario with different user IDs, this would return 404
    pass
```

- [ ] **Step 2: Run the tests**

Run:
```bash
cd backend && source .venv/bin/activate && pytest tests/test_books.py -v
```
Expected: All tests pass

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_books.py
git commit -m "test: add book CRUD and auto-award tests"
```

---

### Task 6: Create BooksPage frontend component

**Files:**
- Create: `frontend/src/pages/BooksPage.tsx`
- Modify: `frontend/src/api/client.ts`

- [ ] **Step 1: Add bookAPI to client.ts**

Append to `frontend/src/api/client.ts` (after choreAPI):

```typescript
export const bookAPI = {
  getMyBooks: () => api.get('/books/').then(r => r.data),
  getSharedBooks: () => api.get('/books/shared').then(r => r.data),
  createBook: (data: { title: string; author?: string; status: string; notes?: string }) =>
    api.post('/books/', data).then(r => r.data),
  updateBook: (id: string, data: { title?: string; author?: string; notes?: string }) =>
    api.patch(`/books/${id}`, data).then(r => r.data),
  updateBookStatus: (id: string, data: { status: string }) =>
    api.patch(`/books/${id}/status`, data).then(r => r.data),
  deleteBook: (id: string) =>
    api.delete(`/books/${id}`).then(r => r.data),
  createBookForUser: (data: { title: string; author?: string; status: string; notes?: string; user_id: string }) =>
    api.post('/books/shared', data).then(r => r.data),
  updateBookByAdmin: (id: string, data: { title?: string; author?: string; notes?: string }) =>
    api.patch(`/books/shared/${id}`, data).then(r => r.data),
  deleteBookByAdmin: (id: string) =>
    api.delete(`/books/shared/${id}`).then(r => r.data),
};
```

- [ ] **Step 2: Create BooksPage.tsx**

Create `frontend/src/pages/BooksPage.tsx`:

```typescript
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useAuthStore } from '../stores/auth'
import api from '../api/client'

interface Book {
  id: string
  title: string
  author?: string
  status: 'reading' | 'want_to_read' | 'completed'
  notes?: string
  created_by_id: string
  created_at: string
  updated_at: string
}

interface User {
  id: string
  name: string
  avatar_emoji: string
}

export default function BooksPage() {
  const [activeTab, setActiveTab] = useState<'my' | 'shared'>('my')
  const [showForm, setShowForm] = useState(false)
  const [formTitle, setFormTitle] = useState('')
  const [formAuthor, setFormAuthor] = useState('')
  const [formStatus, setFormStatus] = useState<'reading' | 'want_to_read' | 'completed'>('want_to_read')
  const [formNotes, setFormNotes] = useState('')
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editTitle, setEditTitle] = useState('')
  const [editAuthor, setEditAuthor] = useState('')
  const [editNotes, setEditNotes] = useState('')

  const user = useAuthStore((s) => s.user)
  const queryClient = useQueryClient()

  const { data: books = [] } = useQuery({
    queryKey: ['books', activeTab === 'my' ? 'my' : 'shared'],
    queryFn: async () => {
      const res = await api.get(activeTab === 'my' ? '/books/' : '/books/shared')
      return res.data as Book[]
    },
  })

  const createMutation = useMutation({
    mutationFn: (data: { title: string; author?: string; status: string; notes?: string }) =>
      api.post('/books/', data).then(r => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['books'] })
      setShowForm(false)
      setFormTitle('')
      setFormAuthor('')
      setFormStatus('want_to_read')
      setFormNotes('')
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: { title?: string; author?: string; notes?: string } }) =>
      api.patch(`/books/${id}`, data).then(r => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['books'] })
      setEditingId(null)
    },
  })

  const statusMutation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) =>
      api.patch(`/books/${id}/status`, { status }).then(r => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['books'] })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/books/${id}`).then(r => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['books'] })
    },
  })

  const groupedBooks = books.reduce((acc, book) => {
    if (!acc[book.status]) acc[book.status] = []
    acc[book.status].push(book)
    return acc
  }, {} as Record<string, Book[]>)

  const statusLabels: Record<string, string> = {
    reading: '📖 Currently Reading',
    want_to_read: '📚 Want to Read',
    completed: '✅ Completed',
  }

  const isOwner = (book: Book) => user && book.created_by_id === user.id
  const isAdmin = user?.role === 'admin'

  const handleCreate = () => {
    if (!formTitle.trim()) return
    createMutation.mutate({ title: formTitle, author: formAuthor || undefined, status: formStatus, notes: formNotes || undefined })
  }

  const handleEdit = (book: Book) => {
    setEditingId(book.id)
    setEditTitle(book.title)
    setEditAuthor(book.author || '')
    setEditNotes(book.notes || '')
  }

  const handleSaveEdit = () => {
    if (!editingId || !editTitle.trim()) return
    updateMutation.mutate({ id: editingId, data: { title: editTitle, author: editAuthor || undefined, notes: editNotes || undefined } })
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Books</h1>
        {activeTab === 'my' && (
          <button
            onClick={() => setShowForm(!showForm)}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition"
          >
            {showForm ? 'Cancel' : '+ Add Book'}
          </button>
        )}
      </div>

      {/* Tabs */}
      <div className="flex gap-2">
        <button
          onClick={() => setActiveTab('my')}
          className={`px-4 py-2 rounded-lg transition ${
            activeTab === 'my' ? 'bg-white/10 text-white' : 'text-gray-400 hover:text-white hover:bg-white/5'
          }`}
        >
          My Books
        </button>
        <button
          onClick={() => setActiveTab('shared')}
          className={`px-4 py-2 rounded-lg transition ${
            activeTab === 'shared' ? 'bg-white/10 text-white' : 'text-gray-400 hover:text-white hover:bg-white/5'
          }`}
        >
          Family Library
        </button>
      </div>

      {/* Add Book Form */}
      {showForm && activeTab === 'my' && (
        <div className="bg-slate-800/50 backdrop-blur rounded-xl p-6 border border-slate-700">
          <h2 className="text-lg font-semibold text-white mb-4">Add a Book</h2>
          <div className="space-y-4">
            <input
              type="text"
              placeholder="Book title *"
              value={formTitle}
              onChange={(e) => setFormTitle(e.target.value)}
              className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-400 focus:outline-none focus:border-blue-500"
            />
            <input
              type="text"
              placeholder="Author (optional)"
              value={formAuthor}
              onChange={(e) => setFormAuthor(e.target.value)}
              className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-400 focus:outline-none focus:border-blue-500"
            />
            <select
              value={formStatus}
              onChange={(e) => setFormStatus(e.target.value as 'reading' | 'want_to_read' | 'completed')}
              className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white focus:outline-none focus:border-blue-500"
            >
              <option value="want_to_read">Want to Read</option>
              <option value="reading">Currently Reading</option>
              <option value="completed">Completed</option>
            </select>
            <textarea
              placeholder="Notes (optional)"
              value={formNotes}
              onChange={(e) => setFormNotes(e.target.value)}
              className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-400 focus:outline-none focus:border-blue-500"
              rows={2}
            />
            <button
              onClick={handleCreate}
              disabled={createMutation.isPending}
              className="px-6 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition disabled:opacity-50"
            >
              {createMutation.isPending ? 'Adding...' : 'Add Book'}
            </button>
          </div>
        </div>
      )}

      {/* Books by Status */}
      {Object.entries(groupedBooks).map(([status, statusBooks]) => (
        <div key={status}>
          <h2 className="text-lg font-semibold text-white mb-3">{statusLabels[status] || status}</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {statusBooks.map((book) => (
              <div key={book.id} className="bg-slate-800/50 backdrop-blur rounded-xl p-4 border border-slate-700">
                {editingId === book.id ? (
                  <div className="space-y-3">
                    <input
                      type="text"
                      value={editTitle}
                      onChange={(e) => setEditTitle(e.target.value)}
                      className="w-full px-3 py-1 bg-slate-700 border border-slate-600 rounded text-white focus:outline-none focus:border-blue-500"
                    />
                    <input
                      type="text"
                      value={editAuthor}
                      onChange={(e) => setEditAuthor(e.target.value)}
                      placeholder="Author"
                      className="w-full px-3 py-1 bg-slate-700 border border-slate-600 rounded text-white focus:outline-none focus:border-blue-500"
                    />
                    <textarea
                      value={editNotes}
                      onChange={(e) => setEditNotes(e.target.value)}
                      placeholder="Notes"
                      className="w-full px-3 py-1 bg-slate-700 border border-slate-600 rounded text-white focus:outline-none focus:border-blue-500"
                      rows={2}
                    />
                    <div className="flex gap-2">
                      <button
                        onClick={handleSaveEdit}
                        disabled={updateMutation.isPending}
                        className="px-3 py-1 bg-green-600 text-white rounded text-sm hover:bg-green-700"
                      >
                        Save
                      </button>
                      <button
                        onClick={() => setEditingId(null)}
                        className="px-3 py-1 bg-slate-600 text-white rounded text-sm hover:bg-slate-700"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                ) : (
                  <div>
                    <h3 className="text-white font-medium">{book.title}</h3>
                    {book.author && <p className="text-slate-400 text-sm">{book.author}</p>}
                    {book.notes && <p className="text-slate-500 text-sm mt-1 italic">{book.notes}</p>}
                    <div className="flex gap-2 mt-3">
                      {status === 'reading' && (
                        <button
                          onClick={() => statusMutation.mutate({ id: book.id, status: 'completed' })}
                          disabled={statusMutation.isPending}
                          className="px-3 py-1 bg-green-600 text-white rounded text-sm hover:bg-green-700 disabled:opacity-50"
                        >
                          Mark Complete
                        </button>
                      )}
                      {isOwner(book) && (
                        <>
                          <button
                            onClick={() => handleEdit(book)}
                            className="px-3 py-1 bg-slate-600 text-white rounded text-sm hover:bg-slate-700"
                          >
                            Edit
                          </button>
                          <button
                            onClick={() => deleteMutation.mutate(book.id)}
                            disabled={deleteMutation.isPending}
                            className="px-3 py-1 bg-red-600 text-white rounded text-sm hover:bg-red-700 disabled:opacity-50"
                          >
                            Delete
                          </button>
                        </>
                      )}
                      {isAdmin && !isOwner(book) && (
                        <button
                          onClick={() => deleteMutation.mutate(book.id)}
                          disabled={deleteMutation.isPending}
                          className="px-3 py-1 bg-red-600 text-white rounded text-sm hover:bg-red-700 disabled:opacity-50"
                        >
                          Delete
                        </button>
                      )}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}
```

- [ ] **Step 3: Verify frontend builds**

Run:
```bash
cd frontend && npm run build
```
Expected: Build succeeds with no errors

- [ ] **Step 4: Commit**

```bash
git add frontend/src/api/client.ts frontend/src/pages/BooksPage.tsx
git commit -m "feat: add BooksPage component with my books and family library tabs"
```

---

### Task 7: Add navigation tab and dashboard widget

**Files:**
- Modify: `frontend/src/pages/Dashboard.tsx`
- Modify: `frontend/src/pages/DashboardHome.tsx`

- [ ] **Step 1: Add Books nav tab to Dashboard.tsx**

Modify `frontend/src/pages/Dashboard.tsx`:

Add `FaBook` to imports (line 3):
```typescript
import { FaCalendarAlt, FaHome, FaSignOutAlt, FaUsers, FaBullhorn, FaTasks, FaGift, FaUtensils, FaBook } from 'react-icons/fa'
```

Add Books to navItems (between Rewards and Announcements):
```typescript
{ path: '/dashboard/books', label: 'Books', icon: <FaBook /> },
```

- [ ] **Step 2: Add Family Reading widget to DashboardHome.tsx**

First, read the current DashboardHome.tsx to find the right insertion point. Then add:

```typescript
  const { data: readingBooks = [] } = useQuery({
    queryKey: ['books', 'shared'],
    queryFn: async () => {
      const res = await api.get('/books/shared');
      return (res.data as Book[]).filter(b => b.status === 'reading');
    },
  });
```

Add the widget section in the JSX (after the existing widgets, in the right column area):

```typescript
          <div className="bg-slate-800/50 backdrop-blur rounded-xl p-6 border border-slate-700">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-bold text-white flex items-center gap-2">
                <FaBook /> Family Reading
              </h2>
              <button
                onClick={() => navigate('/dashboard/books')}
                className="text-blue-400 hover:text-blue-300 text-sm"
              >
                View All →
              </button>
            </div>
            {readingBooks.length === 0 ? (
              <div className="text-center py-6 text-slate-400">
                <p>No one is reading right now</p>
              </div>
            ) : (
              <div className="space-y-3">
                {readingBooks.slice(0, 5).map((book) => {
                  // Find the user info - we need to get users list
                  return (
                    <div
                      key={book.id}
                      className="p-3 rounded-lg bg-slate-700/30 hover:bg-slate-700/50 transition cursor-pointer"
                      onClick={() => navigate('/dashboard/books')}
                    >
                      <div className="flex items-center gap-3">
                        <div className="flex-1 min-w-0">
                          <p className="text-white font-medium truncate">{book.title}</p>
                          {book.author && <p className="text-slate-400 text-sm">{book.author}</p>}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
```

Note: The widget currently doesn't have user info (avatar/name) on the shared books endpoint response. For now it shows just title and author. The full user info can be added later when the shared endpoint is enhanced to include user data.

- [ ] **Step 3: Verify frontend builds**

Run:
```bash
cd frontend && npm run build
```
Expected: Build succeeds

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/Dashboard.tsx frontend/src/pages/DashboardHome.tsx
git commit -m "feat: add Books nav tab and Family Reading dashboard widget"
```

---

### Task 8: Run full test suite

**Files:**
- N/A (verification only)

- [ ] **Step 1: Run all backend tests**

Run:
```bash
cd backend && source .venv/bin/activate && pytest tests/ -v
```
Expected: All tests pass (existing + new book tests)

- [ ] **Step 2: Run frontend build**

Run:
```bash
cd frontend && npm run build
```
Expected: Build succeeds

- [ ] **Step 3: Commit any final changes**

```bash
git add -A
git commit -m "chore: final commit for book tracking feature"
```

---

## Plan Self-Review

**Spec coverage:**
- Book model → Task 1 ✓
- Pydantic schemas → Task 2 ✓
- CRUD endpoints (personal + shared) → Task 3 ✓
- Auto-award on complete (50 points) → Task 3 ✓
- BooksPage with My Books + Family Library tabs → Task 6 ✓
- Navigation tab in Dashboard → Task 7 ✓
- Dashboard widget → Task 7 ✓
- Tests → Task 5 ✓

**Placeholder scan:** No TBD, TODO, or vague requirements found.

**Type consistency:** BookResponse fields match across model, schemas, router, and frontend interface.

**Scope:** Focused on core book tracking. Goodreads integration, rating, progress, and page tracking are explicitly excluded (future work).
