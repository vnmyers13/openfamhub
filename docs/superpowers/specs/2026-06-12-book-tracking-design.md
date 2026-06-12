# Book Tracking Feature Design

## Overview

Family members can track books they are reading, want to read, or have completed. Books are personal by default but visible to all in a shared "Family Library" view. Admins have full control over all books. Completing a book auto-awards reward points.

## Data Model

### `Book` model (`backend/app/models/book.py`)

| Field | Type | Nullable | Description |
|---|---|---|---|
| `id` | Text (UUID) | No | Primary key |
| `user_id` | Text (FK → users.id) | No | Owner of the book |
| `title` | Text | No | Book title |
| `author` | Text | Yes | Author name |
| `status` | Text | No | "reading", "want_to_read", or "completed" |
| `notes` | Text | Yes | Optional notes |
| `created_at` | DateTime | No | Auto-set |
| `updated_at` | DateTime | No | Auto-set on update |

Inherits `TimestampMixin`. No soft delete — books are hard-deleted.

### `BookResponse` schema (`backend/app/schemas/models.py`)

```python
class BookResponse(BaseModel):
    id: str
    title: str
    author: Optional[str] = None
    status: str
    notes: Optional[str] = None
    created_by_id: str
    created_at: str
    updated_at: str

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
```

## API Endpoints

### `backend/app/routers/books.py`

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/api/books` | auth | Add a book (personal) |
| GET | `/api/books` | auth | Get current user's books |
| PATCH | `/api/books/{id}` | auth | Update own book (not status) |
| PATCH | `/api/books/{id}/status` | auth | Change status |
| DELETE | `/api/books/{id}` | auth | Delete own book |
| GET | `/api/books/shared` | auth | Get all members' books (shared view) |
| POST | `/api/books/shared` | admin | Add book on behalf of a member |
| PATCH | `/api/books/shared/{id}` | admin | Edit any member's book |
| DELETE | `/api/books/shared/{id}` | admin | Delete any member's book |

### Auto-Award on Complete

When a book's status changes to "completed" via `/api/books/{id}/status`, the endpoint inserts a row into the existing `RewardPointsLedger` table with:
- `user_id`: the book owner
- `points`: 50 (fixed value, configurable via settings)
- `description`: "Completed book: {title}"
- `created_at`: current UTC time

## Frontend

### `frontend/src/pages/BooksPage.tsx`

Standalone page at route `/dashboard/books`.

**Two views with tab toggle:**

1. **My Books** — personal list
   - Add form: title (required), author (optional), status dropdown (default: "want to read"), notes (optional)
   - List of personal books grouped by status
   - Edit/delete buttons (only on own books)
   - "Mark Complete" button on "reading" books → triggers status change + toast

2. **Family Library** — shared view (all users)
   - Grid showing all members' books grouped by status
   - Each card: avatar_emoji, name, title, author, status
   - Members can delete only their own books
   - Admins can delete any book

### Navigation (`frontend/src/pages/Dashboard.tsx`)

Add Books tab to `navItems` array:
```typescript
{ path: '/dashboard/books', label: 'Books', icon: <FaBook /> }
```
Positioned between Rewards and Announcements. Visible to all users.

### Dashboard Widget (`frontend/src/pages/DashboardHome.tsx`)

"Family Reading" section showing cards of all members' "currently reading" books:
- Each card: avatar_emoji, name, book title, author
- Clicking a card navigates to `/dashboard/books`

## Files to Create/Modify

### Create
- `backend/app/models/book.py` — Book model
- `backend/app/routers/books.py` — Book API endpoints
- `frontend/src/pages/BooksPage.tsx` — Books page component

### Modify
- `backend/app/models/__init__.py` — Import and export Book model
- `backend/app/schemas/models.py` — Add BookCreate, BookUpdate, BookStatusUpdate, BookResponse schemas
- `backend/app/main.py` — Include books router
- `frontend/src/pages/Dashboard.tsx` — Add Books nav tab
- `frontend/src/pages/DashboardHome.tsx` — Add Family Reading widget

## Testing

- Backend: pytest tests for all CRUD endpoints + auto-award on status change
- Frontend: manual testing (no existing test framework for React)
