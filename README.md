# Cron Flow Visualization — Hermes Cron Job Flow Visualizer

A Hermes Agent plugin that visualizes the data flow of your cron jobs — trigger, agent/script, connected APIs, file operations, process steps, and delivery targets — all in one flow diagram.

Ships **two ways to use it**:

1. A model tool (`cron_flow_visualize`) and a `/cronflow` slash command that work in any normal Hermes agent session (CLI, TUI, gateway) — no dashboard needed.
2. A Web Dashboard tab (click a job to see its flow diagram), backed by this plugin's own native FastAPI backend.

## Features

- **Job list** — all cron jobs sorted by status, with schedule, provider, and delivery info
- **Flow diagram** — vertical pipeline showing cron → agent/script → process steps → delivery
- **Known Connections** — every API, file, and service the job touches, with auth type
- **Process Steps** — ordered breakdown of what the job does internally
- **Custom profiles** — define detailed connection maps for your own jobs, shared between the tool/slash-command and the dashboard
- **Chat-native access** — ask the agent to visualize a job, or run `/cronflow <job_id>`, without opening a dashboard at all

## Installation

```bash
cd ~/.hermes/plugins
git clone https://github.com/icyak/hermes-cron-flow-visualization.git
hermes plugins enable hermes-cron-flow-visualization
```

That's it. Once enabled, you can:

- Use `/cronflow` (or `/cronflow <job_id>`) in any Hermes agent session
- Ask the agent to use the `cron_flow_visualize` tool directly
- Run `hermes dashboard` and open the **Cron Flow Visualization** tab — it auto-appears once the plugin is enabled (no manual sidebar-button edit, no restart-required backend patch)

## Adding custom job profiles

By default, the plugin shows a generic flow for jobs without profiles. To add a detailed connection map for one of your own jobs, use any of:

- The `cron_flow_visualize` tool with `action=set_profile` (from a normal agent session)
- `/cronflow` and ask the agent to set a profile for a job
- `PUT /api/plugins/hermes-cron-flow-visualization/jobs/<job_id>/profile` directly against the dashboard backend

All three read/write the same store at `~/.hermes/cron_flow_profiles.json`, so a profile set from one surface immediately shows up in the other. There's no `dashboard/dist/index.js` file to hand-edit anymore.

To find your job IDs, run `hermes cron list` or check your dashboard's cron settings. See `example-profiles.json` for the profile shape.

## Profile format reference

| Field | Type | Description |
|---|---|---|
| `name` | String (optional) | Display name override |
| `connections` | Array | External APIs, files, and services the job interacts with |
| `connections[].type` | `"api"` or `"file"` | Type of connection |
| `connections[].label` | String | Display name in UI |
| `connections[].detail` | String | Description of what it does |
| `connections[].direction` | `"read"` or `"write"` | Data direction |
| `connections[].auth` | String or null | Authentication method (e.g. `"OAuth2"`, `"API key"`) |
| `connections[].url` | String (optional) | API endpoint URL |
| `connections[].format` | String (optional) | File format (for `file` type) |
| `process` | Array | Ordered list of steps the job performs |
| `process[].label` | String | Step name (shown in flow diagram) |
| `process[].detail` | String | What this step does |

## Project structure

```
hermes-cron-flow-visualization/
├── README.md                   ← this file
├── LICENSE                     ← MIT
├── BACKEND-SETUP.md            ← deprecation notice (see README instead)
├── plugin.yaml                 ← plugin manifest (kind: standalone)
├── __init__.py                 ← cron_flow_visualize tool + /cronflow command, flow-building logic
├── profiles.py                 ← shared custom-profile storage (~/.hermes/cron_flow_profiles.json)
├── example-profiles.json       ← example profiles you can adapt
├── pyproject.toml              ← package metadata
├── .github/workflows/ci.yml    ← CI (lint + tests)
├── tests/                      ← pytest suite for profiles.py and __init__.py
├── dashboard/
│   ├── manifest.json           ← dashboard tab manifest
│   ├── plugin_api.py           ← native FastAPI backend, mounted at /api/plugins/hermes-cron-flow-visualization/
│   └── dist/
│       └── index.js            ← dashboard tab JavaScript
```

## How it works

1. The dashboard tab queries this plugin's own `/api/plugins/hermes-cron-flow-visualization/jobs` endpoint, mounted in-process by the Hermes Agent dashboard plugin system (no CORS setup, no external WebUI patch). Alternatively, use the `cron_flow_visualize` tool or `/cronflow` to get the same data straight in an agent session.
2. Click a job (or pass its id) to see its metadata (schedule, status, provider, last run)
3. The flow diagram/response shows the sequential pipeline
4. If the job has a saved custom profile, detailed process steps and connections are shown
5. Jobs without profiles show a generic trigger → agent/script → deliver flow, built from the job's own config

## License

MIT
