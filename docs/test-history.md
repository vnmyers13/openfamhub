# Test History & QA Log

This document tracks the testing activities, bug reports, and verification steps performed during the development of OpenFamHub.

## Release v0.15
- **Date**: 2026-05-16
- **Scope**: Core API, Auth, and Database migrations.
- **Tests Performed**: 
    - Unit tests for authentication flows (setup, login, logout).
    - Integration tests for database connectivity.
- **Status**: PASS

## Release v0.16 (Current)
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
