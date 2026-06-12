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
    new_entries = response.json()
    assert len(new_entries) > len(initial_entries)
    last_entry = new_entries[-1]
    assert last_entry["points"] == 50
    assert last_entry["type"] == "book_completion"
    assert f"Completed book: Dune" in last_entry["description"]


def test_delete_book():
    response = client.post(
        "/api/books/",
        json={"title": "Brave New World", "status": "want_to_read"},
    )
    book_id = response.json()["id"]

    response = client.delete(f"/api/books/{book_id}")
    assert response.status_code == 200

    response = client.get("/api/books/")
    books = response.json()
    assert not any(b["id"] == book_id for b in books)


def test_get_shared_books():
    # Create a book
    client.post(
        "/api/books/",
        json={"title": "Shared Book", "author": "Jane Doe", "status": "reading"},
    )

    response = client.get("/api/books/shared")
    assert response.status_code == 200
    books = response.json()
    assert len(books) > 0
    assert any(b["title"] == "Shared Book" for b in books)


def test_create_book_validation():
    # Missing title
    response = client.post(
        "/api/books/",
        json={"author": "Unknown", "status": "reading"},
    )
    assert response.status_code == 422

    # Invalid status
    response = client.post(
        "/api/books/",
        json={"title": "Test", "status": "invalid_status"},
    )
    assert response.status_code == 422


def test_update_nonexistent_book():
    response = client.patch(
        "/api/books/nonexistent-id",
        json={"notes": "Test"},
    )
    assert response.status_code == 404
