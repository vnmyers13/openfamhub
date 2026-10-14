"""Phase 7: recipes, catalog, weekly plan, shopping list, pantry and the weekly reset."""
from contextlib import asynccontextmanager
from datetime import date as D, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select

from app.models.meals import ShoppingItem
from app.services.chores import family_today
from app.services.rewards import week_start
from tests.test_phase2 import SETUP, _cookie, _h, _member

ZONE = ZoneInfo(SETUP["timezone"])
TODAY = family_today(SETUP["timezone"])
MONDAY = week_start(TODAY)


@pytest.fixture(autouse=True)
def _reset_throttle():
    from app.core.security import login_throttle

    login_throttle.reset()
    yield
    login_throttle.reset()


@pytest.fixture
async def admin(client):
    res = await client.post("/api/auth/setup", json=SETUP)
    assert res.status_code == 200, res.text
    return {"Cookie": _cookie(res), "id": res.json()["id"]}


@pytest.fixture
async def kid(client, admin):
    return await _member(client, admin, name="Kid", pin="1357")


@pytest.fixture
async def viewer(client, admin):
    return await _member(client, admin, name="Grandma", pin="9999", role="viewer")


async def recipe(client, who, title="Tacos", ingredients=("1 lb beef", "8 tortillas"), **extra):
    body = {"title": title, "ingredients": list(ingredients), "steps": ["Cook.", "Eat."], **extra}
    res = await client.post("/api/meals/recipes", json=body, headers=_h(who))
    assert res.status_code == 201, res.text
    return res.json()


async def plan(client, who, day, slot, **body):
    res = await client.put(f"/api/meals/plan/{day.isoformat()}/{slot}", json=body, headers=_h(who))
    assert res.status_code == 200, res.text
    return res.json()


async def shopping(client, who):
    res = await client.get("/api/meals/shopping", headers=_h(who))
    assert res.status_code == 200, res.text
    return res.json()


class TestRecipes:
    async def test_members_add_edit_search_and_delete(self, client, admin, kid):
        r = await recipe(client, kid, tags=["Dinner", "dinner", "Gluten-Free"], video_url="https://videos.example.com/t",
                         servings=4)
        assert r["tags"] == ["dinner", "gluten-free"] and r["servings"] == 4 and r["created_by"] == kid["id"]
        await recipe(client, admin, title="Pancakes", ingredients=["1 egg"], description="Sunday breakfast")
        titles = lambda res: [x["title"] for x in res.json()]  # noqa: E731
        assert titles(await client.get("/api/meals/recipes", headers=_h(kid))) == ["Pancakes", "Tacos"]
        assert titles(await client.get("/api/meals/recipes", params={"q": "sunday"}, headers=_h(kid))) == ["Pancakes"]
        assert titles(await client.get("/api/meals/recipes", params={"tag": "gluten-free"}, headers=_h(kid))) == ["Tacos"]
        res = await client.patch(f"/api/meals/recipes/{r['id']}", json={"title": "Fish tacos", "video_url": None}, headers=_h(kid))
        assert res.status_code == 200 and res.json()["title"] == "Fish tacos" and res.json()["video_url"] is None
        assert res.json()["ingredients"] == ["1 lb beef", "8 tortillas"]
        assert (await client.delete(f"/api/meals/recipes/{r['id']}", headers=_h(kid))).status_code == 200
        assert (await client.get(f"/api/meals/recipes/{r['id']}", headers=_h(kid))).status_code == 404

    async def test_only_web_links_are_accepted(self, client, admin):
        for field in ("video_url", "source_url"):
            res = await client.post("/api/meals/recipes", json={"title": "x", field: "javascript:alert(1)"}, headers=_h(admin))
            assert res.status_code == 422

    async def test_viewers_read_but_dont_change_and_strangers_get_nothing(self, client, admin, viewer):
        await recipe(client, admin)
        assert len((await client.get("/api/meals/recipes", headers=_h(viewer))).json()) == 1
        assert (await client.post("/api/meals/recipes", json={"title": "x"}, headers=_h(viewer))).status_code == 403
        for path in ("/api/meals/recipes", "/api/meals/plan", "/api/meals/shopping", "/api/meals/pantry", "/api/meals/catalog"):
            assert (await client.get(path)).status_code == 401, path

    async def test_the_catalog_adds_each_recipe_once(self, client, admin, kid):
        cat = (await client.get("/api/meals/catalog", headers=_h(kid))).json()
        assert len(cat) >= 8 and not any(c["added"] for c in cat)
        key = cat[0]["key"]
        res = await client.post(f"/api/meals/catalog/{key}", headers=_h(kid))
        assert res.status_code == 201 and res.json()["catalog_key"] == key and res.json()["ingredients"]
        assert (await client.post(f"/api/meals/catalog/{key}", headers=_h(kid))).status_code == 409
        assert (await client.post("/api/meals/catalog/nope", headers=_h(kid))).status_code == 404
        assert [c["added"] for c in (await client.get("/api/meals/catalog", headers=_h(kid))).json()].count(True) == 1


