"""Calendar source and event scoping (review backlog #6, #7)."""
import pytest

from tests.test_phase2 import SETUP, _cookie, _h


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


WINDOW = {"start": "2026-10-10T00:00:00Z", "end": "2026-10-11T00:00:00Z"}


class TestInternalSourceCreation:
    async def test_admin_cannot_create_an_internal_source(self, client, admin):
        res = await client.post(
            "/api/calendar/sources",
            json={"display_name": "Sneaky", "provider": "internal"},
            headers=_h(admin),
        )
        assert res.status_code == 422

        sources = (await client.get("/api/calendar/sources", headers=_h(admin))).json()
        assert all(s["display_name"] != "Sneaky" for s in sources)

    async def test_ical_is_still_the_default_provider(self, client, admin):
        res = await client.post(
            "/api/calendar/sources",
            json={"display_name": "School", "ics_url": "https://example.test/s.ics"},
            headers=_h(admin),
        )
        assert res.status_code == 201, res.text
        assert res.json()["provider"] == "ical"


class TestEventFamilyScoping:
    async def _plant_foreign_event(self, client, admin, setup_db):
        """An event row whose source belongs to this family but whose own
        family_id is another tenant's: a malformed row that must stay hidden."""
        from app.models.calendar_event import CalendarEvent
        from app.services.calendar import get_or_create_internal_source
        from datetime import datetime, timezone

        me = (await client.get("/api/auth/me", headers=_h(admin))).json()
        source = await get_or_create_internal_source(setup_db, me["family_id"])
        event = CalendarEvent(
            source_id=source.id,
            family_id="some-other-family",
            title="Not yours",
            start_dt=datetime(2026, 10, 10, 15, tzinfo=timezone.utc),
            end_dt=datetime(2026, 10, 10, 16, tzinfo=timezone.utc),
        )
        setup_db.add(event)
        await setup_db.flush()
        return event.id

    async def test_list_hides_events_from_another_family(self, client, admin, setup_db):
        await self._plant_foreign_event(client, admin, setup_db)
        events = (await client.get("/api/calendar/events", params=WINDOW, headers=_h(admin))).json()
        assert [e["title"] for e in events] == []

    async def test_single_event_routes_hide_events_from_another_family(self, client, admin, setup_db):
        event_id = await self._plant_foreign_event(client, admin, setup_db)
        assert (await client.get(f"/api/calendar/events/{event_id}", headers=_h(admin))).status_code == 404
        res = await client.patch(f"/api/calendar/events/{event_id}", json={"title": "x"}, headers=_h(admin))
        assert res.status_code == 404
        assert (await client.delete(f"/api/calendar/events/{event_id}", headers=_h(admin))).status_code == 404

    async def test_own_events_are_still_listed(self, client, admin):
        res = await client.post(
            "/api/calendar/events",
            json={"title": "Dinner", "start_dt": "2026-10-10T22:00:00Z", "end_dt": "2026-10-10T23:00:00Z"},
            headers=_h(admin),
        )
        assert res.status_code == 201, res.text
        events = (await client.get("/api/calendar/events", params=WINDOW, headers=_h(admin))).json()
        assert [e["title"] for e in events] == ["Dinner"]
