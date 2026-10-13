"""Phase 3: iCal correctness (EXDATE, RECURRENCE-ID, floating times, DST,
storage window). Parser tests call parse_ics directly with a fixed `now` and
family timezone, so they don't depend on the date they run."""
from datetime import datetime, timezone

from app.integrations.ical_feed import WINDOW_FUTURE, WINDOW_PAST, parse_ics

NOW = datetime(2026, 10, 12, 12, 0, tzinfo=timezone.utc)
FAMILY_TZ = "America/Detroit"


def _ics(*events: list[str]) -> bytes:
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//OpenFamHub test//EN"]
    for ev in events:
        lines += ["BEGIN:VEVENT", *ev, "END:VEVENT"]
    lines += ["END:VCALENDAR", ""]
    return "\r\n".join(lines).encode()


def _parse(*events, tz=FAMILY_TZ, now=NOW):
    return parse_ics(_ics(*events), family_tz=tz, now=now)


def _starts(events):
    return sorted(e["start_dt"].isoformat() for e in events)


WEEKLY = [
    "UID:piano",
    "DTSTART:20261014T220000Z",
    "DTEND:20261014T230000Z",
    "RRULE:FREQ=WEEKLY;COUNT=4",
    "SUMMARY:Piano",
]


class TestExdateAndRecurrenceId:
    def test_each_occurrence_once(self):
        assert _starts(_parse(WEEKLY)) == [
            "2026-10-14T22:00:00+00:00", "2026-10-21T22:00:00+00:00",
            "2026-10-28T22:00:00+00:00", "2026-11-04T22:00:00+00:00",
        ]

    def test_exdate_removes_an_instance(self):
        events = _parse(WEEKLY + ["EXDATE:20261021T220000Z"])
        assert "2026-10-21T22:00:00+00:00" not in _starts(events)
        assert len(events) == 3

    def test_exdate_list_and_all_day_exdates(self):
        events = _parse([
            "UID:no-school",
            "DTSTART;VALUE=DATE:20261012",
            "DTEND;VALUE=DATE:20261013",
            "RRULE:FREQ=DAILY;COUNT=5",
            "EXDATE;VALUE=DATE:20261013,20261015",
            "SUMMARY:Spirit week",
        ])
        assert [e["start_dt"].date().isoformat() for e in sorted(events, key=lambda e: e["start_dt"])] == [
            "2026-10-12", "2026-10-14", "2026-10-16",
        ]
        assert all(e["all_day"] for e in events)

    def test_recurrence_id_moves_an_instance(self):
        moved = [
            "UID:piano",
            "RECURRENCE-ID:20261021T220000Z",
            "DTSTART:20261022T230000Z",
            "DTEND:20261023T000000Z",
            "SUMMARY:Piano (moved)",
        ]
        events = _parse(WEEKLY, moved)
        starts = _starts(events)
        assert "2026-10-21T22:00:00+00:00" not in starts
        assert "2026-10-22T23:00:00+00:00" in starts
        assert len(events) == 4
        override = next(e for e in events if e["title"] == "Piano (moved)")
        # Keeps the UID of the instance it replaces, so the stored row is updated in place.
        assert override["external_uid"] == "piano_2026-10-21T22:00:00+00:00"
        assert len({e["external_uid"] for e in events}) == 4

    def test_recurrence_id_before_its_master_in_the_feed(self):
        moved = ["UID:piano", "RECURRENCE-ID:20261021T220000Z", "DTSTART:20261022T230000Z",
                 "DTEND:20261023T000000Z", "SUMMARY:Piano (moved)"]
        assert len(_parse(moved, WEEKLY)) == 4

    def test_cancelled_instance_is_dropped(self):
        cancelled = ["UID:piano", "RECURRENCE-ID:20261028T220000Z", "DTSTART:20261028T220000Z",
                     "DTEND:20261028T230000Z", "STATUS:CANCELLED", "SUMMARY:Piano"]
        events = _parse(WEEKLY, cancelled)
        assert "2026-10-28T22:00:00+00:00" not in _starts(events)
        assert len(events) == 3

    def test_moving_the_first_occurrence_keeps_the_series_uid(self):
        moved = ["UID:piano", "RECURRENCE-ID:20261014T220000Z", "DTSTART:20261015T220000Z",
                 "DTEND:20261015T230000Z", "SUMMARY:Piano (moved)"]
        events = _parse(WEEKLY, moved)
        override = next(e for e in events if e["title"] == "Piano (moved)")
        assert override["external_uid"] == "piano"

    def test_cancelled_event_is_dropped(self):
        assert _parse(["UID:x", "DTSTART:20261020T150000Z", "DTEND:20261020T160000Z",
                       "STATUS:CANCELLED", "SUMMARY:Called off"]) == []

    def test_rdate_adds_an_instance(self):
        events = _parse(WEEKLY + ["RDATE:20261017T150000Z"])
        assert "2026-10-17T15:00:00+00:00" in _starts(events)
        assert len(events) == 5