class TestPlan:
    async def test_set_clear_and_read_a_week(self, client, admin, kid):
        r = await recipe(client, kid)
        await plan(client, kid, MONDAY, "dinner", recipe_id=r["id"])
        await plan(client, kid, MONDAY + timedelta(days=1), "lunch", title="Leftovers", note="from Monday")
        await plan(client, kid, MONDAY, "breakfast", title="Cereal")
        week = (await client.get("/api/meals/plan", headers=_h(kid))).json()
        assert week["week_start"] == MONDAY.isoformat() and len(week["days"]) == 7
        assert [(e["day"], e["slot"], e["title"]) for e in week["entries"]] == [
            (MONDAY.isoformat(), "breakfast", "Cereal"), (MONDAY.isoformat(), "dinner", "Tacos"),
            ((MONDAY + timedelta(days=1)).isoformat(), "lunch", "Leftovers")]
        await plan(client, kid, MONDAY, "dinner", title="Pizza night")  # replaces the slot
        assert (await client.delete(f"/api/meals/plan/{MONDAY}/breakfast", headers=_h(kid))).status_code == 200
        week = (await client.get("/api/meals/plan", params={"start": (MONDAY + timedelta(days=3)).isoformat()}, headers=_h(kid))).json()
        assert [(e["slot"], e["title"], e["recipe_id"]) for e in week["entries"]] == [("dinner", "Pizza night", None), ("lunch", "Leftovers", None)]

    async def test_a_deleted_recipe_keeps_its_planned_title(self, client, admin):
        r = await recipe(client, admin, title="Lasagna")
        await plan(client, admin, MONDAY, "dinner", recipe_id=r["id"])
        await client.delete(f"/api/meals/recipes/{r['id']}", headers=_h(admin))
        [entry] = (await client.get("/api/meals/plan", headers=_h(admin))).json()["entries"]
        assert entry["title"] == "Lasagna"

    async def test_saving_a_week_replaces_only_that_week(self, client, admin):
        r = await recipe(client, admin)
        next_monday = MONDAY + timedelta(days=7)
        await plan(client, admin, MONDAY, "dinner", title="Old dinner")
        await plan(client, admin, MONDAY + timedelta(days=2), "lunch", title="Old lunch")
        await plan(client, admin, next_monday, "dinner", title="Next week")
        body = {"entries": [{"day": MONDAY.isoformat(), "slot": "dinner", "recipe_id": r["id"]},
                            {"day": (MONDAY + timedelta(days=4)).isoformat(), "slot": "snack", "title": "Popcorn"}]}
        res = await client.put(f"/api/meals/plan/week/{MONDAY}", json=body, headers=_h(admin))
        assert res.status_code == 200, res.text
        assert [(e["slot"], e["title"]) for e in res.json()["entries"]] == [("dinner", "Tacos"), ("snack", "Popcorn")]
        nxt = (await client.get("/api/meals/plan", params={"start": next_monday.isoformat()}, headers=_h(admin))).json()
        assert [e["title"] for e in nxt["entries"]] == ["Next week"]

    async def test_bad_weeks_are_refused(self, client, admin):
        tuesday = MONDAY + timedelta(days=1)
        assert (await client.put(f"/api/meals/plan/week/{tuesday}", json={"entries": []}, headers=_h(admin))).status_code == 400
        outside = {"entries": [{"day": (MONDAY + timedelta(days=7)).isoformat(), "slot": "dinner", "title": "x"}]}
        assert (await client.put(f"/api/meals/plan/week/{MONDAY}", json=outside, headers=_h(admin))).status_code == 400
        twice = {"entries": [{"day": MONDAY.isoformat(), "slot": "dinner", "title": "a"},
                             {"day": MONDAY.isoformat(), "slot": "dinner", "title": "b"}]}
        assert (await client.put(f"/api/meals/plan/week/{MONDAY}", json=twice, headers=_h(admin))).status_code == 400
        empty = await client.put(f"/api/meals/plan/{MONDAY}/dinner", json={}, headers=_h(admin))
        assert empty.status_code == 422
        assert (await client.put(f"/api/meals/plan/{MONDAY}/brunch", json={"title": "x"}, headers=_h(admin))).status_code == 422
        assert (await client.put(f"/api/meals/plan/{MONDAY}/dinner", json={"recipe_id": "nope"}, headers=_h(admin))).status_code == 404


