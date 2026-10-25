"""Phase 11: the reminder engine (jobs/reminders.py), run every minute.

Event reminders (each person: off by default, "mine" or "all", N minutes
before), a morning nudge with today's chores and to-dos, and reward requests
for admins; the day before a birthday, pantry food reaching its use-by date,
and allowance paid (Phase 11, more reminders). Each is sent once; nothing is sent in quiet hours (the wall's
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


def _born(turns: int, on):
    try:
        return on.replace(year=on.year - turns)
    except ValueError:  # tomorrow is 29 Feb
        return on.replace(year=on.year - turns - 4)


class TestBirthdays:
    async def test_the_day_before_at_the_morning_time_to_everyone_but_them(self, client, admin, inbox, run):
        kid = await _member(client, admin)
        grandma = await _member(client, admin, name="Grandma", pin="1111", role="viewer")
        tomorrow = TODAY + timedelta(days=1)
        res = await client.patch(f"/api/users/{kid['id']}", json={"birthday": _born(10, tomorrow).isoformat()}, headers=_h(kid))
        assert res.status_code == 200, res.text
        for who in (admin, kid, grandma):
            await device(client, who)
        await run(now=local(6, 59))
        assert [p for _, p in inbox if p["tag"].startswith("birthday")] == []
        await run(now=local(7, 0))
        got = [(u, p) for u, p in inbox if p["tag"].startswith("birthday")]
        assert sorted(u for u, _ in got) == sorted([admin["id"], grandma["id"]])
        assert got[0][1]["title"] == "Tomorrow: Kid turns 10"
        await run(now=local(9, 0))
        assert len([1 for _, p in inbox if p["tag"].startswith("birthday")]) == 2

    async def test_not_on_other_days_and_it_can_be_turned_off(self, client, admin, inbox, run):
        kid = await _member(client, admin)
        sib = await _member(client, admin, name="Sib", pin="2468")
        await client.patch(f"/api/users/{kid['id']}", json={"birthday": _born(8, TODAY + timedelta(days=1)).isoformat()}, headers=_h(kid))
        await client.patch(f"/api/users/{sib['id']}", json={"birthday": _born(6, TODAY + timedelta(days=3)).isoformat()}, headers=_h(sib))
        await device(client, admin)
        await notify(client, admin, birthdays=False)
        await run(now=local(8, 0))
        assert [p for _, p in inbox if p["tag"].startswith("birthday")] == []

    async def test_week_before_notification(self, client, admin, inbox, run):
        """A birthday 7 days away sends a 'next week' notification to everyone but the birthday person."""
        kid = await _member(client, admin)
        sib = await _member(client, admin, name="Sib", pin="2468")
        a_week = TODAY + timedelta(days=7)
        await client.patch(f"/api/users/{kid['id']}", json={"birthday": _born(10, a_week).isoformat()}, headers=_h(kid))
        await device(client, admin)
        await device(client, sib)
        await notify(client, admin, birthdays_week_before=True)
        await notify(client, sib, birthdays_week_before=True)
        await run(now=local(7, 0))
        got = [(u, p) for u, p in inbox if p["tag"].startswith("birthday_week")]
        assert sorted(u for u, _ in got) == sorted([admin["id"], sib["id"]])
        assert got[0][1]["title"] == "Next week: Kid turns 10"
        await run(now=local(9, 0))
        assert len([1 for _, p in inbox if p["tag"].startswith("birthday_week")]) == 2

    async def test_week_before_can_be_turned_off(self, client, admin, inbox, run):
        kid = await _member(client, admin)
        a_week = TODAY + timedelta(days=7)
        await client.patch(f"/api/users/{kid['id']}", json={"birthday": _born(10, a_week).isoformat()}, headers=_h(kid))
        await device(client, admin)
        await notify(client, admin, birthdays_week_before=False)
        await run(now=local(7, 0))
        assert [p for _, p in inbox if p["tag"].startswith("birthday_week")] == []

    async def test_day_of_sends_happy_birthday_notification(self, client, admin, inbox, run):
        """On the birthday, everyone except the birthday person gets a 'Happy Birthday' notification."""
        kid = await _member(client, admin)
        sib = await _member(client, admin, name="Sib", pin="2468")
        await client.patch(f"/api/users/{kid['id']}", json={"birthday": _born(10, TODAY).isoformat()}, headers=_h(kid))
        await device(client, admin)
        await device(client, sib)
        await notify(client, admin, birthdays_day_of=True)
        await notify(client, sib, birthdays_day_of=True)
        await run(now=local(7, 0))
        got = [(u, p) for u, p in inbox if p["tag"].startswith("birthday_day")]
        assert sorted(u for u, _ in got) == sorted([admin["id"], sib["id"]])
        assert got[0][1]["title"] == "Happy Birthday, Kid! (turns 10)"
        await run(now=local(9, 0))
        assert len([1 for _, p in inbox if p["tag"].startswith("birthday_day")]) == 2

    async def test_day_of_can_be_turned_off(self, client, admin, inbox, run):
        kid = await _member(client, admin)
        await client.patch(f"/api/users/{kid['id']}", json={"birthday": _born(10, TODAY).isoformat()}, headers=_h(kid))
        await device(client, admin)
        await notify(client, admin, birthdays_day_of=False)
        await run(now=local(7, 0))
        assert [p for _, p in inbox if p["tag"].startswith("birthday_day")] == []

    async def test_birthday_person_does_not_get_their_own_notifications(self, client, admin, inbox, run):
        """The birthday person themselves never get their own birthday notifications."""
        kid = await _member(client, admin)
        a_week = TODAY + timedelta(days=7)
        await client.patch(f"/api/users/{kid['id']}", json={"birthday": _born(10, a_week).isoformat()}, headers=_h(kid))
        await device(client, kid)
        await run(now=local(7, 0))
        got = [(u, p) for u, p in inbox if p["tag"].startswith("birthday")]
        got_week = [p for _, p in inbox if p["tag"].startswith("birthday_week")]
        got_day = [p for _, p in inbox if p["tag"].startswith("birthday_day")]
        assert got == [] and got_week == [] and got_day == []


class TestPantry:
    async def item(self, client, admin, name, expires):
        res = await client.post("/api/meals/pantry", json={"name": name, "expires_on": expires.isoformat()}, headers=_h(admin))
        assert res.status_code in (200, 201), res.text

    async def test_one_list_of_what_reaches_its_use_by_today_or_tomorrow(self, client, admin, inbox, run):
        kid = await _member(client, admin)
        grandma = await _member(client, admin, name="Grandma", pin="1111", role="viewer")
        for who in (admin, kid, grandma):
            await device(client, who)
        await self.item(client, admin, "Milk", TODAY)
        await self.item(client, admin, "Yogurt", TODAY + timedelta(days=1))
        await self.item(client, admin, "Rice", TODAY + timedelta(days=30))
        await self.item(client, admin, "Old bread", TODAY - timedelta(days=5))
        await run(now=local(7, 5))
        got = [(u, p) for u, p in inbox if p["tag"].startswith("pantry")]
        assert sorted(u for u, _ in got) == sorted([admin["id"], kid["id"]])  # not viewers
        assert got[0][1]["title"] == "Use soon: 2 pantry items"
        assert got[0][1]["body"] == "Milk (today), Yogurt (tomorrow)"
        await run(now=local(12, 0))
        assert len([1 for _, p in inbox if p["tag"].startswith("pantry")]) == 2

    async def test_nothing_close_means_nothing_sent_and_it_can_be_turned_off(self, client, admin, inbox, run):
        kid = await _member(client, admin)
        await device(client, admin)
        await device(client, kid)
        await notify(client, kid, pantry=False)
        await run(now=local(7, 5))
        await self.item(client, admin, "Milk", TODAY)
        await run(now=local(7, 6))
        assert [u for u, p in inbox if p["tag"].startswith("pantry")] == [admin["id"]]


class TestAllowancePaid:
    async def pay(self, client, admin, setup_db, monkeypatch, kid, cents=500):
        from datetime import date

        from sqlalchemy import select

        from app.jobs import allowance
        from app.models.rewards import AllowancePlan

        res = await client.put(f"/api/rewards/allowance/{kid['id']}", json={"weekly_cents": cents}, headers=_h(admin))
        assert res.status_code == 200, res.text
        row = (await setup_db.execute(select(AllowancePlan).where(AllowancePlan.user_id == kid["id"]))).scalar_one()
        row.start_week = date(2026, 10, 19)
        await setup_db.flush()

        @asynccontextmanager
        async def shared_session():
            yield setup_db

        monkeypatch.setattr(allowance, "session_factory", shared_session)
        assert await allowance.run_allowance(now=datetime.combine(date(2026, 10, 19), time(7, 5), ZONE)) == 1

    async def test_the_child_hears_their_allowance_was_paid_once(self, client, admin, setup_db, monkeypatch, inbox, run):
        kid = await _member(client, admin)
        await device(client, kid)
        await device(client, admin)
        await self.pay(client, admin, setup_db, monkeypatch, kid)
        await run(now=datetime.now(timezone.utc))
        got = [(u, p) for u, p in inbox if p["tag"].startswith("allowance")]
        assert [u for u, _ in got] == [kid["id"]]
        assert got[0][1]["title"] == "Allowance paid: $5.00" and got[0][1]["url"] == "/rewards"
        await run(now=datetime.now(timezone.utc))
        assert len([1 for _, p in inbox if p["tag"].startswith("allowance")]) == 1

    async def test_it_can_be_turned_off(self, client, admin, setup_db, monkeypatch, inbox, run):
        kid = await _member(client, admin)
        await device(client, kid)
        await notify(client, kid, allowance=False)
        await self.pay(client, admin, setup_db, monkeypatch, kid)
        await run(now=datetime.now(timezone.utc))
        assert [p for _, p in inbox if p["tag"].startswith("allowance")] == []


class TestWellness:
    def kinds(self, inbox, kind):
        return [p for _, p in inbox if p["tag"].startswith(kind + ":")]

    async def test_off_by_default(self, client, admin, inbox, run):
        await device(client, admin)
        for hh in (9, 11, 15):
            await run(now=local(hh, 0))
        assert self.kinds(inbox, "water") == [] and self.kinds(inbox, "mindful") == []

    async def test_water_on_the_chosen_rhythm_between_the_chosen_times(self, client, admin, inbox, run):
        await device(client, admin)
        await notify(client, admin, water=True, water_every=120, water_from="09:00", water_until="20:00")
        await run(now=local(8, 59))
        assert self.kinds(inbox, "water") == []
        await run(now=local(9, 0))
        await run(now=local(9, 5))
        assert len(self.kinds(inbox, "water")) == 1
        assert "water" in self.kinds(inbox, "water")[0]["title"].lower()
        await run(now=local(10, 59))
        await run(now=local(11, 0))
        assert len(self.kinds(inbox, "water")) == 2
        await run(now=local(13, 30))  # missed the 13:00 one by too long: skipped, not sent late
        assert len(self.kinds(inbox, "water")) == 2
        await run(now=local(19, 2))
        assert len(self.kinds(inbox, "water")) == 3
        await run(now=local(21, 0))  # 21:00 is after 20:00
        assert len(self.kinds(inbox, "water")) == 3

    async def test_a_breathing_pause_once_a_day(self, client, admin, inbox, run):
        await device(client, admin)
        await notify(client, admin, mindful=True, mindful_time="15:00")
        await run(now=local(14, 59))
        assert self.kinds(inbox, "mindful") == []
        await run(now=local(15, 10))
        await run(now=local(15, 20))
        await run(now=local(16, 0))
        assert len(self.kinds(inbox, "mindful")) == 1
        await run(now=local(15, 0) + timedelta(days=1))
        assert len(self.kinds(inbox, "mindful")) == 2
        assert self.kinds(inbox, "mindful")[0]["body"] != ""

    async def test_quiet_hours_skip_them(self, client, admin, inbox, run):
        await client.patch("/api/family", json={"sleep": {"enabled": True, "off": "13:00", "on": "16:00"}}, headers=_h(admin))
        await device(client, admin)
        await notify(client, admin, mindful=True, mindful_time="15:00", water=True, water_every=60,
                     water_from="15:00", water_until="18:00")
        await run(now=local(15, 0))
        await run(now=local(16, 0))  # quiet hours over: the 15:00 pause is too late now, 16:00 water is on time
        assert self.kinds(inbox, "mindful") == []
        assert len(self.kinds(inbox, "water")) == 1

    async def test_bad_wellness_choices_are_refused(self, client, admin):
        current = (await client.get("/api/users/me/preferences", headers=_h(admin))).json()
        for bad in ({"water_every": 45}, {"water_from": "20:00", "water_until": "09:00"},
                    {"water_from": "09:00", "water_until": "09:00"}, {"mindful_time": "3pm"}):
            res = await client.put("/api/users/me/preferences", json={**current, "notifications": bad}, headers=_h(admin))
            assert res.status_code == 422, bad


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
