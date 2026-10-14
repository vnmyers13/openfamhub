"""Calendar source and event routes not covered elsewhere: editing sources,
sync logs, event edits and their validation."""
from datetime import datetime, timedelta, timezone

import pytest

from tests.test_phase2 import SETUP, _cookie, _event, _h, _member


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


async def _feed_source(client, admin):
    res = await client.post(
        "/api/calendar/sources",
        json={"display_name": "School", "ics_url": "https://example.test/s.ics"},
        headers=_h(admin),
    )
    assert res.status_code == 201, res.text
    return res.json()


def feeds(by_url: dict):
    """A fake fetch_and_parse: each URL serves events with the given uids; any other URL is unreachable."""
    soon = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(days=7)
    seen = []

    async def fake_fetch(url, **kwargs):
        seen.append(url)
        if url not in by_url:
            raise ConnectionError("Name or service not known")
        return [{"external_uid": uid, "title": f"Event {uid}", "all_day": False, "location": None,
                 "description": None, "start_dt": soon + timedelta(hours=i), "end_dt": soon + timedelta(hours=i + 1)}
                for i, uid in enumerate(by_url[url])]

    fake_fetch.seen = seen
    return fake_fetch


async def titles(client, who):
    now = datetime.now(timezone.utc)
    res = await client.get("/api/calendar/events", headers=_h(who),
                           params={"start": now.isoformat(), "end": (now + timedelta(days=30)).isoformat()})
    assert res.status_code == 200, res.text
    return {e["title"]: e for e in res.json()}


class TestSources:
    async def test_admin_edits_a_source(self, client, admin, monkeypatch):
        monkeypatch.setattr("app.jobs.calendar_sync.fetch_and_parse", feeds({"https://example.test/n.ics": ["n1"]}))
        src = await _feed_source(client, admin)
        res = await client.patch(
            f"/api/calendar/sources/{src['id']}",
            json={"display_name": "School (new)", "color_hex": "#10B981", "ics_url": "https://example.test/n.ics",
                  "sync_interval_hours": 12, "enabled": False},
            headers=_h(admin),
        )
        assert res.status_code == 200, res.text
        body = res.json()
        assert (body["display_name"], body["color_hex"], body["ics_url"], body["sync_interval_hours"], body["enabled"]) == (
            "School (new)", "#10B981", "https://example.test/n.ics", 12, False,
        )

    async def test_empty_patch_changes_nothing(self, client, admin):
        src = await _feed_source(client, admin)
        res = await client.patch(f"/api/calendar/sources/{src['id']}", json={}, headers=_h(admin))
        assert res.status_code == 200 and res.json()["display_name"] == "School"

    async def test_bad_color_is_rejected(self, client, admin):
        src = await _feed_source(client, admin)
        res = await client.patch(f"/api/calendar/sources/{src['id']}", json={"color_hex": "green"}, headers=_h(admin))
        assert res.status_code == 422

    async def test_unknown_sources_are_404(self, client, admin):
        for method, path in [("patch", "/api/calendar/sources/nope"), ("delete", "/api/calendar/sources/nope"),
                             ("post", "/api/calendar/sources/nope/sync"), ("get", "/api/calendar/sources/nope/log")]:
            kwargs = {"json": {}} if method == "patch" else {}
            res = await getattr(client, method)(path, headers=_h(admin), **kwargs)
            assert res.status_code == 404, (method, path, res.text)

    async def test_members_cannot_edit_sources(self, client, admin):
        src = await _feed_source(client, admin)
        kid = await _member(client, admin)
        res = await client.patch(f"/api/calendar/sources/{src['id']}", json={"display_name": "x"}, headers=_h(kid))
        assert res.status_code == 403

    async def test_sync_log_lists_runs(self, client, admin, monkeypatch):
        async def fake_fetch(url, **kwargs):
            return [{"external_uid": "u", "title": "Game", "all_day": False, "location": None, "description": None,
                     "start_dt": datetime(2026, 10, 20, 18, tzinfo=timezone.utc),
                     "end_dt": datetime(2026, 10, 20, 19, tzinfo=timezone.utc)}]

        monkeypatch.setattr("app.jobs.calendar_sync.fetch_and_parse", fake_fetch)
        src = await _feed_source(client, admin)
        await client.post(f"/api/calendar/sources/{src['id']}/sync", headers=_h(admin))
        logs = (await client.get(f"/api/calendar/sources/{src['id']}/log", headers=_h(admin))).json()
        assert len(logs) == 1 and logs[0]["events_upserted"] == 1 and logs[0]["error"] is None

    async def test_the_family_calendar_cannot_be_synced(self, client, admin):
        ev = (await _event(client, admin)).json()
        res = await client.post(f"/api/calendar/sources/{ev['source_id']}/sync", headers=_h(admin))
        assert res.status_code == 400


