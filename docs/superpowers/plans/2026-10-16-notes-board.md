# Family Notes Board Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the Phase 12 family Notes board with private photos, stickers, sketching, PNG export, and a paired-wall card.

**Architecture:** Store one validated scene per family in a `note_boards` model and expose it through member and paired-wall routes. Render that scene in a reusable SVG component for both the editor and the read-only wall card; image tiles reference existing processed Media rows.

**Tech Stack:** FastAPI, SQLAlchemy/Alembic, Pydantic, React, React Query, SVG/browser canvas, Vitest, pytest.

**Spec:** `docs/superpowers/specs/2026-10-16-notes-board-design.md`

## Global Constraints

- Every board and media lookup filters by `family_id`; an install has exactly one family.
- Member/admin writes only; viewers and paired walls are read-only.
- Add an Alembic migration and model imports for the new table.
- Publish `notes_updated` only after commit with `queue_event`.
- Existing Media API is the only upload path; do not add public media URLs.
- Keep backend ≥93% and frontend configured coverage thresholds.

## Review Focus

- Another family’s media id is rejected on update (Task 2).
- Oversized/malformed scenes return 422 (Task 1).
- Viewers cannot write in either UI or API (Tasks 2 and 4).
- Paired walls read only their family board (Task 3).
- PNG export makes no server request and uses no public media URL (Task 5).

---

### Task 1: Persist and validate a family board

**Files:**
- Create: `backend/app/models/note.py`, `backend/app/schemas/notes.py`, `backend/alembic/versions/015_notes_board.py`
- Modify: `backend/app/models/__init__.py`, `backend/alembic/env.py`
- Test: `backend/tests/test_notes.py`

**Interfaces:** Produces `NoteBoard` (`id`, `family_id`, `title`, `scene_json`, `updated_by`, timestamps) and discriminated `NoteBoardUpdate`/`NoteBoardResponse` scene schemas for `note`, `sticker`, `image`, and `stroke` items.

- [ ] Write `test_note_scene_rejects_more_than_100_items` and `test_note_scene_rejects_oversized_stroke`, then run `cd backend && source .venv/bin/activate && pytest -q tests/test_notes.py`; expect route/schema failure.
- [ ] Implement bounded schemas, the `NoteBoard` model, migration 015 (unique/indexed `family_id`, `UTCDateTime` timestamps), and required imports.
- [ ] Rerun the focused tests; expect pass.
- [ ] Commit: `git commit -m "Add validated family notes board storage"`.

### Task 2: Add member board reads and writes

**Files:**
- Create: `backend/app/routers/notes.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_notes.py`

**Interfaces:** Consumes Task 1 schemas; produces authenticated `GET/PUT /api/notes/board`.

- [ ] Write failing tests for lazy empty-board creation, family isolation, a viewer receiving 403 from PUT, and a foreign/non-image/not-ready media id receiving 422.
- [ ] Run `cd backend && source .venv/bin/activate && pytest -q tests/test_notes.py`; expect missing router failure.
- [ ] Implement member GET and guarded PUT, validate ready photo Media rows in the caller’s family, replace the scene atomically, and call `queue_event(db, "notes_updated")`.
- [ ] Rerun focused tests; expect pass. Commit: `git commit -m "Add family-scoped notes board API"`.

### Task 3: Expose read-only Notes to paired walls

**Files:**
- Modify: `backend/app/routers/wall.py`, `backend/app/schemas/family.py`
- Test: `backend/tests/test_notes.py`, `backend/tests/test_wall_api.py`

**Interfaces:** Produces `GET /api/wall/notes/board` and `notes` as a `WallDashboardWidgetKey`.

- [ ] Write a failing test that a valid paired cookie reads its board while an absent/foreign device cannot; run `pytest -q tests/test_notes.py tests/test_wall_api.py`, expect 404.
- [ ] Implement GET using the wall device family lookup only and add the `notes` widget key/label.
- [ ] Rerun focused tests; expect pass. Commit: `git commit -m "Expose read-only notes on paired walls"`.

### Task 4: Build the reusable SVG scene and API hooks

**Files:**
- Create: `frontend/src/api/notes.ts`, `frontend/src/components/NoteBoardCanvas.tsx`, `frontend/src/components/NoteBoardCanvas.test.tsx`

**Interfaces:** Produces `NoteBoard`, `NoteItem`, `useNoteBoard`, `useSaveNoteBoard`, and a `NoteBoardCanvas` with an explicit read-only mode.

- [ ] Write a failing render test for one text note, emoji sticker, image tile, and freehand path; run `cd frontend && npm test -- NoteBoardCanvas.test.tsx`, expect absent component failure.
- [ ] Implement typed API hooks and SVG rendering. Use authenticated member media URLs in the page and wall-scoped media URLs in the wall card; display a harmless placeholder for unavailable image data.
- [ ] Rerun component tests; expect pass. Commit: `git commit -m "Add reusable notes board renderer"`.

### Task 5: Add member editor and local PNG export

**Files:**
- Create: `frontend/src/pages/NotesPage.tsx`, `frontend/src/pages/NotesPage.test.tsx`
- Modify: `frontend/src/App.tsx`, `frontend/src/components/NavShell.tsx`

**Interfaces:** Consumes Task 4. Produces lazy `/notes` route with add-note, sticker, photo, draw, save, and export actions.

- [ ] Write failing tests that a member adds/saves a note, a viewer sees no write controls, and export calls `URL.createObjectURL` plus a download anchor without an API request.
- [ ] Run `cd frontend && npm test -- NotesPage.test.tsx`; expect absent page failure.
- [ ] Implement normalized scene editing, photo placement through existing upload mutation, SVG-to-canvas PNG download, route, and navigation.
- [ ] Rerun `npm test -- NotesPage.test.tsx NoteBoardCanvas.test.tsx`; expect pass. Commit: `git commit -m "Add editable family notes board"`.

### Task 6: Render the Notes wall card and finish Phase 12

**Files:**
- Create: `frontend/src/wall/WallNotes.tsx`
- Modify: `frontend/src/api/wall.ts`, `frontend/src/wall/WallDashboard.tsx`, `frontend/src/wall/WallDashboard.test.tsx`, `docs/architecture.md`, `TODO.md`

**Interfaces:** Consumes Task 3 wall API and Task 4 renderer. Produces a selected read-only `notes` wall card.

- [ ] Write a failing wall-dashboard test that selects `{ key: 'notes', size: 'wide' }`, renders the board, and presents an empty-board message when appropriate.
- [ ] Run `cd frontend && npm test -- WallDashboard.test.tsx`; expect unsupported-widget failure.
- [ ] Implement the paired wall hook/card using only wall-scoped image URLs. Document storage, permission and export behavior; tick TODO line 314 only after verification passes.
- [ ] Run `cd backend && source .venv/bin/activate && pytest -v --cov` and `cd frontend && npm run test:coverage && npm run lint && npm run build`; expect both pass with thresholds met.
- [ ] Commit: `git commit -m "Add notes board wall panel"`.

## Self-review

- Spec coverage: Tasks 1–3 cover persistence, validation, member and wall access; Tasks 4–5 cover every board item/editor/export; Task 6 covers the wall panel and documentation.
- Type consistency: Task 1 defines `NoteBoard`/scene items, Tasks 2–3 expose them, Tasks 4–6 consume those exact types.
- Review-focus cases are each pinned to a test-owning task above.
- Proportion: the plan defines interfaces and tests without transcribing implementations.
