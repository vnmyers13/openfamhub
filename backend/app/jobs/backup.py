import logging
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from app.core.config import settings
from app.services import server_config as cfg

# Docker sets DATA_PATH=/data; outside Docker default to <repo>/data.
_DATA_ROOT = Path(os.environ.get("DATA_PATH", Path(__file__).resolve().parents[3] / "data"))
_DB_DIR = _DATA_ROOT / "db"
_BACKUPS_DIR = _DATA_ROOT / "backups"

logger = logging.getLogger(__name__)


async def daily_backup() -> None:
    db_path = _DB_DIR / "homehub.db"
    if not db_path.exists():
        logger.warning("Database file not found, skipping backup")
        return

    _BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    backup_path = _BACKUPS_DIR / f"homehub_{date_str}.db"

    try:
        import sqlite3
        src_conn = sqlite3.connect(str(db_path))
        dst_conn = sqlite3.connect(str(backup_path))
        src_conn.backup(dst_conn)
        dst_conn.close()
        src_conn.close()
        logger.info(f"Backup created: {backup_path}")
    except Exception as exc:
        logger.error(f"Backup failed: {exc}")
        return

    retention = cfg.get("backup_retention_days")
    cutoff = datetime.now(timezone.utc).timestamp() - retention * 86400
    for f in sorted(_BACKUPS_DIR.glob("homehub_*.db")):
        try:
            parts = f.stem.split("_")
            if len(parts) >= 2:
                file_dt = datetime.strptime(parts[1], "%Y-%m-%d").timestamp()
                if file_dt < cutoff:
                    f.unlink()
                    logger.info(f"Pruned old backup: {f}")
        except (ValueError, OSError):
            continue


def register_backup_job(scheduler, timezone_name: str | None = None):
    """Daily at the backup time (Admin › Settings or BACKUP_TIME) in the family's
    timezone; TIMEZONE only before a family exists."""
    try:
        hour, minute = cfg.get("backup_time").split(":")
    except (AttributeError, ValueError):
        hour, minute = "03", "00"
    # A scheduler that hasn't started keeps duplicates; replace explicitly.
    while scheduler.get_job("daily_backup") is not None:
        scheduler.remove_job("daily_backup")
    scheduler.add_job(
        daily_backup,
        "cron",
        hour=int(hour),
        minute=int(minute),
        timezone=timezone_name or settings.timezone,
        id="daily_backup",
        replace_existing=True,
    )


async def family_timezone(db) -> str | None:
    from app.models.family import Family

    family = (await db.execute(select(Family).where(Family.is_deleted == False))).scalars().first()  # noqa: E712
    return family.timezone if family else None


async def reschedule_backup(db) -> None:
    """After the backup time or the family timezone changes."""
    from app.jobs.scheduler import scheduler

    register_backup_job(scheduler, await family_timezone(db))
