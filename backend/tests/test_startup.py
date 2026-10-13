"""Production startup smoke test (review backlog #16).

The other tests build tables with ``Base.metadata.create_all``. This one boots
the real app lifespan against a fresh SQLite file, so Alembic migrations and
scheduler registration are exercised the way the container runs them. It runs
in a subprocess because settings and the engine are bound at import time.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]

PROBE = r'''
import json, sqlite3
from fastapi.testclient import TestClient
from alembic.script import ScriptDirectory

from app.core.database import Base
from app.core.migrate import _alembic_config
from app.main import app
from app.jobs.scheduler import scheduler

import os

with TestClient(app) as client:
    out = {
        "health": client.get("/api/health").status_code,
        "jobs": sorted(job.id for job in scheduler.get_jobs()),
    }

con = sqlite3.connect(os.environ["PROBE_DB"])
out["revision"] = con.execute("SELECT version_num FROM alembic_version").fetchone()[0]
out["head"] = ScriptDirectory.from_config(_alembic_config()).get_current_head()
missing = {}
for table in Base.metadata.sorted_tables:
    cols = {r[1] for r in con.execute(f"PRAGMA table_info({table.name})")}
    gone = sorted(c.name for c in table.columns if c.name not in cols)
    if not cols or gone:
        missing[table.name] = gone or ["<table>"]
out["missing"] = missing
out["triggers"] = sorted(r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='trigger'"))
print("PROBE" + json.dumps(out))
'''


def test_app_boots_migrates_and_registers_jobs(tmp_path):
    db = tmp_path / "db" / "homehub.db"
    env = {
        **os.environ,
        "SECRET_KEY": os.environ.get("SECRET_KEY", "startup-smoke-secret-0123456789abcdef"),
        "DATABASE_URL": f"sqlite+aiosqlite:///{db}",
        "DATA_PATH": str(tmp_path),
        "PROBE_DB": str(db),
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    # Boot twice: a container restart must find the schema current and
    # register the same jobs again.
    for boot in ("first", "restart"):
        proc = subprocess.run(
            [sys.executable, "-c", PROBE],
            cwd=BACKEND_DIR, env=env, capture_output=True, text=True, timeout=120,
        )
        lines = [l for l in proc.stdout.splitlines() if l.startswith("PROBE")]
        assert proc.returncode == 0 and lines, f"{boot} boot failed:\n{proc.stderr[-3000:]}"
        out = json.loads(lines[-1][len("PROBE"):])

        assert out["health"] == 200, boot
        assert out["jobs"] == ["calendar_sync_all_due", "chore_generator", "daily_backup"], boot
        assert out["revision"] == out["head"], boot
        # Every model column exists after migrations alone, so a model change
        # without its Alembic migration fails here.
        assert out["missing"] == {}, boot
        # Migration 006: one family per install.
        assert "families_single_row" in out["triggers"], boot
