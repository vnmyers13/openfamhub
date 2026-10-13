# Test History & QA Log

This document tracks the testing activities, bug reports, and verification steps performed during the development of OpenFamHub.

## Release v0.15
- **Date**: 2026-05-16
- **Scope**: Core API, Auth, and Database migrations.
- **Tests Performed**: 
    - Unit tests for authentication flows (setup, login, logout).
    - Integration tests for database connectivity.
- **Status**: PASS

## Release v0.16
- **Date**: 2026-05-16
- **Scope**: Documentation, Kiosk scripts, and Deployment automation.
- **Tests Performed**: 
    - Syntax verification of `setup-wall-pi.sh`.
    - Syntax verification of `deploy.sh`.
    - README/Documentation readability check.
- **Status**: PASS

## Ongoing Testing
- [ ] Automated CI/CD pipeline integration.
- [ ] Load testing for concurrent user access.
- [ ] End-to-end (E2E) browser testing for the Wall Display.

---
*Last Updated: 2026-05-16*

## Release 0.17 — Test Run — 2026-05-16T12:11:37.296711
- pytest: 5 passed 0 failed
- Frontend build: OK
- Migration round-trip: OK

## 0.71 — review fixes — 2026-10-12
- Backend: `pytest backend/tests`: 81 passed (adds recurring-feed, calendar-scoping and app-startup tests).
- Frontend: `npm test` (Vitest, new): 35 passed in 8 files; `npm run lint` clean; `npm run build` OK (main bundle 351 KB).
- Release tooling: `scripts/tests/*-test.sh`: 4 harnesses passed; `scripts/check-version.sh` OK.
- Not yet verified on the `test` VM.


## 0.82 — Phase 3 + coverage — 2026-10-12
- Backend: `pytest --cov`: 166 passed, coverage 96% (CI floor 93%). New: parser (EXDATE/RECURRENCE-ID/RDATE, floating times, DST, storage window), sync job, adding feeds, backups, users, wall and calendar routes.
- Frontend: `npm run test:coverage`: 97 passed in 20 files, 93% statements / 82% branches; lint clean; build OK. New: app boot, sign-in, calendar page, admin pages, wall strip/layout, NavShell.
- Found and fixed by the new tests: PATCH /calendar/sources answered 500; an unmounted password prompt could hang later admin actions; setup defaulted the family timezone to UTC.
- Not yet verified on the `test` VM.

## 0.88 — Phase 3b — 2026-10-12
- Backend: `pytest --cov`: 207 passed, coverage 96%. New: media uploads (type/size limits, EXIF GPS stripped, video converted with metadata removed, range requests, family scoping, unpaired walls refused), family settings and the sleep schedule in the wall session.
- Frontend: `npm run test:coverage`: 128 passed in 26 files, 94% statements / 84% branches. New: sleep schedule across DST in the family zone, shuffle bag, slideshow, Photos page, Admin › Settings.
- Release tooling: 5 harnesses passed, including the new `backup-offhost-test.sh` (rsync and cp modes).
- Not yet verified on the `test` VM.

## 0.94 — Phase 5 — 2026-10-12
- Backend: `pytest --cov`: 278 passed, coverage 96%. New: recurrence across DST and anchored intervals, family-local "today", idempotent generator and the unique (template, date) constraint, claim/complete role gating, exactly-once points with undo reversals, admin by-person counts, stats and streaks, family-scoped to-dos, routine step order across edits, the wall routines endpoint.
- Frontend: `npm run test:coverage`: 174 passed in 31 files, 94% statements / 86% branches. New: repeat descriptions, routine timeline in the family zone, chore action rules, the Chores page tabs and forms, wall routine countdown.
- Not yet verified on the `test` VM.

## 1 / 1.01 — CI, release process, release names — 2026-10-13
- Backend: `pytest --cov`: 290 passed in 22 files, coverage 96%. New: `release_name` cases (99 → 0.99, 100 → 1, 101 → 1.01, 200 → 2) and a `VERSION` file past 99.
- Frontend: unchanged since 0.94 (174 tests in 31 files, 94% statements).
- Script harnesses (`scripts/tests/*-test.sh`, 8): pass. New: `trivy-test.sh` (scan tags, issue open/dedupe/limit/close against a fake Forgejo), `issues-test.sh` (triage, close-done, the pinned report issue), `release-name-test.sh`, and the pre-commit badge past 99 in `hook-test.sh`.
- 1.01: build 1's `publish` failed (`scripts/deploy.sh: Permission denied`; an edit dropped its executable bit). New `exec-bits-test.sh` checks every `#!` script under `scripts/` and `.githooks/` is committed 100755; 9 harnesses pass.
