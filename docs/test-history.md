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