class TestShopping:
    async def test_the_plan_makes_a_list_that_tracks_recipes_and_regenerates_idempotently(self, client, admin):
        tacos = await recipe(client, admin)
        soup = await recipe(client, admin, title="Soup", ingredients=["1 onion", "4 cups broth"])
        await plan(client, admin, MONDAY, "dinner", recipe_id=tacos["id"])
        await plan(client, admin, MONDAY + timedelta(days=3), "dinner", recipe_id=tacos["id"])
        await plan(client, admin, MONDAY + timedelta(days=1), "lunch", recipe_id=soup["id"])
        await client.post("/api/meals/shopping", json={"name": "Coffee"}, headers=_h(admin))
        res = await client.post("/api/meals/shopping/from-plan", headers=_h(admin))
        assert res.json() == {"added": 4, "removed": 0, "week_start": MONDAY.isoformat()}
        items = await shopping(client, admin)
        assert {(i["name"], i["recipe_title"], i["quantity"]) for i in items} == {
            ("Coffee", None, None), ("1 lb beef", "Tacos", "×2"), ("8 tortillas", "Tacos", "×2"),
            ("1 onion", "Soup", None), ("4 cups broth", "Soup", None)}
        again = await client.post("/api/meals/shopping/from-plan", headers=_h(admin))
        assert again.json()["added"] == 0 and again.json()["removed"] == 0
        assert len(await shopping(client, admin)) == 5

    async def test_regenerating_after_a_plan_change_keeps_what_was_bought(self, client, admin):
        tacos = await recipe(client, admin)
        await plan(client, admin, MONDAY, "dinner", recipe_id=tacos["id"])
        await client.post("/api/meals/shopping/from-plan", headers=_h(admin))
        beef = next(i for i in await shopping(client, admin) if i["name"] == "1 lb beef")
        res = await client.patch(f"/api/meals/shopping/{beef['id']}", json={"checked": True}, headers=_h(admin))
        assert res.json()["checked"] is True and res.json()["checked_by"] == admin["id"]
        await plan(client, admin, MONDAY, "dinner", title="Eating out")
        res = await client.post("/api/meals/shopping/from-plan", headers=_h(admin))
        assert res.json()["removed"] == 1  # the tortillas; the bought beef stays
        assert [(i["name"], i["checked"]) for i in await shopping(client, admin)] == [("1 lb beef", True)]

    async def test_manual_items_check_edit_and_delete(self, client, admin, kid, viewer):
        res = await client.post("/api/meals/shopping", json={"name": " Milk ", "quantity": "2 gal"}, headers=_h(kid))
        item = res.json()
        assert res.status_code == 201 and item["name"] == "Milk" and item["source"] == "manual"
        res = await client.patch(f"/api/meals/shopping/{item['id']}", json={"quantity": None}, headers=_h(kid))
        assert res.json()["quantity"] is None
        assert (await client.patch(f"/api/meals/shopping/{item['id']}", json={"checked": True}, headers=_h(viewer))).status_code == 403
        assert (await client.delete(f"/api/meals/shopping/{item['id']}", headers=_h(kid))).status_code == 200
        assert await shopping(client, kid) == []
        assert (await client.delete(f"/api/meals/shopping/{item['id']}", headers=_h(kid))).status_code == 404

    async def test_the_pantry_hints_what_you_already_have(self, client, admin):
        await client.post("/api/meals/pantry", json={"name": "Rice", "quantity": 3, "unit": "lb"}, headers=_h(admin))
        await client.post("/api/meals/pantry", json={"name": "Egg", "quantity": 1, "low_at": 2}, headers=_h(admin))
        for name in ("2 cups rice", "3 eggs", "Rice cakes"):
            await client.post("/api/meals/shopping", json={"name": name}, headers=_h(admin))
        hints = {i["name"]: i["in_pantry"] for i in await shopping(client, admin)}
        assert hints == {"2 cups rice": "Rice", "3 eggs": None, "Rice cakes": "Rice"}  # eggs are running low


