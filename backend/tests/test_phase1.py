"""Regression tests for the Phase 1 review fixes (timezones, ranges, sources, wall)."""
import pytest

SETUP = {
    "family_name": "Test Family",
    "timezone": "America/Detroit",
    "admin_display_name": "Admin User",
    "admin_password": "securepassword123",
}


def _cookie(response, name):
    """Extract 'name=value' from a Set-Cookie header (the test client is http,
    so Secure cookies aren't stored automatically)."""
    for header in response.headers.get_list("set-cookie"):
        if header.startswith(f"{name}="):
            return header.split(";", 1)[0]
    raise AssertionError(f"{name} cookie not set")


@pytest.fixture
async def admin(client):
    res = await client.post("/api/auth/setup", json=SETUP)
    assert res.status_code == 200
    return {"Cookie": _cookie(res, "access_token")}


async def _create_event(client, admin, title, start, end, all_day=False):
    res = await client.post(
        "/api/calendar/events",
        json={"title": title, "start_dt": start, "end_dt": end, "all_day": all_day},
        headers=admin,
    )
    assert res.status_code == 201, res.text
    return res.json()


async def _list(client, headers, start, end, path="/api/calendar/events"):
    res = await client.get(path, params={"start": start, "end": end}, headers=headers)
    assert res.status_code == 200, res.text
    return res.json()


class TestTimezones:
    async def test_offset_input_is_returned_as_utc(self, client, admin):
        ev = await _create_event(
            client, admin, "Dentist", "2026-10-04T15:00:00-04:00", "2026-10-04T16:00:00-04:00"
        )
        assert ev["start_dt"] == "2026-10-04T19:00:00+00:00"
        assert ev["end_dt"] == "2026-10-04T20:00:00+00:00"

    async def test_range_query_compares_instants(self, client, admin):
        await _create_event(
            client, admin, "Evening", "2026-10-04T21:00:00-04:00", "2026-10-04T22:00:00-04:00"
        )
        # 21:00 Detroit is 01:00Z on the 5th: inside a Detroit "Oct 4" window...
        local_day = await _list(client, admin, "2026-10-04T04:00:00Z", "2026-10-05T04:00:00Z")
        assert [e["title"] for e in local_day] == ["Evening"]
        # ...and outside the UTC calendar day of Oct 4.
        utc_day = await _list(client, admin, "2026-10-04T00:00:00Z", "2026-10-05T00:00:00Z")
        assert utc_day == []

    async def test_end_before_start_is_rejected(self, client, admin):
        res = await client.post(
            "/api/calendar/events",
            json={"title": "x", "start_dt": "2026-10-04T10:00:00Z", "end_dt": "2026-10-04T09:00:00Z"},
            headers=admin,
        )
        assert res.status_code == 400

    async def test_invalid_datetime_is_400_not_500(self, client, admin):
        res = await client.get(
            "/api/calendar/events", params={"start": "nope", "end": "nope"}, headers=admin
        )
        assert res.status_code == 400


class TestRangeOverlap:
    async def test_multi_day_event_started_before_window_is_returned(self, client, admin):
        await _create_event(
            client, admin, "Vacation", "2026-10-01T00:00:00Z", "2026-10-06T00:00:00Z", all_day=True
        )
        await _create_event(
            client, admin, "Later", "2026-10-10T10:00:00Z", "2026-10-10T11:00:00Z"
        )
        events = await _list(client, admin, "2026-10-03T00:00:00Z", "2026-10-04T00:00:00Z")
        assert [e["title"] for e in events] == ["Vacation"]


