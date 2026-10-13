"""Live-update notices: published after commit, and from background syncs too."""
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import pytest

from app.core.events import discard_queued, event_bus, publish_queued, queue_event

SETUP = {
    "family_name": "Test Family",
    "timezone": "America/Detroit",
    "admin_display_name": "Admin User",
    "admin_password": "securepassword123",
}


def _cookie(response, name="access_token"):
    for header in response.headers.get_list("set-cookie"):
        if header.startswith(f"{name}="):
            return header.split(";", 1)[0]
    raise AssertionError(f"{name} cookie not set")


@pytest.fixture
def heard():
    """Record every event the bus publishes during the test."""
    events = []

    async def listener(event_type, payload):
        events.append((event_type, payload))

    unsubscribe = event_bus.subscribe(listener)
    yield events
    unsubscribe()


class _FakeSession:
    def __init__(self):
        self.info = {}


class TestQueue:
    async def test_nothing_is_published_until_publish_queued(self, heard):
        db = _FakeSession()
        queue_event(db, "calendar_updated", {"source_id": "s1"})
        queue_event(db, "calendar_updated", {"source_id": "s1"})  # duplicate collapses
        assert heard == []
        await publish_queued(db)
        assert heard == [("calendar_updated", {"source_id": "s1"})]
        await publish_queued(db)  # already drained
        assert len(heard) == 1

    async def test_discard_drops_queued_events(self, heard):
        db = _FakeSession()
        queue_event(db, "calendar_updated", {"source_id": "s1"})
        discard_queued(db)
        await publish_queued(db)
        assert heard == []


class TestBackgroundSync:
    async def test_scheduled_sync_notifies_walls_after_commit(self, client, setup_db, monkeypatch, heard):
        admin = await client.post("/api/auth/setup", json=SETUP)
        headers = {"Cookie": _cookie(admin)}
        source = (await client.post(
            "/api/calendar/sources",
            json={"display_name": "School", "ics_url": "https://example.test/s.ics"},
            headers=headers,
        )).json()

        async def fake_fetch(url, **kwargs):
            return [{
                "external_uid": "u1", "title": "Assembly",
                "start_dt": datetime(2026, 10, 20, 13, tzinfo=timezone.utc),
                "end_dt": datetime(2026, 10, 20, 14, tzinfo=timezone.utc),
                "all_day": False, "location": None, "description": None,
            }]

        monkeypatch.setattr("app.jobs.calendar_sync.fetch_and_parse", fake_fetch)

        committed_when_heard = []
        original_commit = setup_db.commit

        async def tracking_commit():
            await original_commit()
            committed_when_heard.append("commit")

        monkeypatch.setattr(setup_db, "commit", tracking_commit)

        async def listener(event_type, payload):
            committed_when_heard.append("publish")

        unsubscribe = event_bus.subscribe(listener)

        @asynccontextmanager
        async def session_factory():
            yield setup_db

        monkeypatch.setattr("app.jobs.calendar_sync.AsyncSessionLocal", session_factory)
        from app.jobs.calendar_sync import sync_all_due

        try:
            await sync_all_due()
        finally:
            unsubscribe()

        assert ("calendar_updated", {"source_id": source["id"]}) in heard
        # The notice goes out only after the scheduler's commit.
        assert committed_when_heard == ["commit", "publish"]

    async def test_manual_sync_queues_one_notice(self, client, setup_db, monkeypatch):
        admin = await client.post("/api/auth/setup", json=SETUP)
        headers = {"Cookie": _cookie(admin)}
        source = (await client.post(
            "/api/calendar/sources",
            json={"display_name": "School", "ics_url": "https://example.test/s.ics"},
            headers=headers,
        )).json()

        async def fake_fetch(url, **kwargs):
            return []

        monkeypatch.setattr("app.jobs.calendar_sync.fetch_and_parse", fake_fetch)
        setup_db.info.pop("pending_events", None)
        res = await client.post(f"/api/calendar/sources/{source['id']}/sync", headers=headers)
        assert res.status_code == 200
        assert setup_db.info.get("pending_events") == [("calendar_updated", {"source_id": source["id"]})]
