"""Event location and details (pulled forward 2026-10-15): feeds keep their
link, organizer and attendees as well as location and description; events
added in the app can carry a link; all of it comes back with each event."""
from datetime import datetime, timedelta, timezone

import pytest

from app.integrations.ical_feed import parse_ics
from tests.test_calendar_sync import Feed, _ev, _source, _sync
from tests.test_phase2 import SETUP, _cookie, _h, _member

NOW = datetime(2026, 10, 12, 12, 0, tzinfo=timezone.utc)


def _ics(*lines: str) -> bytes:
    body = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//OpenFamHub test//EN", "BEGIN:VEVENT",
            "UID:game", "DTSTART:20261014T220000Z", "DTEND:20261014T230000Z", "SUMMARY:Soccer game", *lines,
            "END:VEVENT", "END:VCALENDAR", ""]
    return "\r\n".join(body).encode()


def _one(*lines):
    (event,) = parse_ics(_ics(*lines), family_tz="America/Detroit", now=NOW)
    return event


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


class TestFeedDetails:
    def test_location_link_organizer_and_attendees_are_kept(self):
        event = _one(
            "LOCATION:Riverside Park\\, Field 3",
            "DESCRIPTION:Bring water.\\nSee https://club.example/schedule",
            "URL:https://club.example/games/42",
            "ORGANIZER;CN=Coach Lee:mailto:lee@club.example",
            "ATTENDEE;CN=Sam:mailto:sam@example.com",
            "ATTENDEE:mailto:pat@example.com",
        )
        assert event["location"] == "Riverside Park, Field 3"
        assert event["description"] == "Bring water.\nSee https://club.example/schedule"
        assert event["url"] == "https://club.example/games/42"
        assert event["organizer"] == "Coach Lee"
        assert event["attendees"] == ["Sam", "pat@example.com"]

    def test_only_web_links_are_kept_and_names_fall_back_to_the_address(self):
        event = _one("URL:javascript:alert(1)", "ORGANIZER:mailto:office@school.example")
        assert event["url"] is None and event["organizer"] == "office@school.example" and event["attendees"] is None

    def test_none_of_it_is_needed(self):
        event = _one()
        assert (event["location"], event["url"], event["organizer"], event["attendees"]) == (None, None, None, None)

    def test_attendee_lists_are_capped(self):
        event = _one(*[f"ATTENDEE;CN=Kid {i}:mailto:k{i}@example.com" for i in range(80)])
        assert len(event["attendees"]) == 50

    async def test_they_survive_a_sync_and_come_back_with_the_event(self, client, admin, monkeypatch):
        from app.jobs import calendar_sync

        start = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(days=1)
        full = {**_ev("game", start), "location": "Field 3", "description": "Bring water", "url": "https://club.example/g",
                "organizer": "Coach Lee", "attendees": ["Sam", "Pat"]}
        older = _ev("practice", start + timedelta(hours=3))  # a parser result without the new keys
        monkeypatch.setattr(calendar_sync, "fetch_and_parse", Feed([full, older]))
        source_id = await _source(client, admin)
        await _sync(client, admin, source_id)
        res = await client.get("/api/calendar/events", params={"start": (start - timedelta(hours=1)).isoformat(),
                                                                "end": (start + timedelta(days=1)).isoformat()},
                               headers=_h(admin))
        by_title = {e["title"]: e for e in res.json()}
        game = by_title["game"]
        assert (game["location"], game["url"], game["organizer"], game["attendees"]) == (
            "Field 3", "https://club.example/g", "Coach Lee", ["Sam", "Pat"])
        assert (by_title["practice"]["url"], by_title["practice"]["attendees"]) == (None, None)


class TestLocalEventLinks:
    async def make(self, client, who, **extra):
        return await client.post("/api/calendar/events", headers=_h(who), json={
            "title": "Dinner", "start_dt": "2026-10-20T22:00:00Z", "end_dt": "2026-10-20T23:00:00Z", **extra})

    async def test_an_event_added_here_can_carry_a_link(self, client, admin):
        res = await self.make(client, admin, location="Nonna's", url="https://maps.example/nonna")
        assert res.status_code in (200, 201), res.text
        event = res.json()
        assert event["url"] == "https://maps.example/nonna" and event["organizer"] is None
        got = (await client.get(f"/api/calendar/events/{event['id']}", headers=_h(admin))).json()
        assert got["url"] == "https://maps.example/nonna" and got["location"] == "Nonna's"

    @pytest.mark.parametrize("bad", ["javascript:alert(1)", "ftp://x.example/f", "not a link", "https://" + "x" * 2050])
    async def test_only_web_links(self, client, admin, bad):
        assert (await self.make(client, admin, url=bad)).status_code == 422

    async def test_a_link_can_be_changed_and_cleared(self, client, admin):
        event = (await self.make(client, admin, url="https://a.example")).json()
        res = await client.patch(f"/api/calendar/events/{event['id']}", json={"url": "https://b.example"}, headers=_h(admin))
        assert res.json()["url"] == "https://b.example"
        res = await client.patch(f"/api/calendar/events/{event['id']}", json={"url": ""}, headers=_h(admin))
        assert res.status_code == 200 and res.json()["url"] is None
        res = await client.patch(f"/api/calendar/events/{event['id']}", json={"title": "Supper"}, headers=_h(admin))
        assert res.json()["url"] is None and res.json()["title"] == "Supper"

    async def test_members_see_the_details_of_family_events(self, client, admin):
        event = (await self.make(client, admin, location="Nonna's", description="Bring dessert", url="https://a.example")).json()
        kid = await _member(client, admin)
        got = (await client.get(f"/api/calendar/events/{event['id']}", headers=_h(kid))).json()
        assert (got["location"], got["description"], got["url"]) == ("Nonna's", "Bring dessert", "https://a.example")
