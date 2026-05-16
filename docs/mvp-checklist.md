# MVP Hardware Test & Sign-off Checklist

This checklist is used to verify that the OpenFamHub deployment meets all requirements for a stable, production-ready environment.

## 1. Core Server Environment
- [ ] **Docker/Compose**: All services (API, Web, Caddy) start without errors.
- [ ] **Persistence**: Data is correctly stored in volumes and survives container restarts.
- [ ] **Network**: `openfamhub.local` (or configured domain) is accessible via HTTPS.
- [ ] **Security**: `.env` file is secured and not exposed in the web root.

## 2. Wall Display (Raspberry Pi)
- [ ] **Kiosk Mode**: Chromium launches automatically on boot in full-screen kiosk mode.
- [ ] **Display Settings**: Screen timeout/sleep is disabled.
- [ ] **Connectivity**: The Pi maintains a stable connection to the host server.
- [ ] **Certificate**: SSL/TLS certificate is trusted by the Pi's browser (no warnings).

## 3. Functional Verification
- [ ] **Setup Flow**: Admin user and Family record are created correctly.
- [ ] **Authentication**: Login/Logout works via cookies as expected.
- [ ] **Calendar Sync**: ICS feeds can be added and are processed without errors.
- [ ] **Timezone**: All calendar events reflect the configured family timezone.

## 4. Backup & Recovery
- [ ] **Automated Backups**: Verify that backup tasks are scheduled and running.
- [ ] **Manual Restore Test**: Successfully restored a database from a backup file to a fresh instance.

## Sign-off
**Tester Name:** __________________________  
**Date:** __________________________  
**Status:** [ ] PASS  [ ] FAIL
