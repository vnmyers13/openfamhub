"""Bring the database schema up to date with Alembic at startup.

Installs from before 0.30 were created with `Base.metadata.create_all` and have
no `alembic_version` table. Those are stamped at the revision that matches the
tables they already have, then upgraded normally.
"""
import logging
import sqlite3
from pathlib import Path

from alembic import command
from alembic.config import Config

from app.core.config import settings

logger = logging.getLogger(__name__)

BACKEND_DIR = Path(__file__).resolve().parents[2]

# (table that first appeared, revision that created it), newest first.
_LEGACY_MARKERS = [
    ("wall_devices", "a1f3c9d2e004"),
    ("calendar_events", "12c7ab6cf8c5"),
    ("sessions", "4c6b1ca5fd2c"),
    ("families", "5ca65f282ae7"),
]


def _sqlite_path(url: str) -> str | None:
    for prefix in ("sqlite+aiosqlite:///", "sqlite:///"):
        if url.startswith(prefix):
            path = url[len(prefix):]
            return None if path in ("", ":memory:") or path.startswith("file:") else path
    return None


def _alembic_config() -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    return cfg


def upgrade_database() -> None:
    path = _sqlite_path(settings.database_url)
    if path is None:
        logger.info("Skipping migrations for non-file database %s", settings.database_url)
        return
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    cfg = _alembic_config()

    with sqlite3.connect(path) as con:
        tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "alembic_version" not in tables:
        for table, revision in _LEGACY_MARKERS:
            if table in tables:
                logger.info("Stamping pre-0.30 database at %s", revision)
                command.stamp(cfg, revision)
                break

    command.upgrade(cfg, "head")
