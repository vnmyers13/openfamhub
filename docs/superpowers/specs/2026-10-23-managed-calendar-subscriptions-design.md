# Managed Calendar Subscriptions Design

## Intent

Let a family see its complete OpenFamHub calendar while away from home—in
Google Calendar today and Proton Calendar, Apple Calendar, Outlook, or another
standards-compatible client later—without exposing the home installation to
internet calendar clients.

OpenFamHub remains the calendar system of record. A managed relay publishes
read-only iCalendar (ICS) subscriptions for it; it is not an editable calendar
or an initial two-way-sync provider.

## Decisions

- The managed relay is an OpenFamHub-controlled **Cloudflare Worker with
  SQLite-backed Durable Object storage**. It stores and serves the two ICS
  snapshots; OpenFamHub pushes to it over HTTPS.
- Do not use Workers KV for feed state or revocation: its eventual consistency
  could briefly serve a rotated or revoked link. Durable Object storage is
  transactional and strongly consistent.
- OpenFamHub sends the managed relay an outbound snapshot of the family's
  calendar. The relay never needs to connect back to a home installation.
- The relay publishes two independent, unguessable, revocable HTTPS ICS URLs:
  **titles** and **full details**.
- Both feeds include every active, non-deleted event available to OpenFamHub,
  regardless of whether it was created in OpenFamHub or synchronized from an
  existing iCal source.
- The titles feed exposes event timing, all-day status, stable UID, and title;
  it omits description, location, URL, organizer, attendees, and source
  metadata.
- The full-details feed also exposes OpenFamHub's stored event details:
  description, location, URL, organizer, attendees, and title.
- Feed subscriptions are read-only. Creating, editing, deleting, resolving
  conflicts, and managing source feeds remain in OpenFamHub.
- The relay is a managed data processor. It may hold the published event data
  needed to generate the feeds, subject to its reviewed privacy policy; it does
  not receive OpenFamHub user credentials or a general-purpose API token.
- The first release is provider-neutral standard ICS. It must work with Google,
  Proton, Apple, Outlook, and other clients that accept an iCalendar URL.

## Goals

- Make the whole family calendar available outside the home network.
- Allow people to compare it with work and personal calendars in their chosen
  calendar client.
- Keep OpenFamHub event and source ownership rules intact.
- Give an unlocked admin clear controls to create, inspect, rotate, and revoke
  each feed independently.
- Avoid leaking the OpenFamHub host address, family member accounts, or
  browser-session cookies to external calendar clients.
- Publish valid, stable ICS so clients identify updates and deletions reliably.

## Non-goals

- Replacing Google, Proton, Apple, Outlook, or CalDAV with an OpenFamHub-hosted
  account/calendar service.
- Writing events back from a subscribed client.
- Google OAuth, Microsoft Graph, CalDAV, Proton-specific write integration, or
  conflict resolution. These remain candidates for the existing future
  two-way-calendar-sync phase.
- Sharing selected events, per-person feeds, availability-only feeds, or
  public browsing of a feed.
- Publishing chores, meals, birthdays, reminders, or wall-only data as events
  in this first release.

## Existing-System Fit

- `CalendarEvent` is family-scoped and belongs to either the single internal
  source or an iCal source. Existing calendar reads already exclude deleted
  events and disabled/deleted sources.
- iCal sync normalizes recurring source material into event rows, preserves
  details, uses UTC instants, and stores all-day events as date boundaries with
  an exclusive end. The relay export should reuse these stored normalized rows,
  not fetch source URLs again or reimplement recurrence parsing.
- The current sync storage window is 90 days in the past through 365 days in
  the future. The initial export contains every eligible event OpenFamHub holds
  in that window. Extending the retained/exported horizon is separate work if a
  longer view proves necessary.
- Existing calendar source administration is admin-only and password-gated;
  feed management follows that same protection level. Regular family members
  do not create, reveal, rotate, or revoke external links.

## User Experience

### Admin setup

1. An unlocked admin opens **Admin → Calendar subscriptions**.
2. The page explains that feeds are read-only and that subscribers may refresh
   on their own schedule (for example, Proton currently documents an
   approximately 16-hour refresh interval).
3. The admin creates either or both feeds. OpenFamHub shows each URL and
   offers copy and client-neutral subscription instructions.
4. The admin pastes the URL into Google Calendar, Proton Calendar, Apple
   Calendar, Outlook, or another calendar app's “subscribe from URL” flow.

### Ongoing management

- The page shows whether each feed is active, when it was last successfully
  delivered to the relay, and a non-secret identifier or URL suffix for
  recognizing the link. An unlocked admin can explicitly reveal and copy an
  existing URL again; each reveal is audit logged.
- **Rotate** creates a replacement URL and invalidates the old one immediately.
- **Revoke** invalidates the URL and requests deletion of its published feed at
  the relay. A revoked feed answers 404/410 at the relay; clients can retain a
  stale local copy until their own refresh policy removes it.
- A relay outage never prevents family members from using OpenFamHub's calendar;
  it only leaves the external copy stale and reports an actionable status to an
  admin.

