"""Phase 8: books (lists and the family library), announcements and birthdays."""
from datetime import date as D, datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from app.models.chores import PointsEntry
from app.services import birthdays as bd
from app.services.chores import family_today
from tests.test_phase2 import SETUP, _cookie, _h, _member

TODAY = family_today(SETUP["timezone"])


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
async def kids(client, admin):
    return await _member(client, admin, name="Kid", pin="1357"), await _member(client, admin, name="Sib", pin="2468")


@pytest.fixture
async def viewer(client, admin):
    return await _member(client, admin, name="Grandma", pin="9999", role="viewer")


async def add_book(client, who, **body):
    res = await client.post("/api/books", json={"title": "Charlotte's Web", **body}, headers=_h(who))
    assert res.status_code == 201, res.text
    return res.json()


async def book_points(setup_db, user_id):
    return (await setup_db.execute(
        select(func.coalesce(func.sum(PointsEntry.delta), 0))
        .where(PointsEntry.user_id == user_id, PointsEntry.source_type == "book")
    )).scalar()


class TestBooks:
    async def test_finishing_a_book_pays_its_reader_once(self, client, admin, kids, setup_db):
        kid, _ = kids
        book = await add_book(client, kid, author="E. B. White")
        assert book["owner_id"] == kid["id"] and book["status"] == "want_to_read"
        res = await client.patch(f"/api/books/{book['id']}", json={"status": "reading"}, headers=_h(kid))
        assert res.json()["reader_id"] == kid["id"] and res.json()["points_awarded"] is False
        res = await client.patch(f"/api/books/{book['id']}", json={"status": "finished"}, headers=_h(kid))
        assert res.json()["points_awarded"] is True and res.json()["finished_at"]
        # Un-finish and finish again: no second award.
        await client.patch(f"/api/books/{book['id']}", json={"status": "reading"}, headers=_h(kid))
        res = await client.patch(f"/api/books/{book['id']}", json={"status": "finished"}, headers=_h(kid))
        assert res.json()["points_awarded"] is False
        assert await book_points(setup_db, kid["id"]) == 50

    async def test_adding_a_finished_book_pays_once_too(self, client, admin, kids, setup_db):
        kid, _ = kids
        res = await client.post("/api/books", json={"title": "Holes", "status": "finished"}, headers=_h(kid))
        assert res.json()["points_awarded"] is True
        assert await book_points(setup_db, kid["id"]) == 50

    async def test_lists_are_visible_to_the_family_but_only_their_owner_changes_them(self, client, admin, kids, viewer):
        kid, sib = kids
        book = await add_book(client, kid)
        mine = (await client.get("/api/books", params={"shelf": "mine"}, headers=_h(sib))).json()
        assert mine == []
        theirs = (await client.get("/api/books", params={"shelf": "mine", "user_id": kid["id"]}, headers=_h(sib))).json()
        assert [b["id"] for b in theirs] == [book["id"]]
        assert len((await client.get("/api/books", headers=_h(viewer))).json()) == 1
        assert (await client.patch(f"/api/books/{book['id']}", json={"status": "reading"}, headers=_h(sib))).status_code == 403
        assert (await client.patch(f"/api/books/{book['id']}", json={"title": "Mine now"}, headers=_h(sib))).status_code == 403
        assert (await client.delete(f"/api/books/{book['id']}", headers=_h(sib))).status_code == 403
        assert (await client.post("/api/books", json={"title": "x"}, headers=_h(viewer))).status_code == 403
        res = await client.patch(f"/api/books/{book['id']}", json={"title": "Charlotte's Web (2nd ed.)", "author": "  "}, headers=_h(admin))
        assert res.status_code == 200 and res.json()["author"] is None
        assert (await client.delete(f"/api/books/{book['id']}", headers=_h(kid))).status_code == 200

    async def test_the_family_library_can_be_picked_up_by_anyone(self, client, admin, kids, setup_db):
        kid, sib = kids
        book = await add_book(client, admin, title="Matilda", shelf="family")
        assert book["owner_id"] is None
        library = (await client.get("/api/books", params={"shelf": "family"}, headers=_h(kid))).json()
        assert [b["title"] for b in library] == ["Matilda"]
        res = await client.patch(f"/api/books/{book['id']}", json={"status": "reading"}, headers=_h(kid))
        assert res.json()["reader_id"] == kid["id"]
        await client.patch(f"/api/books/{book['id']}", json={"status": "finished"}, headers=_h(kid))
        # Back on the shelf, then the sibling reads it: they earn their own points.
        res = await client.patch(f"/api/books/{book['id']}", json={"status": "want_to_read"}, headers=_h(sib))
        assert res.json()["reader_id"] is None
        await client.patch(f"/api/books/{book['id']}", json={"status": "finished"}, headers=_h(sib))
        assert (await book_points(setup_db, kid["id"]), await book_points(setup_db, sib["id"])) == (50, 50)
        # Only whoever added it (or an admin) edits or removes a library book.
        assert (await client.patch(f"/api/books/{book['id']}", json={"notes": "x"}, headers=_h(kid))).status_code == 403
        assert (await client.delete(f"/api/books/{book['id']}", headers=_h(kid))).status_code == 403
        assert (await client.delete(f"/api/books/{book['id']}", headers=_h(admin))).status_code == 200
        assert (await client.patch(f"/api/books/{book['id']}", json={"status": "reading"}, headers=_h(kid))).status_code == 404

    async def test_book_points_count_toward_badges(self, client, admin, kids):
        kid, _ = kids
        await client.post("/api/rewards/badges", headers=_h(admin),
                          json={"name": "Bookworm", "kind": "points_earned", "threshold": 1, "bonus_points": 0})
        # Book points aren't chore points, so this badge isn't earned by reading.
        await add_book(client, kid, status="finished")
        rows = (await client.get("/api/rewards/progress", headers=_h(kid))).json()
        row = next(r for r in rows if r["user_id"] == kid["id"])
        assert row["points_balance"] == 50 and row["badges"] == []

    async def test_bad_input(self, client, admin):
        assert (await client.post("/api/books", json={"title": "  "}, headers=_h(admin))).status_code == 422
        assert (await client.post("/api/books", json={"title": "x", "status": "skimmed"}, headers=_h(admin))).status_code == 422
        assert (await client.get("/api/books")).status_code == 401


