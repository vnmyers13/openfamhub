# Family Notes Board Design

## Goal

Provide one shared, family-scoped visual note board that family members can edit and paired wall displays can show without gaining write access.

## Decisions

- A family has one board, created lazily on its first read. This avoids a board-management domain while meeting the Phase 12 requirement.
- A board holds a bounded JSON scene (`items`): text notes, emoji stickers, media-image references, and freehand strokes. Each item has an id, x/y position, width/height where applicable, colour, and type-specific data. The API validates the complete scene rather than accepting arbitrary JSON.
- Images reference existing ready `Media` rows in the same family. The Notes UI uploads through the existing private Media API, then places the returned media id; it neither creates a public URL nor stores image bytes in a note row.
- Members and admins may update the board; viewers may read it. The board is deliberately shared. Paired wall displays have a GET-only endpoint and receive the board through the authenticated wall API.
- The editor uses SVG for notes, stickers, image tiles and freehand paths. Export serializes that SVG to a browser-generated PNG download; no canvas/image data is sent to the server.
- The wall gets a `notes` widget key. It shows the board read-only, never editor controls or a write-capable member cookie.

## Bounds and validation

- Board title: 1–80 trimmed characters; default “Family notes”.
- At most 100 items; text is at most 1,000 characters; a stroke has at most 500 points and the full serialized scene is at most 250 KB.
- Coordinates are normalized from 0 through 1000. Dimensions keep items visible and prevent pathological SVG markup.
- Image ids must name a ready image (not video) belonging to the caller’s family. An invalid or deleted media reference is rejected on update and omitted safely by the renderer if it becomes unavailable later.

## API

- `GET /api/notes/board`: authenticated family member; returns the family board, creating the empty default when absent.
- `PUT /api/notes/board`: member/admin; validates and replaces the scene atomically, sets `updated_by`, queues `notes_updated` after commit.
- `GET /api/wall/notes/board`: paired wall cookie only; returns the same read model, scoped to the paired device’s family.

## UI

- `/notes` is a lazy-loaded, member-visible route and navigation item.
- The editor offers Add note, Sticker, Photo, and Draw tools; board title editing; Save; and Export PNG. Viewers see the board and Export only.
- A shared `NoteBoardCanvas` renders both the editor and `WallNotes`; the wall receives a `notes` card selected through the existing wall-dashboard configuration.

## Verification

- Backend tests cover lazy creation, family isolation, viewer write refusal, item/media validation, and paired-wall-only reads.
- Frontend tests cover rendering each item type, editing/saving as a member, viewer read-only behavior, and PNG export invocation.
- Wall tests cover rendering a Notes card only when selected and its empty-board state.
