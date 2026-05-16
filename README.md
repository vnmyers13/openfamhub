# OpenFamHub

Self-hosted family calendar and organizer. Designed to run on a central server (like a NAS or Linux box) with optional Raspberry Pi wall displays.

## Requirements
- **Docker + Docker Compose**: For running the core services (API, Web, Caddy).
- **Linux Server or NAS**: To host the application.
- **ICS Export URL**: An Apple ID or Google account to export calendar feeds via ICS.
- **Raspberry Pi (Optional)**: For the wall display feature.

## Quick Start

1. **Clone the repository**:
   ```bash
   git clone https://github.com/vnmyers13/openfamhub.git
   cd openfamhub
   ```

2. **Configure Environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your unique SECRET_KEY, FAMILY_NAME, and TIMEZONE
   ```

3. **Launch**:
   ```bash
   docker compose up -d
   ```

4. **Initial Setup**:
   Navigate to `https://openfamhub.local` in your browser and follow the setup wizard to create your admin account.

## Wall Display
To set up a dedicated wall display using a Raspberry Pi, follow our [Wall Screen Setup Guide](./docs/wall-screen-setup.md).

## Adding Calendar Feeds
OpenFamHub supports ICS feeds. To sync your personal calendars:
- **Google Calendar**: Go to Settings > Integrate Calendar > Export to ICS. Copy the URL.
- **iCloud**: Use a unique calendar and copy its public/private ICS link.
- **Sports Apps (e.g., TeamSnap)**: Use the provided ICS export links.

## Updates
To update your installation to the latest version:
```bash
git pull origin master
docker compose pull
docker compose up -d
```

## Backups
Backups are automatically performed daily to the `./data/backups` directory. 
- **Manual Restore**: To restore, copy your backup file and use `sqlite3` to import it into your database.

## Contributing
Please report issues or suggest features at [GitHub Issues](https://github.com/anomalyco/opencode/issues).
