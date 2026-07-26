# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [2.0.0] - 2026-07-25

### Added

- `cron_flow_visualize` model tool + `/cronflow` slash command for use in any Hermes agent session (CLI/TUI/gateway), not just the dashboard.
- Native FastAPI backend (`dashboard/plugin_api.py`) serving the dashboard tab in-process — no more hand-patching an external Hermes WebUI's `api/routes.py` + `server.py` for CORS.
- `profiles.py`: shared custom-profile storage used by both the tool and the dashboard.
- CI workflow (ruff, pytest, JS syntax check, manifest validation, ESLint, Prettier).

### Fixed

- Pydantic V2 deprecation (`model_dump()` instead of `dict()`).
- CI dependency typo (`httpx2` -> `httpx`).

## [1.0.0] - 2026-07-25

### Added

- Initial dashboard-only Cron Flow Visualization plugin (external Hermes WebUI backend patch required).
