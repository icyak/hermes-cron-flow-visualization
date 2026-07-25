# Cron Flow Visualization — Hermes Cron Job Flow Visualizer

A [Hermes WebUI](https://hermes-agent.nousresearch.com) dashboard plugin that visualizes the data flow of your cron jobs. Click any job to see its trigger, agent/script, connected APIs, file operations, process steps, and delivery targets — all in one flow diagram.

![GitHub Actions CI](https://github.com/icyak/hermes-cron-flow-visualization/actions/workflows/ci.yml/badge.svg)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

## Features

- **Job list** — all cron jobs sorted by status, with schedule, provider, and delivery info
- **Flow diagram** — vertical pipeline showing cron → agent/script → process steps → delivery
- **Known Connections** — every API, file, and service the job touches, with auth type
- **Process Steps** — ordered breakdown of what the job does internally
- **Custom profiles** — define detailed connection maps for your own jobs

## Installation

### 1. Clone into plugins directory

```bash
cd ~/.hermes/plugins
git clone https://github.com/icyak/hermes-cron-flow-visualization.git
```

### 2. Add the backend API endpoint

The plugin runs in a sandboxed iframe and needs a CORS-enabled API endpoint to read cron job data. See [BACKEND-SETUP.md](./BACKEND-SETUP.md) for the exact code changes.

### 3. Enable the plugin

```bash
# Via CLI
python3 << 'EOF'
import json, os
path = os.path.expanduser('~/.hermes/webui/settings.json')
with open(path) as f:
    s = json.load(f)
s.setdefault('dashboard_plugins', {})['hermes-cron-flow-visualization'] = True
with open(path, 'w') as f:
    json.dump(s, f, indent=2)
EOF
```

Or via WebUI: **Settings → Plugins** → toggle **Cron Flow Visualization** on.

### 4. Add sidebar button (optional)

To add a sidebar button, edit `static/index.html` in the Hermes WebUI repo. Add after the Insights button:

```html
<!-- Rail (desktop) -->
<button class="rail-btn nav-tab has-tooltip" data-panel="plugin"
  data-label="Cron Flow Visualization"
  onclick="switchPluginPage(event,'/hermes-cron-flow-visualization','Cron Flow Visualization')"
  data-tooltip="Cron Flow Visualization - Cron job flow visualization" aria-label="Cron Flow Visualization">
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
    <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline>
  </svg>
</button>
```

### 5. Restart WebUI

```bash
cd /path/to/hermes-webui
bash ctl.sh restart
```

## Adding custom job profiles

By default, the plugin shows a generic flow for jobs without profiles. To add detailed connection maps for your own jobs, edit the `CUSTOM_PROFILES` object at the top of `dashboard/dist/index.js`:

```javascript
var CUSTOM_PROFILES = {
  'your-job-id-here': {
    connections: [
      { type: 'api', label: 'Weather API', detail: 'GET current conditions', direction: 'read', auth: 'API key' },
      { type: 'file', label: 'State file', detail: '~/.hermes/state.json', format: 'JSON' },
    ],
    process: [
      { label: '1. Fetch data', detail: 'Call external API with pagination' },
      { label: '2. Transform', detail: 'Normalize and validate' },
      { label: '3. Deliver', detail: 'Send to configured channel' },
    ]
  },
};
```

To find your job IDs, run `hermes cron list` or check your WebUI cron settings.

## Profile format reference

| Field | Type | Description |
|---|---|---|
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
├── BACKEND-SETUP.md            ← backend API endpoint instructions
├── example-profiles.json       ← example profiles you can adapt
├── dashboard/
│   ├── manifest.json           ← plugin manifest
│   └── dist/
│       └── index.js            ← plugin JavaScript (edit CUSTOM_PROFILES here)
```

## How it works

1. The plugin lists all your Hermes cron jobs by querying `/api/taskflow/jobs`
2. Click a job to see its metadata (schedule, status, provider, last run)
3. The flow diagram shows the sequential pipeline
4. If the job has a profile, detailed process steps and connections are shown
5. Jobs without profiles show a generic agent → skill → output flow

## License

MIT