class TestAnnouncements:
    async def test_post_pin_edit_and_remove(self, client, admin, kids, viewer):
        kid, sib = kids
        first = (await client.post("/api/announcements", json={"body": "Dentist Tuesday"}, headers=_h(kid))).json()
        second = (await client.post("/api/announcements", json={"body": "  Pizza Friday  "}, headers=_h(admin))).json()
        assert second["body"] == "Pizza Friday"
        listed = (await client.get("/api/announcements", headers=_h(viewer))).json()
        assert [a["body"] for a in listed] == ["Pizza Friday", "Dentist Tuesday"]  # newest first
        res = await client.patch(f"/api/announcements/{first['id']}", json={"pinned": True}, headers=_h(kid))
        assert res.json()["pinned"] is True
        listed = (await client.get("/api/announcements", headers=_h(kid))).json()
        assert [a["body"] for a in listed] == ["Dentist Tuesday", "Pizza Friday"]  # pinned first
        assert (await client.patch(f"/api/announcements/{first['id']}", json={"body": "x"}, headers=_h(sib))).status_code == 403
        assert (await client.post("/api/announcements", json={"body": "hi"}, headers=_h(viewer))).status_code == 403
        assert (await client.delete(f"/api/announcements/{first['id']}", headers=_h(admin))).status_code == 200
        assert (await client.delete(f"/api/announcements/{first['id']}", headers=_h(admin))).status_code == 404
        assert (await client.post("/api/announcements", json={"body": ""}, headers=_h(admin))).status_code == 422
        assert (await client.get("/api/announcements")).status_code == 401


class TestBirthdays:
    def test_next_birthday_and_age_cross_the_year_boundary(self):
        born = D(2016, 1, 3)
        assert bd.next_birthday(born, D(2026, 12, 30)) == D(2027, 1, 3)
        assert bd.age_on(born, D(2027, 1, 3)) == 11
        assert bd.next_birthday(born, D(2026, 1, 3)) == D(2026, 1, 3)  # today counts
        leap = D(2016, 2, 29)
        assert bd.next_birthday(leap, D(2026, 2, 1)) == D(2026, 2, 28)
        assert bd.next_birthday(leap, D(2028, 2, 1)) == D(2028, 2, 29)

    async def test_members_set_their_birthday_and_it_shows_up(self, client, admin, kids):
        kid, sib = kids
        soon = TODAY + timedelta(days=3)
        born = soon.replace(year=soon.year - 9) if not (soon.month == 2 and soon.day == 29) else D(soon.year - 8, 2, 29)
        res = await client.patch(f"/api/users/{kid['id']}", json={"birthday": born.isoformat()}, headers=_h(kid))
        assert res.status_code == 200 and res.json()["birthday"] == born.isoformat()
        assert (await client.patch(f"/api/users/{sib['id']}", json={"birthday": "2015-01-01"}, headers=_h(kid))).status_code == 403
        future = (TODAY + timedelta(days=400)).isoformat()
        assert (await client.patch(f"/api/users/{kid['id']}", json={"birthday": future}, headers=_h(kid))).status_code == 422
        [b] = (await client.get("/api/dashboard/birthdays", headers=_h(sib))).json()
        assert (b["display_name"], b["days_away"]) == ("Kid", 3)
        # An all-day, read-only calendar entry on the day.
        start = datetime(soon.year, soon.month, soon.day, tzinfo=timezone.utc) - timedelta(days=1)
        events = (await client.get("/api/calendar/events", headers=_h(sib),
                                   params={"start": start.isoformat(), "end": (start + timedelta(days=3)).isoformat()})).json()
        [ev] = [e for e in events if e["source_id"] == "birthdays"]
        assert ev["all_day"] is True and ev["external_uid"] and ev["title"].startswith("🎂 Kid's birthday (")
        # Clearing it removes it.
        await client.patch(f"/api/users/{kid['id']}", json={"birthday": None}, headers=_h(kid))
        assert (await client.get("/api/dashboard/birthdays", headers=_h(sib))).json() == []

    async def test_the_wall_shows_the_next_two_weeks(self, client, admin, kids):
        kid, sib = kids
        await client.patch(f"/api/users/{kid['id']}", headers=_h(kid),
                           json={"birthday": (TODAY - timedelta(days=365 * 10 - 5)).isoformat()})
        await client.patch(f"/api/users/{sib['id']}", headers=_h(sib),
                           json={"birthday": (TODAY - timedelta(days=365 * 8 - 40)).isoformat()})
        assert (await client.get("/api/wall/birthdays")).status_code == 401
        device = (await client.post("/api/wall/devices", json={"name": "Kitchen"}, headers=_h(admin))).json()
        pair = await client.post("/api/wall/pair", json={"token": device["token"]})
        rows = (await client.get("/api/wall/birthdays", headers={"Cookie": _cookie(pair, "wall_token")})).json()
        assert [r["display_name"] for r in rows] == ["Kid"]
