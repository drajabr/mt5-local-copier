# MT5 Local Copier MVP

A first MVP for a Dockerized MT5 trade copier service on Linux with Wine.

## Included in this MVP

- Lightweight Linux container using Debian slim + Wine + Xvfb
- First-run MT5 installer script (or install recovery if binary is missing)
- JSON config persisted in a Docker volume
- Logs persisted in a separate Docker volume
- Dynamic channels/sources/destinations config model
- Source and destination settings model with FX-style risk controls
- Two-stage symbol mapping foundation:
  - Stage 1 auto mapping on destination add
  - Stage 2 user override via saved config fields
- Simple web UI:
  - Dashboard page (view-only stats)
  - Settings page (token-gated API access)
- Save + preview + confirm apply config flow
- GitHub Actions workflow to build/push Docker image to GHCR

## Quick start

1. Create `.env` from example and set your token:

```bash
# Windows PowerShell
Copy-Item .env.example .env

# Linux/macOS
cp .env.example .env
```

2. Start service:

```bash
docker compose up -d
```

3. Open:

- Dashboard: http://localhost:8000/
- Settings: http://localhost:8000/settings

4. Open Settings and sign in with HTTP Basic auth:

- Username: `admin`
- Password: your `ADMIN_TOKEN` (or generated first-run token)

## Environment variables

- `ADMIN_TOKEN` (required in `docker-compose.yml`): settings token used by API/UI
- `APP_PORT` (optional, default `8000`): maps host and container port together for the web UI/API
- `CONFIG_PATH` (default `/data/config/config.json`)
- `LOG_PATH` (default `/data/logs/copier.log`)
- `MT5_ROOT` (default `/data/mt5`)
- `INSTALLER_SCRIPT` (default `/app/scripts/install_mt5.sh`)
- `MT5_INSTALLER_URL` (optional): override installer URL

## Notes

- Settings/API authentication uses HTTP Basic auth. Use username `admin` and token as password.
- MT5 installation switches may differ by installer build. The script includes an MVP fallback marker so API/UI can still run even if silent install is not detected automatically.
- Real trade execution integration and MT5 bridge logic are not fully implemented in this first MVP; worker lifecycle and config/apply scaffolding are implemented.

## CI

GitHub Actions workflow:
- File: `.github/workflows/docker-image.yml`
- Builds on push/PR/workflow_dispatch
- Pushes to `ghcr.io/<owner>/<repo>` on non-PR events
