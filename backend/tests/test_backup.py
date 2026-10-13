"""The daily SQLite backup job: what it copies and what it prunes."""
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from app.jobs import backup


@pytest.fixture
def dirs(tmp_path, monkeypatch):
    db_dir, backups_dir = tmp_path / "db", tmp_path / "backups"
    db_dir.mkdir()
    monkeypatch.setattr(backup, "_DB_DIR", db_dir)
    monkeypatch.setattr(backup, "_BACKUPS_DIR", backups_dir)
    return db_dir, backups_dir


def _make_db(path, rows=("Field trip",), wal=True):
    con = sqlite3.connect(path)
    if wal:
        con.execute("PRAGMA journal_mode=WAL")
    con.execute("CREATE TABLE events (title TEXT)")
    con.executemany("INSERT INTO events VALUES (?)", [(r,) for r in rows])
    con.commit()
    return con  # left open, as the running API would hold it


def _today():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


async def test_backup_copies_the_live_database(dirs):
    db_dir, backups_dir = dirs
    con = _make_db(db_dir / "homehub.db", rows=("Field trip", "Dentist"))
    try:
        await backup.daily_backup()
    finally:
        con.close()
    copy = backups_dir / f"homehub_{_today()}.db"
    assert copy.exists()
    titles = sorted(r[0] for r in sqlite3.connect(copy).execute("SELECT title FROM events"))
    assert titles == ["Dentist", "Field trip"]


async def test_backup_includes_changes_still_in_the_wal(dirs):
    db_dir, backups_dir = dirs
    con = _make_db(db_dir / "homehub.db")
    con.execute("INSERT INTO events VALUES ('Not checkpointed yet')")
    con.commit()  # committed, but only in homehub.db-wal so far
    try:
        await backup.daily_backup()
    finally:
        con.close()
    copy = sqlite3.connect(backups_dir / f"homehub_{_today()}.db")
    assert copy.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 2


async def test_missing_database_is_skipped(dirs):
    _, backups_dir = dirs
    await backup.daily_backup()
    assert not backups_dir.exists() or not any(backups_dir.iterdir())


async def test_old_backups_are_pruned_and_others_kept(dirs, monkeypatch):
    db_dir, backups_dir = dirs
    monkeypatch.setattr(backup.settings, "backup_retention_days", 30)
    _make_db(db_dir / "homehub.db").close()
    backups_dir.mkdir()
    old = (datetime.now(timezone.utc) - timedelta(days=40)).strftime("%Y-%m-%d")
    recent = (datetime.now(timezone.utc) - timedelta(days=5)).strftime("%Y-%m-%d")
    for name in (f"homehub_{old}.db", f"homehub_{recent}.db", "manual_2020-01-01_0300.db", "homehub_notes.db"):
        (backups_dir / name).write_bytes(b"x")

    await backup.daily_backup()

    names = sorted(p.name for p in backups_dir.iterdir())
    assert f"homehub_{old}.db" not in names
    assert f"homehub_{recent}.db" in names
    assert "manual_2020-01-01_0300.db" in names  # manual backups are never pruned
    assert "homehub_notes.db" in names  # names that aren't dates are left alone
    assert f"homehub_{_today()}.db" in names


async def test_a_failed_backup_prunes_nothing(dirs, monkeypatch):
    db_dir, backups_dir = dirs
    monkeypatch.setattr(backup.settings, "backup_retention_days", 30)
    (db_dir / "homehub.db").write_bytes(b"this is not a sqlite database")
    backups_dir.mkdir()
    old = (datetime.now(timezone.utc) - timedelta(days=40)).strftime("%Y-%m-%d")
    (backups_dir / f"homehub_{old}.db").write_bytes(b"x")

    await backup.daily_backup()

    assert (backups_dir / f"homehub_{old}.db").exists()


def test_job_runs_at_backup_time(monkeypatch):
    added = {}

    class FakeScheduler:
        def add_job(self, fn, trigger, **kw):
            added.update(fn=fn, trigger=trigger, **kw)

    monkeypatch.setattr(backup.settings, "backup_time", "04:15")
    backup.register_backup_job(FakeScheduler())
    assert (added["trigger"], added["hour"], added["minute"], added["id"]) == ("cron", 4, 15, "daily_backup")

    monkeypatch.setattr(backup.settings, "backup_time", "garbage")
    backup.register_backup_job(FakeScheduler())
    assert (added["hour"], added["minute"]) == (3, 0)
