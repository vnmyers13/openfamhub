from fastapi.testclient import TestClient
from app.main import app
from app.core.security import get_current_user

client = TestClient(app)


def override_get_current_user():
    return {"sub": "test-user-id", "role": "admin"}


app.dependency_overrides[get_current_user] = override_get_current_user


# ─── Dietary Tag Tests ──────────────────────────────────────────────────────

def test_create_dietary_tag():
    response = client.post(
        "/api/meals/dietary-tags",
        json={
            "name": "Vegetarian",
            "color_hex": "#4ade80",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "vegetarian"
    assert data["color_hex"] == "#4ade80"
    tag_id = data["id"]

    # Verify it appears in list
    response = client.get("/api/meals/dietary-tags")
    assert response.status_code == 200
    tags = response.json()
    assert any(t["id"] == tag_id for t in tags)


def test_create_duplicate_tag_fails():
    response = client.post(
        "/api/meals/dietary-tags",
        json={
            "name": "Gluten-Free",
            "color_hex": "#60a5fa",
        },
    )
    assert response.status_code == 200
    tag_id = response.json()["id"]

    # Duplicate should fail
    response = client.post(
        "/api/meals/dietary-tags",
        json={
            "name": "Gluten-Free",
            "color_hex": "#ff0000",
        },
    )
    assert response.status_code == 400


def test_update_dietary_tag():
    response = client.post(
        "/api/meals/dietary-tags",
        json={
            "name": "Nut-Free",
            "color_hex": "#fbbf24",
        },
    )
    tag_id = response.json()["id"]

    response = client.patch(
        f"/api/meals/dietary-tags/{tag_id}",
        json={"color_hex": "#f59e0b"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["color_hex"] == "#f59e0b"


def test_delete_dietary_tag():
    response = client.post(
        "/api/meals/dietary-tags",
        json={
            "name": "Dairy-Free",
            "color_hex": "#a78bfa",
        },
    )
    tag_id = response.json()["id"]

    response = client.delete(f"/api/meals/dietary-tags/{tag_id}")
    assert response.status_code == 200
    assert response.json()["ok"] is True

    response = client.get("/api/meals/dietary-tags")
    assert response.status_code == 200
    assert not any(t["id"] == tag_id for t in response.json())


# ─── Recipe Tests ───────────────────────────────────────────────────────────

def test_create_recipe_from_text():
    response = client.post(
        "/api/meals/recipes",
        json={
            "title": "Test Salad",
            "content_text": "Test Salad\n\nIngredients:\n1 cup lettuce\n2 tomatoes\n\nInstructions:\n1. Wash lettuce\n2. Chop tomatoes\n3. Combine",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Test Salad"
    assert data["ingredients_raw"] is not None
    assert "lettuce" in data["ingredients_raw"]


def test_recipe_filter_by_search():
    response = client.post(
        "/api/meals/recipes",
        json={
            "title": "Pasta Primavera",
            "content_text": "Pasta Primavera\n\nIngredients:\n2 cups pasta\n1 cup bell peppers\n\nInstructions:\n1. Cook pasta\n2. Saute vegetables\n3. Combine",
        },
    )
    recipe_id = response.json()["id"]

    response = client.get("/api/meals/recipes?search=pasta")
    assert response.status_code == 200
    recipes = response.json()
    assert any(r["id"] == recipe_id for r in recipes)


# ─── Meal Plan Tests ────────────────────────────────────────────────────────

def test_create_meal_plan():
    response = client.post(
        "/api/meals/plans",
        json={
            "meal_type": "dinner",
            "date": "2026-06-15",
            "title": "Grilled Chicken",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Grilled Chicken"
    assert data["meal_type"] == "dinner"
    assert data["date"] == "2026-06-15"


def test_get_meal_plan_week():
    from datetime import datetime, timezone, timedelta

    today = datetime.now(timezone.utc).date()
    monday = today - timedelta(days=today.weekday())

    # Create a meal plan for this Monday
    client.post(
        "/api/meals/plans",
        json={
            "meal_type": "breakfast",
            "date": str(monday),
            "title": "Pancakes",
        },
    )

    response = client.get(f"/api/meals/plans?week_start={monday}")
    assert response.status_code == 200
    data = response.json()
    assert "week_start" in data
    assert "week_end" in data
    assert "meals" in data
    assert len(data["meals"]) >= 1


# ─── Shopping List Tests ────────────────────────────────────────────────────

def test_add_shopping_item():
    response = client.post(
        "/api/meals/shopping-list",
        json={
            "item": "Olive Oil",
            "quantity": "1 bottle",
            "is_persistent": True,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["item"] == "Olive Oil"
    assert data["is_persistent"] is True
    assert data["source"] == "manual"


def test_shopping_item_check():
    response = client.post(
        "/api/meals/shopping-list",
        json={
            "item": "Garlic",
            "quantity": "1 bulb",
        },
    )
    assert response.status_code == 200
    item_id = response.json()["id"]

    response = client.patch(
        f"/api/meals/shopping-list/{item_id}",
        json={"is_checked": True},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["is_checked"] is True
    assert data["checked_at"] is not None

    response = client.patch(
        f"/api/meals/shopping-list/{item_id}",
        json={"is_checked": False},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["is_checked"] is False
