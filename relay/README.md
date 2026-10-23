# Managed calendar relay

An outbound snapshot store, not a proxy to an OpenFamHub installation. One
SQLite-backed `FeedStore` Durable Object owns every mapping and document.

## Local checks

With a current Node.js runtime:

```sh
npm ci
npm test
npm run typecheck
```

Tests use local workerd/SQLite only. The fake relay hostname and management
credential in the test configuration do not address a live service.

## Protocol

All management requests require `Authorization: Bearer <RELAY_API_TOKEN>`.
The runtime secret has no default and is not committed in Wrangler variables.
Only HTTPS requests are accepted.

- `POST /v1/feeds`, JSON `{kind: "titles" | "full", ics: string}` → 201,
  `{relay_id, subscription_url}`.
- `PUT /v1/feeds/{relay_id}`, JSON `{ics: string}` → 204, or 404 if revoked.
- `DELETE /v1/feeds/{relay_id}` → 204, including an already-removed ID.
- `GET /c/{token}.ics` → active snapshot as `text/calendar; charset=utf-8`,
  otherwise 404. Both responses use `Cache-Control: no-store`.

Documents are limited to 1 MiB of UTF-8; JSON input is also bounded while
streaming. Caller-selected IDs, URLs and additional payload fields are rejected.
Relay IDs and public tokens are independent 256-bit random values. Only the
SHA-256 hash of the public token is stored. Replacement and deletion run in
SQLite transactions; deletion removes both the token mapping and the document.

OpenFamHub uses `CALENDAR_RELAY_URL` (the HTTPS origin, no path) and
`CALENDAR_RELAY_TOKEN`, or their encrypted Admin → Settings equivalents. Both
saved settings are write-only. Its client never follows redirects, never fetches
a returned subscription URL, ignores environment proxies, caps responses at
16 KiB, and uses connect/pool timeouts of 5 s and read/write timeouts of 15 s.

## Before any production use

This project has not been deployed. Provider privacy/DPA, location, retention,
backup/restore, incident response, edge rate limiting, and access-log policy must
be reviewed before rollout. Wrangler observability is disabled; do not enable
request logging, tracing or analytics that capture public bearer URLs or ICS
content. Restoring a database backup must not resurrect revoked links. Calendar
clients may retain their own copies after revocation even though the relay
immediately returns 404.
