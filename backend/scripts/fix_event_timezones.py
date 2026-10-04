"""One-off fix for events created before v0.18's timezone handling.

Before v0.18 the web UI sent manually created timed events as local wall-clock
time with a bogus "Z", and SQLite stored that wall-clock value. iCal events were
already stored in UTC, so only manual (external_uid IS NULL) events need fixing:

* timed events: reinterpret the stored value in the family timezone -> UTC
* all-day events: old inclusive "23:59:59" end -> exclusive next-day 00:00

Dry run by default. Re-running is safe: a marker is written to the family's
settings_json and the script exits if it is present.

    python scripts/fix_event_timezones.py /data/db/homehub.db            # preview
    python scripts/fix_event_timezones.py /data/db/homehub.db --apply    # write

Back up the database first (data/backups has nightly copies).
"""
import argparse
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

MARKER = "tz_fix_v018_applied"
FMT = "%Y-%m-%d %H:%M:%S.%f"


def parse(v: str) -> datetime:
    return datetime.strptime(v if "." in v else v + ".000000", FMT)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("db")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    con = sqlite3.connect(args.db)
    con.row_factory = sqlite3.Row
    families = con.execute("SELECT id, timezone, settings_json FROM families").fetchall()
    for fam in families:
        settings = json.loads(fam["settings_json"] or "{}")
        if settings.get(MARKER):
            print(f"family {fam['id'][:8]}: already fixed, skipping")
            continue
        tz = ZoneInfo(fam["timezone"] or "UTC")
        rows = con.execute(
            "SELECT id, title, start_dt, end_dt, all_day FROM calendar_events "
            "WHERE family_id = ? AND external_uid IS NULL",
            (fam["id"],),
        ).fetchall()
        changes = []
        for r in rows:
            start, end = parse(r["start_dt"]), parse(r["end_dt"])
            if r["all_day"]:
                new_start = start.replace(hour=0, minute=0, second=0, microsecond=0)
                new_end = end
                if (end.hour, end.minute, end.second) == (23, 59, 59):
                    new_end = end.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
            else:
                to_utc = lambda d: d.replace(tzinfo=tz).astimezone(timezone.utc).replace(tzinfo=None)
                new_start, new_end = to_utc(start), to_utc(end)
            if (new_start, new_end) != (start, end):
                changes.append((r["id"], r["title"], start, end, new_start, new_end))

        print(f"family {fam['id'][:8]} ({tz}): {len(changes)} of {len(rows)} manual events to update")
        for _id, title, s, e, ns, ne in changes:
            print(f"  {title[:40]:40}  {s} -> {ns}   {e} -> {ne}")

        if args.apply:
            for _id, _t, _s, _e, ns, ne in changes:
                con.execute(
                    "UPDATE calendar_events SET start_dt = ?, end_dt = ? WHERE id = ?",
                    (ns.strftime(FMT), ne.strftime(FMT), _id),
                )
            settings[MARKER] = True
            con.execute(
                "UPDATE families SET settings_json = ? WHERE id = ?",
                (json.dumps(settings), fam["id"]),
            )
    if args.apply:
        con.commit()
        print("applied")
    else:
        print("dry run; re-run with --apply to write")


if __name__ == "__main__":
    main()
