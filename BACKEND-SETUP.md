# Backend API Setup — deprecated

This file described patching an external Hermes WebUI repo's `api/routes.py` and `server.py` to add a CORS-enabled `/api/taskflow/jobs` endpoint, because the dashboard tab used to run in a sandboxed iframe (`Origin: null`) with no access to WebUI internals.

**None of that is needed anymore.** As of this plugin's native architecture, the dashboard tab is backed by `dashboard/plugin_api.py`, a FastAPI router mounted natively by the Hermes Agent dashboard plugin system at:

```
/api/plugins/hermes-cron-flow-visualization/jobs
```

Because it's mounted in-process by the plugin system itself, there's no iframe sandbox with a `null` origin to work around, and therefore no CORS headers, `do_OPTIONS` patch, or external WebUI file edits to make. Enabling the plugin (`hermes plugins enable hermes-cron-flow-visualization`) is sufficient — the dashboard tab and its backend come up together.

See [README.md](./README.md) for current installation and usage instructions, including the `cron_flow_visualize` tool and `/cronflow` slash command, which work without the dashboard at all.

This file is kept only so old links/bookmarks resolve to an explanation instead of a 404.