class TestLocalTimes:
    def test_floating_times_use_the_family_timezone(self):
        # 18:00 with no TZID and no Z is 18:00 in Detroit (EDT, UTC-4).
        events = _parse(["UID:f", "DTSTART:20261020T180000", "DTEND:20261020T190000", "SUMMARY:Dinner"])
        assert _starts(events) == ["2026-10-20T22:00:00+00:00"]
        assert events[0]["end_dt"].isoformat() == "2026-10-20T23:00:00+00:00"

    def test_floating_recurrence_keeps_wall_time_across_dst(self):
        events = _parse(["UID:f", "DTSTART:20261029T180000", "DTEND:20261029T190000",
                         "RRULE:FREQ=WEEKLY;COUNT=2", "SUMMARY:Scouts"])
        # Clocks go back on Nov 1: 18:00 EDT = 22:00Z, 18:00 EST = 23:00Z.
        assert _starts(events) == ["2026-10-29T22:00:00+00:00", "2026-11-05T23:00:00+00:00"]

    def test_tzid_recurrence_keeps_wall_time_across_dst(self):
        events = _parse(["UID:t", "DTSTART;TZID=America/New_York:20261029T090000",
                         "DTEND;TZID=America/New_York:20261029T100000",
                         "RRULE:FREQ=WEEKLY;COUNT=2", "SUMMARY:Standup"])
        assert _starts(events) == ["2026-10-29T13:00:00+00:00", "2026-11-05T14:00:00+00:00"]

    def test_tzid_exdate_matches_its_instance(self):
        events = _parse(["UID:t", "DTSTART;TZID=America/New_York:20261029T090000",
                         "DTEND;TZID=America/New_York:20261029T100000",
                         "RRULE:FREQ=WEEKLY;COUNT=3",
                         "EXDATE;TZID=America/New_York:20261105T090000", "SUMMARY:Standup"])
        assert _starts(events) == ["2026-10-29T13:00:00+00:00", "2026-11-12T14:00:00+00:00"]

    def test_utc_and_all_day_are_unaffected_by_the_family_zone(self):
        events = _parse(["UID:u", "DTSTART:20261020T150000Z", "DTEND:20261020T160000Z", "SUMMARY:UTC"],
                        ["UID:d", "DTSTART;VALUE=DATE:20261020", "SUMMARY:Day"], tz="Asia/Tokyo")
        assert _starts(events) == ["2026-10-20T00:00:00+00:00", "2026-10-20T15:00:00+00:00"]


class TestStorageWindow:
    def test_window_bounds(self):
        assert WINDOW_PAST.days == 90 and WINDOW_FUTURE.days == 365

    def test_events_outside_the_window_are_dropped(self):
        events = _parse(
            ["UID:old", "DTSTART:20260101T150000Z", "DTEND:20260101T160000Z", "SUMMARY:Old"],
            ["UID:far", "DTSTART:20280101T150000Z", "DTEND:20280101T160000Z", "SUMMARY:Far"],
            ["UID:recent", "DTSTART:20260801T150000Z", "DTEND:20260801T160000Z", "SUMMARY:Recent"],
        )
        assert [e["title"] for e in events] == ["Recent"]

    def test_long_running_series_only_expands_inside_the_window(self):
        events = _parse(["UID:weekly", "DTSTART:20150105T230000Z", "DTEND:20150106T000000Z",
                         "RRULE:FREQ=WEEKLY", "SUMMARY:Since 2015"])
        starts = [e["start_dt"] for e in events]
        assert min(starts) >= NOW - WINDOW_PAST
        assert max(starts) <= NOW + WINDOW_FUTURE
        assert 60 <= len(events) <= 66  # ~455 days of weekly occurrences
        # The DTSTART occurrence is long gone, so no row carries the bare series UID.
        assert all(e["external_uid"].startswith("weekly_") for e in events)

    def test_an_event_overlapping_the_window_edge_is_kept(self):
        start = (NOW - WINDOW_PAST).strftime("%Y%m%dT%H%M%SZ")
        events = _parse(["UID:edge", f"DTSTART:{start}", "DURATION:PT2H", "SUMMARY:Edge"])
        assert len(events) == 1
