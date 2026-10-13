"""Phase 5: chore recurrence and instance generation (no HTTP)."""
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.chores import ChoreInstance, ChoreTemplate
from app.models.family import Family
from app.services.chores import due_dates, family_today, generate_instances, retire_template

D = date


def daily(n=1):
    return {"every": "day", "interval": n}


class TestDueDates:
    def test_one_off_is_its_start_date(self):
        assert due_dates(None, D(2026, 10, 14), D(2026, 10, 12), D(2026, 10, 18)) == [D(2026, 10, 14)]
        assert due_dates({"every": "none"}, D(2026, 10, 1), D(2026, 10, 12), D(2026, 10, 18)) == []

    def test_daily_across_the_dst_change_has_each_date_once(self):
        # US clocks go back on 1 Nov 2026; dates must neither repeat nor skip.
        assert due_dates(daily(), D(2026, 10, 1), D(2026, 10, 30), D(2026, 11, 3)) == [
            D(2026, 10, 30), D(2026, 10, 31), D(2026, 11, 1), D(2026, 11, 2), D(2026, 11, 3)]

    def test_every_n_days_is_anchored_to_the_start_date(self):
        # v0.29 restarted the interval from "today" on every run.
        rule = daily(3)
        first = due_dates(rule, D(2026, 10, 1), D(2026, 10, 12), D(2026, 10, 18))
        next_day = due_dates(rule, D(2026, 10, 1), D(2026, 10, 13), D(2026, 10, 19))
        assert first == [D(2026, 10, 13), D(2026, 10, 16)]
        assert next_day == [D(2026, 10, 13), D(2026, 10, 16), D(2026, 10, 19)]

    def test_weekly_on_chosen_days(self):
        rule = {"every": "week", "interval": 1, "weekdays": ["mo", "th"]}
        assert due_dates(rule, D(2026, 10, 1), D(2026, 10, 12), D(2026, 10, 25)) == [
            D(2026, 10, 12), D(2026, 10, 15), D(2026, 10, 19), D(2026, 10, 22)]

    def test_every_other_week_defaults_to_the_start_weekday(self):
        rule = {"every": "week", "interval": 2}
        # 2026-10-01 is a Thursday.
        assert due_dates(rule, D(2026, 10, 1), D(2026, 10, 1), D(2026, 10, 31)) == [
            D(2026, 10, 1), D(2026, 10, 15), D(2026, 10, 29)]

    def test_monthly_on_a_day_and_on_the_last_day(self):
        assert due_dates({"every": "month", "month_day": 15}, D(2026, 10, 1), D(2026, 10, 1), D(2027, 1, 31)) == [
            D(2026, 10, 15), D(2026, 11, 15), D(2026, 12, 15), D(2027, 1, 15)]
        assert due_dates({"every": "month", "month_day": -1}, D(2026, 10, 1), D(2026, 10, 1), D(2027, 2, 28)) == [
            D(2026, 10, 31), D(2026, 11, 30), D(2026, 12, 31), D(2027, 1, 31), D(2027, 2, 28)]

    def test_nothing_before_the_start_date(self):
        assert due_dates(daily(), D(2026, 10, 15), D(2026, 10, 12), D(2026, 10, 16)) == [D(2026, 10, 15), D(2026, 10, 16)]


class TestFamilyToday:
    def test_uses_the_family_timezone_not_utc(self):
        # 03:30 UTC on 1 Nov is still 31 Oct in Detroit (v0.29 used the UTC date).
        now = datetime(2026, 11, 1, 3, 30, tzinfo=timezone.utc)
        assert family_today("America/Detroit", now) == D(2026, 10, 31)
        assert family_today("Asia/Tokyo", now) == D(2026, 11, 1)
        assert family_today("Not/AZone", now) == D(2026, 11, 1)  # falls back to UTC


@pytest.fixture
async def family(setup_db):
    fam = Family(name="Test", timezone="America/Detroit")
    setup_db.add(fam)
    await setup_db.flush()
    return fam


async def _template(db, family, **kw):
    fields = dict(family_id=family.id, title="Feed the cat", points=5, assignment="assigned",
                  assigned_to="kid", repeat=daily(), start_date=D(2026, 10, 1))
    fields.update(kw)
    t = ChoreTemplate(**fields)
    db.add(t)
    await db.flush()
    return t


async def _instances(db, template_id=None):
    q = select(ChoreInstance)
    if template_id:
        q = q.where(ChoreInstance.template_id == template_id)
    return list((await db.execute(q.order_by(ChoreInstance.due_date))).scalars().all())


