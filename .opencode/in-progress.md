# In-Progress Sessions

## v0.23 Release (2026-06-13)

### Status: COMPLETE

All 11 phases of the release checklist completed successfully.

- P1: 0 open GitHub issues
- P2: TODO.md and FUTURE_ENHANCEMENTS.md verified (no new entries)
- P3: Version bumped to 0.23 (config.py, Dockerfile, README.md)
- P4: CHANGELOG.md updated with v0.23 release notes
- P5: Backend tests — 59/59 passed (all pre-existing failures fixed)
- P6: Frontend build — OK
- P7: Docker images built for linux/amd64
- P8: Pushed to GitHub (main branch + tag v0.23)
- P9: Pushed to Docker Hub (vnmyers13/openfamhub-api:0.23, vnmyers13/openfamhub-web:0.23)
- P10: Production deployed — health check OK
- P11: Release summary written to docs/releases/v0.23.md

### Key Changes
- All 59 backend tests now pass (previously 15 failures from test isolation issues)
- Weather widget DNS resolution fix
- Weather service improved error handling
- New components: MenuWallPanel, CalendarWallView, ChoresWallPanel, AnnouncementsWallPanel
- WallDisplay refactored into thin composer with 25vh/75vh split layout

## v0.22 Release

- Released: 2026-06-12
- Git tag: v0.22
- Commits: 53e904d, 6a918ab
- Docker images: vnmyers13/openfamhub-api:0.22, vnmyers13/openfamhub-web:0.22
- Production: deployed and verified (all services healthy)
