"""Phase 9 server side: idempotent replays and conflict detection for offline edits."""
import pytest
from sqlalchemy import func, select

from app.models.meals import ShoppingItem
from tests.test_phase2 import SETUP, _cookie, _h, _member


@pytest.fixture(autouse=True)
def _reset():
    from app.core import idempotency
    from app.core.security import login_throttle
    from app.main import app

    login_throttle.reset()
    mw = idempotency.find(app)
    if mw:
        mw.reset()
    yield
    login_throttle.reset()


@pytest.fixture
async def admin(client):
    res = await client.post("/api/auth/setup", json=SETUP)
    return {"Cookie": _cookie(res), "id": res.json()["id"]}


@pytest.fixture
async def kid(client, admin):
    return await _member(client, admin)


async def count_items(setup_db):
    return (await setup_db.execute(select(func.count()).select_from(ShoppingItem))).scalar()


class TestIdempotency:
    async def test_a_replayed_write_runs_once(self, client, admin, setup_db):
        headers = {**_h(admin), "Idempotency-Key": "op-123"}
        first = await client.post("/api/meals/shopping", json={"name": "Milk"}, headers=headers)
        again = await client.post("/api/meals/shopping", json={"name": "Milk"}, headers=headers)
        assert first.status_code == again.status_code == 201
        assert first.json()["id"] == again.json()["id"]
        assert again.headers.get("idempotent-replay") == "true"
        assert await count_items(setup_db) == 1

    async def test_keys_belong_to_one_sign_in_and_writes_without_one_run_every_time(self, client, admin, kid, setup_db):
        await client.post("/api/meals/shopping", json={"name": "Milk"}, headers={**_h(admin), "Idempotency-Key": "same"})
        await client.post("/api/meals/shopping", json={"name": "Milk"}, headers={**_h(kid), "Idempotency-Key": "same"})
        await client.post("/api/meals/shopping", json={"name": "Eggs"}, headers=_h(kid))
        await client.post("/api/meals/shopping", json={"name": "Eggs"}, headers=_h(kid))
        assert await count_items(setup_db) == 4

    async def test_refusals_are_remembered_too_but_reads_ignore_keys(self, client, admin, kid):
        viewer = await _member(client, admin, name="Gran", pin="9999", role="viewer")
        h = {**_h(viewer), "Idempotency-Key": "v1"}
        assert (await client.post("/api/meals/shopping", json={"name": "x"}, headers=h)).status_code == 403
        assert (await client.post("/api/meals/shopping", json={"name": "x"}, headers=h)).headers.get("idempotent-replay") == "true"
        res = await client.get("/api/meals/shopping", headers={**_h(kid), "Idempotency-Key": "read"})
        assert "idempotent-replay" not in res.headers


class TestConflicts:
    async def test_a_stale_todo_edit_is_refused_with_the_current_copy(self, client, admin, kid):
        todo = (await client.post("/api/todos", json={"title": "Buy a card"}, headers=_h(kid))).json()
        base = {"title": "Buy a card", "notes": None, "done": False}
        # Someone else renames it first.
        await client.patch(f"/api/todos/{todo['id']}", json={"title": "Buy a birthday card"}, headers=_h(admin))
        res = await client.patch(f"/api/todos/{todo['id']}", json={"done": True, "base": base}, headers=_h(kid))
        assert res.status_code == 409
        detail = res.json()["detail"]
        assert detail["fields"] == ["title"] and detail["current"]["title"] == "Buy a birthday card"
        # "Keep mine": the same edit without base goes through.
        res = await client.patch(f"/api/todos/{todo['id']}", json={"done": True}, headers=_h(kid))
        assert res.status_code == 200 and res.json()["done"] is True

    async def test_a_matching_base_applies(self, client, admin, kid):
        todo = (await client.post("/api/todos", json={"title": "Call Gran"}, headers=_h(kid))).json()
        res = await client.patch(f"/api/todos/{todo['id']}", headers=_h(kid),
                                 json={"done": True, "base": {"title": "Call Gran", "done": False, "due_date": None}})
        assert res.status_code == 200 and res.json()["done"] is True

    async def test_shopping_edits_check_name_quantity_and_ticked(self, client, admin, kid):
        item = (await client.post("/api/meals/shopping", json={"name": "Milk", "quantity": "1 gal"}, headers=_h(kid))).json()
        await client.patch(f"/api/meals/shopping/{item['id']}", json={"checked": True}, headers=_h(admin))
        stale = {"name": "Milk", "quantity": "1 gal", "checked": False, "checked_at": None}
        res = await client.patch(f"/api/meals/shopping/{item['id']}", json={"quantity": "2 gal", "base": stale}, headers=_h(kid))
        assert res.status_code == 409 and res.json()["detail"]["fields"] == ["checked"]
        fresh = {**stale, "checked": True}
        res = await client.patch(f"/api/meals/shopping/{item['id']}", json={"quantity": "2 gal", "base": fresh}, headers=_h(kid))
        assert res.status_code == 200 and res.json()["quantity"] == "2 gal"