class TestEditingFeeds:
    """Admin › Calendars › Edit: name, color, URL, sync interval and on/off."""

    async def test_a_rename_and_recolor_show_on_existing_events(self, client, admin, monkeypatch):
        monkeypatch.setattr("app.jobs.calendar_sync.fetch_and_parse", feeds({"https://example.test/s.ics": ["a"]}))
        src = await _feed_source(client, admin)
        await client.post(f"/api/calendar/sources/{src['id']}/sync", headers=_h(admin))
        res = await client.patch(f"/api/calendar/sources/{src['id']}", headers=_h(admin),
                                 json={"display_name": "Soccer", "color_hex": "#DC2626"})
        assert res.status_code == 200, res.text
        assert (await titles(client, admin))["Event a"]["source_color_hex"] == "#DC2626"

    async def test_a_new_url_replaces_the_old_feeds_events(self, client, admin, monkeypatch):
        fake = feeds({"https://example.test/s.ics": ["a", "b"], "https://example.test/new.ics": ["c"]})
        monkeypatch.setattr("app.jobs.calendar_sync.fetch_and_parse", fake)
        src = await _feed_source(client, admin)
        await client.post(f"/api/calendar/sources/{src['id']}/sync", headers=_h(admin))
        assert {"Event a", "Event b"} <= set(await titles(client, admin))
        res = await client.patch(f"/api/calendar/sources/{src['id']}", headers=_h(admin),
                                 json={"ics_url": "https://example.test/new.ics"})
        assert res.status_code == 200, res.text
        assert res.json()["ics_url"] == "https://example.test/new.ics" and res.json()["last_synced_at"]
        got = set(await titles(client, admin))
        assert "Event c" in got and not {"Event a", "Event b"} & got

    async def test_a_bad_url_is_refused_and_the_old_one_kept(self, client, admin, monkeypatch):
        monkeypatch.setattr("app.jobs.calendar_sync.fetch_and_parse", feeds({"https://example.test/s.ics": ["a"]}))
        src = await _feed_source(client, admin)
        await client.post(f"/api/calendar/sources/{src['id']}/sync", headers=_h(admin))
        res = await client.patch(f"/api/calendar/sources/{src['id']}", headers=_h(admin),
                                 json={"ics_url": "https://nowhere.test/x.ics", "display_name": "Renamed"})
        assert res.status_code == 400 and res.json()["detail"]
        kept = [s for s in (await client.get("/api/calendar/sources", headers=_h(admin))).json() if s["id"] == src["id"]][0]
        assert (kept["ics_url"], kept["display_name"], kept["sync_error"]) == ("https://example.test/s.ics", "School", None)
        assert "Event a" in await titles(client, admin)

    async def test_webcal_links_are_accepted(self, client, admin, monkeypatch):
        fake = feeds({"https://example.test/s.ics": ["a"], "webcal://example.test/team.ics": ["t"]})
        monkeypatch.setattr("app.jobs.calendar_sync.fetch_and_parse", fake)
        src = await _feed_source(client, admin)
        res = await client.patch(f"/api/calendar/sources/{src['id']}", headers=_h(admin),
                                 json={"ics_url": " webcal://example.test/team.ics "})
        assert res.status_code == 200, res.text
        assert res.json()["ics_url"] == "webcal://example.test/team.ics" and "Event t" in await titles(client, admin)

    async def test_the_same_url_is_not_fetched_again(self, client, admin, monkeypatch):
        fake = feeds({"https://example.test/s.ics": ["a"]})
        monkeypatch.setattr("app.jobs.calendar_sync.fetch_and_parse", fake)
        src = await _feed_source(client, admin)
        res = await client.patch(f"/api/calendar/sources/{src['id']}", headers=_h(admin),
                                 json={"ics_url": "https://example.test/s.ics", "sync_interval_hours": 24})
        assert res.status_code == 200 and res.json()["sync_interval_hours"] == 24
        assert fake.seen == []

    async def test_the_family_calendar_has_no_url_and_names_cant_be_blank(self, client, admin):
        ev = (await _event(client, admin)).json()
        res = await client.patch(f"/api/calendar/sources/{ev['source_id']}", headers=_h(admin),
                                 json={"ics_url": "https://example.test/s.ics"})
        assert res.status_code == 400
        src = await _feed_source(client, admin)
        for bad in ({"display_name": "   "}, {"ics_url": "ftp://example.test/s.ics"}, {"sync_interval_hours": 0}):
            res = await client.patch(f"/api/calendar/sources/{src['id']}", headers=_h(admin), json=bad)
            assert res.status_code == 422, (bad, res.text)