## Relay Contract

The implementation should isolate the Cloudflare Worker API behind a small
server-side relay client. The relay must provide:

- authenticated HTTPS ingestion from OpenFamHub;
- two opaque subscription URLs per installation, each independently revoked;
- standard `text/calendar; charset=utf-8` responses over HTTPS;
- encryption in transit and at rest, an explicit retention/deletion policy,
  and no advertising, resale, or secondary use of calendar data;
- prompt propagation of replacement/revocation and delivery-status reporting;
- a documented incident, backup, and data-export/deletion process.

Before production rollout, the operator must review and accept Cloudflare's
Data Processing Addendum, privacy policy, current subprocessor/retention
terms, and the selected Worker/Durable Object data-location configuration.
The deployment documentation must link to those materials and explain that
calendar snapshots are processed by Cloudflare.

OpenFamHub sends a complete replacement document or event snapshot rather than
granting the relay access to its database. A signed, scoped relay credential is
stored only in server configuration, never returned by the API or stored in the
browser. The vendor adapter must use bounded timeouts and safe failure
reporting; it must not expose a user-controlled relay URL.

## Export Semantics

- Generate a stable calendar identity and stable `UID` for every exported
  event. Source events retain an identity derived from their source/event
  identity; internal events retain their OpenFamHub event identity.
- Timed events serialize as UTC instants. All-day events serialize as date-only
  `DTSTART;VALUE=DATE` and exclusive `DTEND;VALUE=DATE`, preserving the
  existing all-day contract.
- Include last-modified/sequence information when available so clients update
  an event rather than duplicate it.
- An event disappearing from the next snapshot must disappear from the
  published feed. The relay replaces the prior document atomically, so it never
  serves a partially updated calendar.
- Push a replacement after any successful calendar-event or source-sync change,
  only after that database transaction commits. Coalesce bursts into a single
  background delivery; retries must be idempotent and visible to admins.
- The relay never asks OpenFamHub to fetch a source URL, and OpenFamHub never
  sends the source URL itself to the relay.

## Security and Privacy

- Treat both URLs as bearer secrets. Do not log the full URL, place it in page
  source, send it in telemetry, or include it in notifications.
- Store the token in encrypted server-side storage so an unlocked admin can
  reveal it again; also store a non-secret identifier suitable for listings and
  audit records. Never return or retain it in browser storage. Every reveal,
  creation, rotation, and revocation is audit logged with actor and timestamp.
- Feed creation, reveal, rotation, and revocation require an authenticated,
  unlocked admin. Every action is audit logged with actor and timestamp.
- URLs use high-entropy random tokens, have no predictable family or feed IDs,
  and are rate-limited at the relay. Rotation/revocation must take effect
  immediately at the relay even if OpenFamHub is offline.
- Full-details feeds deliberately disclose every stored event detail to anyone
  who holds that link; the UI must state this plainly before creation and before
  copying it.
- The data-processing agreement/privacy-policy review is a release gate before
  configuring a production relay.

## Failure Handling

- If relay configuration is absent, subscription controls explain that an
  operator has not enabled the managed service; no partial local/public route
  is created.
- A failed push leaves the last good relay version intact, records a safe error
  and retry time, and retries in the background. It never rolls back the local
  calendar write or source sync.
- A relay authentication failure disables further automatic attempts until an
  admin updates the server configuration, preventing noisy retries.
- A malformed relay response, redirect, or non-HTTPS endpoint is rejected by
  the server-side adapter and surfaced as an operator configuration error.

## Acceptance Criteria

1. An unlocked admin can create independent titles and full-details feeds;
   members, viewers, anonymous requests, and PIN-only admins cannot.
2. Each active feed includes local and synchronized eligible calendar events,
   excludes deleted/disabled-source events, and represents timed and all-day
   events correctly.
3. The titles feed never contains any full-details-only fields; the full feed
   contains the details OpenFamHub stores.
4. Adding, editing, deleting, or synchronizing an event publishes an updated
   feed only after the local transaction succeeds.
5. Recurring source occurrences retain stable event identity across unchanged
   publications; removed events disappear without leaving duplicates.
6. A transient relay failure leaves local calendar operations successful,
   retries safely, and shows actionable delivery status to admins.
7. Rotating or revoking one feed immediately invalidates only that URL and does
   not affect the other feed or local calendar access.
8. Tests cover ICS serialization, family scoping, role/password-gate behavior,
   token secrecy, event/source changes, relay retries, and rotation/revocation.

## Implementation Calls Left to the Builder

- Implement the selected Cloudflare Worker/Durable Object relay contract only
  after the privacy-policy review confirms its current retention, deletion,
  encryption, location, and incident-response terms.
- Choose the minimal persisted model for feed state and delivery attempts;
  any schema change requires an Alembic migration.
- Use the existing post-commit event/queue pattern or an equivalent committed
  background-delivery mechanism so relay publication never precedes a database
  commit.
- Add the admin page using existing authenticated API and password-prompt
  patterns; it must not persist feed URLs in browser storage.
