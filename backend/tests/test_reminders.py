"""Phase 11: the reminder engine (jobs/reminders.py), run every minute.

Event reminders (each person: off by default, "mine" or "all", N minutes
before), a morning nudge with today's chores and to-dos, and reward requests
for admins. Each is sent once; nothing is sent in quiet hours (the wall's
sleep schedule); people without a device get nothing."""
from contextlib import asynccontextmanager
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from tests.test_phase2 import SETUP, _cookie, _h, _member
from tests.test_push import Phone

ZONE = ZoneInfo(SETUP["timezone"])
TODAY = datetime.now(timezone.utc).astimezone(ZONE).date()


def local(hh: int, mm: int = 0, day=TODAY) -> datetime:
    return datetime.combine(day, time(hh, mm), ZONE).astimezone(timezone.utc)


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
def inbox(monkeypatch):
    """Capture what would be pushed, per person, instead of contacting a push service."""
    from app.services import push as push_svc

    sent: list[tuple[str, dict]] = []

    async def fake_send(db, user_ids, payload):
        ids = list(user_ids)
        for uid in ids:
            sent.append((uid, payload))
        return len(ids)

    monkeypatch.setattr(push_svc, "send_to_users", fake_send)
    return sent


@pytest.fixture
def run(setup_db, monkeypatch):
    from app.jobs import reminders

    @asynccontextmanager
    async def shared_session():
        yield setup_db

    monkeypatch.setattr(reminders, "session_factory", shared_session)
    return reminders.run_reminders


async def device(client, who):
    res = await client.post("/api/push/subscriptions", json=Phone(f"https://push.example.test/{who['id']}").subscription(),
                            headers=_h(who))
    assert res.status_code == 201, res.text


async def notify(client, who, **prefs):
    current = (await client.get("/api/users/me/preferences", headers=_h(who))).json()
    current["notifications"] = {**current.get("notifications", {}), **prefs}
    res = await client.put("/api/users/me/preferences", json=current, headers=_h(who))
    assert res.status_code == 200, res.text


async def event(client, who, title, start: datetime, minutes=60, all_day=False):
    res = await client.post("/api/calendar/events", headers=_h(who), json={
        "title": title, "start_dt": start.isoformat(), "end_dt": (start + timedelta(minutes=minutes)).isoformat(),
        "all_day": all_day})
    assert res.status_code in (200, 201), res.text
    return res.json()


class TestEvents:
    async def test_off_by_default(self, client, admin, inbox, run):
        await device(client, admin)
        await event(client, admin, "Dentist", local(15, 30))
        await run(now=local(15, 20))
        assert inbox == []

    async def test_mine_before_the_start_once(self, client, admin, inbox, run):
        await device(client, admin)
        await notify(client, admin, events="mine", event_minutes=15)
        await event(client, admin, "Dentist", local(15, 30))
        await run(now=local(15, 10))  # 20 minutes before: too early
        assert inbox == []
        await run(now=local(15, 16))
        assert [(u, p["title"]) for u, p in inbox] == [(admin["id"], "Dentist")]
        assert "15:30" in inbox[0][1]["body"]
        await run(now=local(15, 17))
        assert len(inbox) == 1  # once
        await run(now=local(15, 31))  # started: never late
        assert len(inbox) == 1

    async def test_mine_skips_other_peoples_events_and_all_includes_them(self, client, admin, inbox, run):
        kid = await _member(client, admin)
        await device(client, admin)
        await device(client, kid)
        await notify(client, admin, events="mine")
        await notify(client, kid, events="all")
        await event(client, kid, "Soccer", local(16, 0))
        await run(now=local(15, 50))
        assert sorted(u for u, _ in inbox) == [kid["id"]]

    async def test_all_day_events_get_no_reminder(self, client, admin, inbox, run):
        await device(client, admin)
        await notify(client, admin, events="all")
        start = datetime.combine(TODAY, time(0), timezone.utc)
        await event(client, admin, "Holiday", start, minutes=24 * 60, all_day=True)
        await run(now=local(0, 1))
        assert inbox == []


class TestDailyNudge:
    async def make_chore(self, client, admin, kid, title="Feed the cat"):
        res = await client.post("/api/chores/templates", headers=_h(admin), json={
            "title": title, "points": 5, "assignment": "assigned", "assigned_to": kid["id"], "repeat": None})
        assert res.status_code == 201, res.text

    async def test_at_the_chosen_time_once_a_day_with_whats_due(self, client, admin, inbox, run):
        kid = await _member(client, admin)
        await device(client, kid)
        await self.make_chore(client, admin, kid)
        await client.post("/api/todos", json={"title": "Library book", "assigned_to": kid["id"], "due_date": TODAY.isoformat()},
                          headers=_h(admin))
        await run(now=local(6, 59))
        assert inbox == []
        await run(now=local(7, 1))
        assert len(inbox) == 1 and inbox[0][0] == kid["id"]
        body = inbox[0][1]["body"]
        assert "Feed the cat" in body and "Library book" in body
        await run(now=local(12, 0))
        assert len(inbox) == 1

    async def test_nothing_due_means_no_nudge_and_it_can_be_turned_off(self, client, admin, inbox, run):
        kid = await _member(client, admin)
        await device(client, kid)
        await device(client, admin)
        await notify(client, kid, daily=False)
        await self.make_chore(client, admin, kid)
        await run(now=local(7, 30))
        assert inbox == []  # kid turned it off; Mom has nothing due

    async def test_a_later_time_is_honored(self, client, admin, inbox, run):
        kid = await _member(client, admin)
        await device(client, kid)
        await notify(client, kid, daily_time="16:00")
        await self.make_chore(client, admin, kid)
        await run(now=local(9, 0))
        assert inbox == []
        await run(now=local(16, 0))
        assert len(inbox) == 1