class TestEvents:
    async def test_edit_every_field(self, client, admin):
        ev = (await _event(client, admin)).json()
        res = await client.patch(
            f"/api/calendar/events/{ev['id']}",
            json={"title": "Late dinner", "start_dt": "2026-10-10T23:00:00Z", "end_dt": "2026-10-11T00:30:00Z",
                  "all_day": False, "location": "Home", "description": "Bring dessert"},
            headers=_h(admin),
        )
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["title"] == "Late dinner" and body["location"] == "Home" and body["description"] == "Bring dessert"
        assert body["start_dt"] == "2026-10-10T23:00:00+00:00" and body["end_dt"] == "2026-10-11T00:30:00+00:00"

    async def test_get_one_event(self, client, admin):
        ev = (await _event(client, admin)).json()
        res = await client.get(f"/api/calendar/events/{ev['id']}", headers=_h(admin))
        assert res.status_code == 200 and res.json()["title"] == "Dinner"

    async def test_end_must_follow_start(self, client, admin):
        ev = (await _event(client, admin)).json()
        res = await client.patch(f"/api/calendar/events/{ev['id']}", json={"end_dt": "2026-10-10T21:00:00Z"}, headers=_h(admin))
        assert res.status_code == 400
        res = await client.post(
            "/api/calendar/events",
            json={"title": "Backwards", "start_dt": "2026-10-10T22:00:00Z", "end_dt": "2026-10-10T21:00:00Z"},
            headers=_h(admin),
        )
        assert res.status_code == 400

    async def test_unparseable_times_are_400(self, client, admin):
        res = await client.post(
            "/api/calendar/events",
            json={"title": "Bad", "start_dt": "tomorrow-ish", "end_dt": "2026-10-10T21:00:00Z"},
            headers=_h(admin),
        )
        assert res.status_code in (400, 422)

    async def test_unknown_events_are_404(self, client, admin):
        assert (await client.get("/api/calendar/events/nope", headers=_h(admin))).status_code == 404
        assert (await client.patch("/api/calendar/events/nope", json={"title": "x"}, headers=_h(admin))).status_code == 404
        assert (await client.delete("/api/calendar/events/nope", headers=_h(admin))).status_code == 404

    async def test_deleted_events_disappear(self, client, admin):
        ev = (await _event(client, admin)).json()
        assert (await client.delete(f"/api/calendar/events/{ev['id']}", headers=_h(admin))).status_code == 200
        assert (await client.get(f"/api/calendar/events/{ev['id']}", headers=_h(admin))).status_code == 404