class TestSources:
    async def _ical_source(self, client, admin):
        res = await client.post(
            "/api/calendar/sources",
            json={"display_name": "School", "ics_url": "https://example.test/school.ics"},
            headers=admin,
        )
        assert res.status_code == 201, res.text
        return res.json()

    async def test_sync_now_runs_the_sync(self, client, admin, monkeypatch):
        from datetime import datetime, timezone

        async def fake_fetch(url):
            return [{
                "external_uid": "abc",
                "title": "Field trip",
                "start_dt": datetime(2026, 10, 7, 13, tzinfo=timezone.utc),
                "end_dt": datetime(2026, 10, 7, 15, tzinfo=timezone.utc),
                "all_day": False,
                "location": None,
                "description": None,
            }]

        monkeypatch.setattr("app.jobs.calendar_sync.fetch_and_parse", fake_fetch)
        source = await self._ical_source(client, admin)
        res = await client.post(f"/api/calendar/sources/{source['id']}/sync", headers=admin)
        assert res.status_code == 200
        assert res.json() == {"ok": True, "error": None}
        events = await _list(client, admin, "2026-10-07T00:00:00Z", "2026-10-08T00:00:00Z")
        assert [e["title"] for e in events] == ["Field trip"]

    async def test_sync_error_is_reported(self, client, admin, monkeypatch):
        async def failing_fetch(url):
            raise ValueError("ICS fetch returned HTTP 404")

        monkeypatch.setattr("app.jobs.calendar_sync.fetch_and_parse", failing_fetch)
        source = await self._ical_source(client, admin)
        res = await client.post(f"/api/calendar/sources/{source['id']}/sync", headers=admin)
        assert res.json() == {"ok": False, "error": "ICS fetch returned HTTP 404"}

    async def test_deleted_source_is_hidden_with_its_events(self, client, admin, monkeypatch):
        from datetime import datetime, timezone

        async def fake_fetch(url):
            return [{
                "external_uid": "x1", "title": "Game",
                "start_dt": datetime(2026, 10, 8, 18, tzinfo=timezone.utc),
                "end_dt": datetime(2026, 10, 8, 20, tzinfo=timezone.utc),
                "all_day": False, "location": None, "description": None,
            }]

        monkeypatch.setattr("app.jobs.calendar_sync.fetch_and_parse", fake_fetch)
        source = await self._ical_source(client, admin)
        await client.post(f"/api/calendar/sources/{source['id']}/sync", headers=admin)

        res = await client.delete(f"/api/calendar/sources/{source['id']}", headers=admin)
        assert res.status_code == 200
        sources = (await client.get("/api/calendar/sources", headers=admin)).json()
        assert source["id"] not in [s["id"] for s in sources]
        assert await _list(client, admin, "2026-10-08T00:00:00Z", "2026-10-09T00:00:00Z") == []

    async def test_internal_source_cannot_be_deleted(self, client, admin):
        ev = await _create_event(
            client, admin, "Dinner", "2026-10-04T22:00:00Z", "2026-10-04T23:00:00Z"
        )
        res = await client.delete(f"/api/calendar/sources/{ev['source_id']}", headers=admin)
        assert res.status_code == 400


class TestWallPairing:
    async def test_pair_read_and_revoke(self, client, admin):
        await _create_event(
            client, admin, "Soccer", "2026-10-05T21:00:00Z", "2026-10-05T22:00:00Z"
        )
        res = await client.post("/api/wall/devices", json={"name": "Kitchen"}, headers=admin)
        assert res.status_code == 201
        device = res.json()

        # Unpaired: no access, and no family data.
        assert (await client.get("/api/wall/session")).status_code == 401

        res = await client.post("/api/wall/pair", json={"token": device["token"]})
        assert res.status_code == 200
        wall = {"Cookie": _cookie(res, "wall_token")}

        res = await client.get("/api/wall/session", headers=wall)
        assert res.status_code == 200
        assert res.json()["device"] == "Kitchen"
        assert "wall_token=" in res.headers.get("set-cookie", "")  # sliding refresh

        events = await _list(
            client, wall, "2026-10-05T00:00:00Z", "2026-10-06T00:00:00Z", path="/api/wall/events"
        )
        assert [e["title"] for e in events] == ["Soccer"]
        members = (await client.get("/api/wall/members", headers=wall)).json()
        assert [m["display_name"] for m in members] == ["Admin User"]

        res = await client.delete(f"/api/wall/devices/{device['id']}", headers=admin)
        assert res.status_code == 200
        assert (await client.get("/api/wall/session", headers=wall)).status_code == 401

    async def test_bad_token_is_rejected(self, client):
        res = await client.post("/api/wall/pair", json={"token": "not-a-real-token"})
        assert res.status_code == 401

    async def test_wall_device_cannot_use_user_endpoints(self, client, admin):
        device = (await client.post("/api/wall/devices", json={"name": "Hall"}, headers=admin)).json()
        res = await client.post("/api/wall/pair", json={"token": device["token"]})
        wall = {"Cookie": _cookie(res, "wall_token")}
        assert (await client.get("/api/users/", headers=wall)).status_code == 401
