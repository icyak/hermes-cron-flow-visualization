# Backend API Setup

The Task Flow plugin runs in a sandboxed iframe (origin = `null`), so it cannot access the Hermes WebUI's internal API directly. You need to add a CORS-enabled endpoint that returns cron job data.

## Changes required

### 1. Add API endpoint in `api/routes.py`

In the `handle_get` method of your Hermes WebUI `api/routes.py`, add this block **before the final `return None`**:

```python
# ── Task Flow plugin data endpoint ──
if parsed.path == "/api/taskflow/jobs":
    try:
        from api.profiles import cron_profile_context
        with cron_profile_context():
            _ensure_agent_cron_import_path()
            active_profile = _get_active_profile_name() or "default"
            active_jobs, other_jobs = _cron_jobs_cross_profile(active_profile)
            jobs = active_jobs
    except Exception:
        # Fallback if cron_profile_context is unavailable
        _ensure_agent_cron_import_path()
        active_profile = _get_active_profile_name() or "default"
        active_jobs, other_jobs = _get_profile_jobs_cross_profile(active_profile)
        jobs = active_jobs

    body = json.dumps({"jobs": jobs}).encode("utf-8")
    handler.send_response(200)
    handler.send_header("Access-Control-Allow-Origin", "null")
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Vary", "Origin")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)
    return True  # ← MUST BE HERE — without it the server sends 404
```

Place this right before the existing `/api/crons/output` check or at the end of the `if/elif` chain, **before** the final `return None` line.

### 2. Handle CORS preflight in `server.py`

In the `do_OPTIONS` method of your Hermes WebUI `server.py`, add null-origin CORS headers for the taskflow endpoint:

```python
def do_OPTIONS(self) -> None:
    self._req_t0 = time.time()
    self.send_response(200)
    
    origin = self.headers.get("Origin", "").strip()
    path = self.path.split("?")[0] if self.path else ""
    
    # Allow null origin for plugin sandbox iframe endpoints
    if origin == "null" and path in ("/api/taskflow/jobs",):
        self.send_header("Access-Control-Allow-Origin", "null")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
    else:
        apply_cors_preflight_headers(self)
    
    self.end_headers()
```

### 3. Restart WebUI

```bash
cd /path/to/hermes-webui
bash ctl.sh restart
```

## Verification

```bash
# Test the endpoint
curl -s http://localhost:8787/api/taskflow/jobs | python3 -m json.tool | head -20
```

Expected output (your jobs will differ):

```json
{
    "jobs": [
        {
            "id": "...",
            "name": "Daily Report",
            "schedule": {"expr": "0 8 * * *", "display": "Daily at 08:00"},
            "no_agent": false,
            "skills": ["my-skill"],
            "provider": "anthropic",
            "model": "claude-sonnet-5",
            ...
        }
    ]
}
```

## How it works

1. The plugin's JavaScript calls `fetch('/api/taskflow/jobs', { credentials: 'omit' })`
2. The sandboxed iframe sends `Origin: null`
3. Your backend responds with `Access-Control-Allow-Origin: null` and the job data as JSON
4. The plugin renders the job list and flow diagrams

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| `Failed to load cron jobs: HTTP 404` | Missing `return True` in the API handler, or path typo |
| `Failed to load cron jobs: TypeError` | CORS not configured — browser blocks null-origin fetch |
| Empty job list (0 jobs) | `cron_profile_context()` missing — see cron_profile_context note below |
| `Failed to load cron jobs: HTTP 500` | Exception in the handler — check WebUI server logs |

### cron_profile_context

Hermes cron jobs are stored per-profile. The `cron_profile_context()` context manager ensures you access the correct profile's job data. Without it, the API may return 0 jobs.

If `from api.profiles import cron_profile_context` fails in your version, use the older `_get_profile_jobs_cross_profile` approach instead (the fallback in the code above handles this).