class TestRewardRequests:
    async def request(self, client, admin, kid):
        await client.post("/api/rewards/points/adjust", json={"user_id": kid["id"], "delta": 50, "reason": "Start"}, headers=_h(admin))
        reward = (await client.post("/api/rewards/catalog", headers=_h(admin), json={
            "name": "Movie night", "icon": "🎬", "point_cost": 30, "needs_approval": True})).json()
        res = await client.post(f"/api/rewards/catalog/{reward['id']}/redeem", headers=_h(kid))
        assert res.status_code == 201, res.text
        return res.json()

    async def test_admins_hear_about_a_waiting_request_once(self, client, admin, inbox, run):
        kid = await _member(client, admin)
        await device(client, admin)
        await device(client, kid)
        await self.request(client, admin, kid)
        await run(now=datetime.now(timezone.utc))
        assert [u for u, _ in inbox] == [admin["id"]]
        assert "Kid" in inbox[0][1]["body"] and "Movie night" in inbox[0][1]["body"]
        await run(now=datetime.now(timezone.utc))
        assert len(inbox) == 1

    async def test_an_admin_can_turn_them_off_and_decided_requests_are_skipped(self, client, admin, inbox, run):
        kid = await _member(client, admin)
        await device(client, admin)
        red = await self.request(client, admin, kid)
        await client.post(f"/api/rewards/redemptions/{red['id']}/approve", headers=_h(admin))
        await run(now=datetime.now(timezone.utc))
        assert inbox == []
        await notify(client, admin, rewards=False)
        await self.request(client, admin, kid)
        await run(now=datetime.now(timezone.utc))
        assert inbox == []


class TestQuietHoursAndDevices:
    async def test_nothing_during_the_walls_sleep_then_waiting_things_go_out(self, client, admin, inbox, run):
        await client.patch("/api/family", json={"sleep": {"enabled": True, "off": "22:00", "on": "06:30"}}, headers=_h(admin))
        kid = await _member(client, admin)
        await device(client, admin)
        await notify(client, admin, events="mine")
        await event(client, admin, "Late call", local(23, 10))
        await TestRewardRequests().request(client, admin, kid)
        await run(now=local(23, 0))
        assert inbox == []  # quiet: the late event's reminder is skipped, the request waits
        await run(now=local(6, 31) + timedelta(days=1))
        assert [p["tag"].split(":")[0] for _, p in inbox] == ["reward"]

    async def test_people_without_a_device_get_nothing(self, client, admin, inbox, run):
        await notify(client, admin, events="mine")
        await event(client, admin, "Dentist", local(15, 30))
        await run(now=local(15, 20))
        assert inbox == []

    async def test_bad_preferences_are_refused(self, client, admin):
        current = (await client.get("/api/users/me/preferences", headers=_h(admin))).json()
        for bad in ({"events": "sometimes"}, {"event_minutes": 7}, {"daily_time": "25:00"}):
            res = await client.put("/api/users/me/preferences", json={**current, "notifications": bad}, headers=_h(admin))
            assert res.status_code == 422, bad


def test_quiet_hours_overnight_daytime_and_across_dst():
    from app.jobs.reminders import in_quiet_hours
    from app.schemas.family import SleepSchedule

    night = SleepSchedule(enabled=True, off="22:00", on="06:30")
    at = lambda h, m=0, d=TODAY: datetime.combine(d, time(h, m), ZONE)  # noqa: E731
    assert in_quiet_hours(night, at(22, 0)) and in_quiet_hours(night, at(3, 0)) and in_quiet_hours(night, at(6, 29))
    assert not in_quiet_hours(night, at(6, 30)) and not in_quiet_hours(night, at(21, 59))
    nap = SleepSchedule(enabled=True, off="13:00", on="15:00")
    assert in_quiet_hours(nap, at(14, 0)) and not in_quiet_hours(nap, at(15, 0))
    assert not in_quiet_hours(SleepSchedule(enabled=False, off="22:00", on="06:30"), at(23, 0))
    # 1 Nov 2026, the night clocks go back in Detroit: 06:00 local is 11:00Z, not 10:00Z.
    from datetime import date
    dst = datetime(2026, 11, 1, 11, 0, tzinfo=timezone.utc).astimezone(ZONE)
    assert (dst.hour, dst.minute) == (6, 0) and in_quiet_hours(night, dst)
    assert not in_quiet_hours(night, datetime(2026, 11, 1, 11, 31, tzinfo=timezone.utc).astimezone(ZONE))
    assert date(2026, 11, 1) == dst.date()