class TestGenerator:
    async def test_generates_a_week_ahead_and_copies_the_assignee(self, setup_db, family):
        t = await _template(setup_db, family)
        created = await generate_instances(setup_db, family.id, D(2026, 10, 12))
        rows = await _instances(setup_db, t.id)
        assert created == 7
        assert [r.due_date for r in rows] == [D(2026, 10, d) for d in range(12, 19)]
        assert all(r.assigned_to == "kid" and r.status == "pending" and r.family_id == family.id for r in rows)

    async def test_running_twice_creates_nothing_new(self, setup_db, family):
        await _template(setup_db, family)
        await generate_instances(setup_db, family.id, D(2026, 10, 12))
        assert await generate_instances(setup_db, family.id, D(2026, 10, 12)) == 0
        assert await generate_instances(setup_db, family.id, D(2026, 10, 13)) == 1  # just the new day
        assert len(await _instances(setup_db)) == 8

    async def test_the_database_refuses_a_duplicate_instance(self, setup_db, family):
        t = await _template(setup_db, family)
        setup_db.add(ChoreInstance(family_id=family.id, template_id=t.id, due_date=D(2026, 10, 12)))
        setup_db.add(ChoreInstance(family_id=family.id, template_id=t.id, due_date=D(2026, 10, 12)))
        with pytest.raises(IntegrityError):
            await setup_db.flush()
        await setup_db.rollback()

    async def test_claimable_chores_have_no_assignee(self, setup_db, family):
        t = await _template(setup_db, family, assignment="claimable", assigned_to=None)
        await generate_instances(setup_db, family.id, D(2026, 10, 12))
        assert all(r.assigned_to is None for r in await _instances(setup_db, t.id))

    async def test_past_unfinished_chores_are_marked_missed(self, setup_db, family):
        t = await _template(setup_db, family)
        await generate_instances(setup_db, family.id, D(2026, 10, 12))
        rows = await _instances(setup_db, t.id)
        rows[0].status = "completed"
        rows[1].status = "claimed"
        await setup_db.flush()
        await generate_instances(setup_db, family.id, D(2026, 10, 15))
        by_date = {r.due_date: r.status for r in await _instances(setup_db, t.id)}
        assert by_date[D(2026, 10, 12)] == "completed"
        assert by_date[D(2026, 10, 13)] == "missed"
        assert by_date[D(2026, 10, 14)] == "missed"
        assert by_date[D(2026, 10, 15)] == "pending"

    async def test_inactive_templates_and_other_families_are_skipped(self, setup_db, family):
        await _template(setup_db, family, is_active=False)
        other = Family.__table__  # noqa: F841 (one family per install; another family_id is enough)
        await _template(setup_db, family, family_id="someone-else")
        assert await generate_instances(setup_db, family.id, D(2026, 10, 12)) == 0

    async def test_retiring_a_template_drops_its_open_future_instances(self, setup_db, family):
        t = await _template(setup_db, family)
        await generate_instances(setup_db, family.id, D(2026, 10, 12))
        rows = await _instances(setup_db, t.id)
        rows[0].status = "completed"
        await setup_db.flush()
        await retire_template(setup_db, t, D(2026, 10, 12))
        left = await _instances(setup_db, t.id)
        assert [(r.due_date, r.status) for r in left] == [(D(2026, 10, 12), "completed")]
        assert t.is_active is False


class TestGeneratorJob:
    async def test_runs_for_each_family_in_its_own_timezone(self, setup_db, family, monkeypatch):
        from contextlib import asynccontextmanager

        from app.jobs import chore_generator

        @asynccontextmanager
        async def shared_session():
            yield setup_db

        monkeypatch.setattr(chore_generator, "session_factory", shared_session)
        monkeypatch.setattr(chore_generator, "family_today", lambda tz: D(2026, 10, 12) if tz == "America/Detroit" else None)
        t = await _template(setup_db, family)
        assert await chore_generator.run_chore_generator() == 7
        assert await chore_generator.run_chore_generator() == 0
        assert len(await _instances(setup_db, t.id)) == 7

    def test_registered_hourly_and_at_startup(self):
        from apscheduler.schedulers.asyncio import AsyncIOScheduler

        from app.jobs.chore_generator import register_chore_job

        scheduler = AsyncIOScheduler(timezone="UTC")
        register_chore_job(scheduler)
        job = scheduler.get_job("chore_generator")
        assert str(job.trigger).startswith("cron[") and "minute='5'" in str(job.trigger)