class TestWeeklyReset:
    @pytest.fixture
    def job(self, setup_db, monkeypatch):
        from app.jobs import shopping_reset

        @asynccontextmanager
        async def shared_session():
            yield setup_db

        monkeypatch.setattr(shopping_reset, "session_factory", shared_session)
        return shopping_reset.run_shopping_reset

    async def test_reset_archives_purchases_and_drops_stale_plan_items(self, client, admin, setup_db, job):
        tacos = await recipe(client, admin)
        await plan(client, admin, MONDAY, "dinner", recipe_id=tacos["id"])
        await client.post("/api/meals/shopping/from-plan", headers=_h(admin))
        await client.post("/api/meals/shopping", json={"name": "Coffee"}, headers=_h(admin))
        beef = next(i for i in await shopping(client, admin) if i["name"] == "1 lb beef")
        await client.patch(f"/api/meals/shopping/{beef['id']}", json={"checked": True}, headers=_h(admin))

        # Same week: nothing happens.
        assert await job(now=datetime.now(timezone.utc)) == (0, 0)
        # Next Monday morning, family time.
        next_monday = datetime.combine(MONDAY + timedelta(days=7), time(1), ZONE).astimezone(timezone.utc)
        assert await job(now=next_monday) == (1, 1)  # beef archived, unbought tortillas dropped
        assert await job(now=next_monday) == (0, 0)
        assert [i["name"] for i in await shopping(client, admin)] == ["Coffee"]  # still to buy
        history = (await client.get("/api/meals/shopping/history", headers=_h(admin))).json()
        assert [(h["name"], h["checked"]) for h in history] == [("1 lb beef", True)]
        rows = (await setup_db.execute(select(ShoppingItem))).scalars().all()
        assert sorted(r.name for r in rows) == ["1 lb beef", "Coffee"]  # the purchase was kept, not deleted
        archived = next(r for r in rows if r.name == "1 lb beef")
        res = await client.patch(f"/api/meals/shopping/{archived.id}", json={"checked": False}, headers=_h(admin))
        assert res.status_code == 409

    async def test_clear_checked_moves_purchases_to_history_now(self, client, admin):
        item = (await client.post("/api/meals/shopping", json={"name": "Bread"}, headers=_h(admin))).json()
        await client.patch(f"/api/meals/shopping/{item['id']}", json={"checked": True}, headers=_h(admin))
        assert (await client.post("/api/meals/shopping/clear-checked", headers=_h(admin))).json() == {"archived": 1}
        assert await shopping(client, admin) == []
        assert len((await client.get("/api/meals/shopping/history", headers=_h(admin))).json()) == 1

    def test_registered_hourly_and_at_startup(self):
        from apscheduler.schedulers.asyncio import AsyncIOScheduler

        from app.jobs.shopping_reset import register_shopping_reset_job

        scheduler = AsyncIOScheduler(timezone="UTC")
        register_shopping_reset_job(scheduler)
        assert scheduler.get_job("shopping_reset").next_run_time is not None


class TestPantry:
    async def test_flags_low_expired_and_expiring_soon(self, client, admin):
        items = [
            {"name": "Milk", "quantity": 0.5, "unit": "gal", "low_at": 1, "expires_on": (TODAY + timedelta(days=2)).isoformat()},
            {"name": "Yogurt", "quantity": 4, "expires_on": (TODAY - timedelta(days=1)).isoformat()},
            {"name": "Flour", "quantity": 5, "unit": "lb", "low_at": 1, "expires_on": (TODAY + timedelta(days=60)).isoformat()},
        ]
        for body in items:
            assert (await client.post("/api/meals/pantry", json=body, headers=_h(admin))).status_code == 201
        rows = {p["name"]: p for p in (await client.get("/api/meals/pantry", headers=_h(admin))).json()}
        assert list(rows) == ["Flour", "Milk", "Yogurt"]
        assert (rows["Milk"]["is_low"], rows["Milk"]["expires_soon"], rows["Milk"]["expired"]) == (True, True, False)
        assert (rows["Yogurt"]["expired"], rows["Yogurt"]["is_low"]) == (True, False)
        assert not any((rows["Flour"]["is_low"], rows["Flour"]["expired"], rows["Flour"]["expires_soon"]))

    async def test_edit_restock_and_delete(self, client, admin, kid, viewer):
        milk = (await client.post("/api/meals/pantry", json={"name": "Milk", "quantity": 2, "low_at": 1}, headers=_h(kid))).json()
        assert milk["is_low"] is False
        res = await client.patch(f"/api/meals/pantry/{milk['id']}", json={"quantity": 1}, headers=_h(kid))
        assert res.json()["is_low"] is True and res.json()["name"] == "Milk"
        assert (await client.post("/api/meals/pantry/restock", headers=_h(kid))).json() == {"added": 1}
        assert (await client.post("/api/meals/pantry/restock", headers=_h(kid))).json() == {"added": 0}  # already on the list
        [item] = await shopping(client, kid)
        assert (item["name"], item["source"]) == ("Milk", "pantry")
        assert (await client.post("/api/meals/pantry", json={"name": "x"}, headers=_h(viewer))).status_code == 403
        assert (await client.delete(f"/api/meals/pantry/{milk['id']}", headers=_h(kid))).status_code == 200
        assert (await client.patch(f"/api/meals/pantry/{milk['id']}", json={"quantity": 3}, headers=_h(kid))).status_code == 404
