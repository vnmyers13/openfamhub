# Security & Realtime Notes

Design notes for the server-side feed fetcher and live wall updates. Originally
written from the graphify analysis of the 0.30 codebase; both gaps it found are
now fixed (0.30.x).

## SSRF guard: every hop, pinned connection

`resolve_public_addresses` (`backend/app/core/url_safety.py`) is the SSRF guard.
It accepts only http(s), resolves the host **once**, and rejects the URL if
*any* resolved address is private, loopback, link-local, multicast, reserved,
unspecified, or carrier-grade NAT (`100.64.0.0/10`). IPv4-mapped IPv6
(`::ffff:127.0.0.1`) is unwrapped first. `assert_public_http_url` is the
yes/no wrapper.

`fetch_ics_bytes` (`backend/app/integrations/ical_feed.py`):

- **Every hop is checked.** It follows redirects itself (`follow_redirects=False`
  on the client) and validates each target before connecting.
- **The connection is pinned.** The request goes to the address the guard
  approved: the URL's host is replaced by that IP, the original name is sent in
  the `Host` header, and for https it is passed as the TLS SNI name
  (`sni_hostname`), so certificate checks still use the real hostname. httpx
  never resolves the name a second time, which closes the DNS-rebinding
  (time-of-check/time-of-use) window where a low-TTL record answers public to
  the guard and private to the connection.
- **The body is capped** at `MAX_ICS_BYTES` (10 MB) while streaming.

Tests: `backend/tests/test_ssrf.py` (`TestDnsRebinding` resolves public first and
loopback afterwards, and asserts the request still went to the approved IP with
one lookup; `TestResponseLimits` covers the cap).

Use the same pattern for any future server-side fetch of a user-supplied URL
(recipe import in Phase 7, Smart Import, webhooks).

## Live wall updates: published after commit, from every sync

Paired walls get `calendar_updated` over `/api/wall/ws` (`ConnectionManager` in
`backend/app/routers/ws.py`, fed by the in-process `EventBus` in
`backend/app/core/events.py`).

- **After commit only.** Code calls `queue_event(db, ...)`; the notice is held on
  the DB session and published by `publish_queued(db)` after a successful commit
  (`get_db` does this for API requests; a rollback discards it). Publishing
  before commit let a wall re-fetch and read the old data.
- **Background syncs notify too.** `sync_source` queues a notice; the scheduler
  job `sync_all_due` commits and then publishes, so scheduled syncs (and the
  sync run when an admin adds a feed) now update walls live, not just on the
  15-minute poll.

Tests: `backend/tests/test_realtime.py`.
