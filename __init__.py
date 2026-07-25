"""Cron Flow Visualization — general Hermes plugin.

Adds a model tool (``cron_flow_visualize``) and a ``/cronflow`` slash
command so the flow-visualization data (trigger -> agent/script ->
connections -> process steps -> delivery) is available from a normal
Hermes agent session — CLI, TUI, or gateway — not just the Web
Dashboard tab shipped under ``dashboard/``.

Custom per-job "profiles" (detailed connections/process steps) are
shared with the dashboard backend via ``profiles.py`` — both surfaces
read/write ``~/.hermes/cron_flow_profiles.json``.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from . import profiles as flow_profiles

# ---------------------------------------------------------------------------
# Flow-building helpers (shared logic; mirrors the dashboard's JS renderer)
# ---------------------------------------------------------------------------

def _generic_process_steps(job: Dict[str, Any]) -> List[Dict[str, str]]:
    steps: List[Dict[str, str]] = []
    schedule = job.get("schedule") or {}
    trigger_desc = schedule.get("display") or schedule.get("expr") or "schedule"
    steps.append({"label": "1. Trigger", "detail": f"Cron fires on: {trigger_desc}"})

    if job.get("no_agent"):
        steps.append({
            "label": "2. Run script",
            "detail": f"Script executes directly (no LLM): {job.get('script') or '(no script set)'}",
        })
    else:
        skills = job.get("skills") or []
        skill_note = f" with skills: {', '.join(skills)}" if skills else ""
        steps.append({
            "label": "2. Agent run",
            "detail": f"LLM agent runs the job prompt{skill_note}",
        })
        if job.get("script"):
            steps.append({
                "label": "2a. Script context",
                "detail": f"Script stdout injected into prompt: {job['script']}",
            })
        if job.get("context_from"):
            steps.append({
                "label": "2b. Chained context",
                "detail": f"Injects last output of job(s): {job['context_from']}",
            })

    deliver = job.get("deliver") or "local"
    steps.append({"label": "3. Deliver", "detail": f"Delivery target: {deliver}"})
    return steps


def _generic_connections(job: Dict[str, Any]) -> List[Dict[str, Any]]:
    conns: List[Dict[str, Any]] = []
    if job.get("script"):
        conns.append({
            "type": "file", "label": "Script", "detail": job["script"],
            "format": "Python/Shell",
        })
    if job.get("workdir"):
        conns.append({
            "type": "file", "label": "Working directory", "detail": job["workdir"],
            "format": "Directory",
        })
    provider = job.get("provider")
    model = job.get("model")
    if provider or model:
        conns.append({
            "type": "api", "label": "Model provider",
            "detail": f"{provider or 'default'} / {model or 'default'}",
            "direction": "read", "auth": "Credential pool",
        })
    deliver = job.get("deliver")
    if deliver and deliver not in ("local",):
        conns.append({
            "type": "api", "label": "Delivery channel", "detail": deliver,
            "direction": "write", "auth": None,
        })
    return conns


def build_flow(job: Dict[str, Any]) -> Dict[str, Any]:
    """Build the flow-visualization payload for one cron job."""
    job_id = job.get("id")
    profile = flow_profiles.get_profile(job_id) if job_id else {}

    connections = profile.get("connections") or _generic_connections(job)
    process = profile.get("process") or _generic_process_steps(job)

    return {
        "id": job_id,
        "name": profile.get("name") or job.get("name") or job_id,
        "schedule": job.get("schedule"),
        "enabled": job.get("enabled", True),
        "no_agent": bool(job.get("no_agent")),
        "script": job.get("script"),
        "workdir": job.get("workdir"),
        "context_from": job.get("context_from"),
        "provider": job.get("provider"),
        "model": job.get("model"),
        "skills": job.get("skills") or [],
        "deliver": job.get("deliver"),
        "last_run_at": job.get("last_run_at"),
        "last_status": job.get("last_status"),
        "last_error": job.get("last_error"),
        "next_run_at": job.get("next_run_at"),
        "has_custom_profile": bool(profile),
        "connections": connections,
        "process": process,
    }


# ---------------------------------------------------------------------------
# Model tool
# ---------------------------------------------------------------------------

_TOOL_SCHEMA = {
    "name": "cron_flow_visualize",
    "description": (
        "Visualize the data flow of one or all Hermes cron jobs: trigger, "
        "agent/script, connected APIs/files, process steps, and delivery "
        "target. Use to explain what a cron job actually does end-to-end, "
        "or to audit all scheduled jobs at once. Optionally save/update a "
        "custom profile (detailed connections + process steps) for a job "
        "so future visualizations use accurate detail instead of a generic "
        "guess."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["list", "show", "set_profile", "delete_profile"],
                "description": (
                    "'list': flow summaries for all jobs. 'show': full flow "
                    "for one job_id. 'set_profile': create/update a custom "
                    "profile for job_id (needs profile_json). "
                    "'delete_profile': remove a custom profile for job_id."
                ),
            },
            "job_id": {
                "type": "string",
                "description": (
                    "Cron job ID (from `hermes cron list` / the cronjob "
                    "tool). Required for show/set_profile/delete_profile."
                ),
            },
            "profile_json": {
                "type": "string",
                "description": (
                    "JSON object string with optional 'name', 'connections' "
                    "(list of {type: api|file, label, detail, direction, "
                    "auth}), and 'process' (list of {label, detail}). "
                    "Required for set_profile."
                ),
            },
            "include_disabled": {
                "type": "boolean",
                "description": "Include paused/disabled jobs in 'list'. Default false.",
            },
        },
        "required": ["action"],
    },
}


def _handle_cron_flow_visualize(params: Dict[str, Any], **kwargs) -> str:
    del kwargs
    from cron import jobs as cron_jobs

    action = (params.get("action") or "list").strip()

    try:
        if action == "list":
            include_disabled = bool(params.get("include_disabled", False))
            all_jobs = cron_jobs.list_jobs(include_disabled=include_disabled)
            flows = [build_flow(j) for j in all_jobs]
            return json.dumps({"success": True, "count": len(flows), "jobs": flows})

        job_id = (params.get("job_id") or "").strip()
        if not job_id:
            return json.dumps({"success": False, "error": "job_id is required for this action"})

        if action == "show":
            job = cron_jobs.get_job(job_id)
            if not job:
                return json.dumps({"success": False, "error": f"No cron job found with id {job_id!r}"})
            return json.dumps({"success": True, "flow": build_flow(job)})

        if action == "set_profile":
            raw = params.get("profile_json")
            if not raw:
                return json.dumps({"success": False, "error": "profile_json is required for set_profile"})
            try:
                profile = json.loads(raw) if isinstance(raw, str) else raw
            except Exception as exc:
                return json.dumps({"success": False, "error": f"profile_json is not valid JSON: {exc}"})
            if not isinstance(profile, dict):
                return json.dumps({"success": False, "error": "profile_json must be a JSON object"})
            saved = flow_profiles.upsert_profile(job_id, profile)
            return json.dumps({"success": True, "job_id": job_id, "profile": saved})

        if action == "delete_profile":
            removed = flow_profiles.delete_profile(job_id)
            return json.dumps({"success": True, "removed": removed, "job_id": job_id})

        return json.dumps({"success": False, "error": f"Unknown action: {action!r}"})
    except Exception as exc:
        return json.dumps({
            "success": False,
            "error": f"cron_flow_visualize failed: {type(exc).__name__}: {exc}",
        })


# ---------------------------------------------------------------------------
# Slash command: /cronflow [job_id]
# ---------------------------------------------------------------------------

def _render_flow_text(flow: Dict[str, Any]) -> str:
    lines = [f"## {flow.get('name')}  (`{flow.get('id')}`)"]
    if flow.get("schedule"):
        sched = flow["schedule"]
        lines.append(f"**Schedule:** {sched.get('display') or sched.get('expr')}")
    lines.append(f"**Enabled:** {flow.get('enabled')}   **No-agent:** {flow.get('no_agent')}")
    if flow.get("skills"):
        lines.append(f"**Skills:** {', '.join(flow['skills'])}")
    if flow.get("deliver"):
        lines.append(f"**Deliver:** {flow['deliver']}")
    lines.append("")
    lines.append("### Process")
    for step in flow.get("process") or []:
        lines.append(f"- **{step.get('label')}** — {step.get('detail')}")
    conns = flow.get("connections") or []
    if conns:
        lines.append("")
        lines.append("### Connections")
        for c in conns:
            bits = [f"[{c.get('type')}]", c.get("label", "")]
            if c.get("direction"):
                bits.append(f"({c['direction']})")
            if c.get("detail"):
                bits.append(f"— {c['detail']}")
            if c.get("auth"):
                bits.append(f"(auth: {c['auth']})")
            lines.append("- " + " ".join(str(b) for b in bits if b))
    if flow.get("has_custom_profile"):
        lines.append("\n_Using a saved custom profile._")
    else:
        lines.append("\n_Generic flow (no custom profile saved for this job)._")
    return "\n".join(lines)


def _cmd_cronflow(raw_args: str):
    from cron import jobs as cron_jobs

    arg = (raw_args or "").strip()
    if not arg:
        all_jobs = cron_jobs.list_jobs(include_disabled=True)
        if not all_jobs:
            return "No cron jobs found."
        lines = ["## Cron jobs — flow overview", ""]
        for j in all_jobs:
            flow = build_flow(j)
            sched = (flow.get("schedule") or {}).get("display") or ""
            lines.append(
                f"- `{flow['id']}` **{flow['name']}** — {sched}"
                + (" (disabled)" if not flow.get("enabled") else "")
            )
        lines.append("\nUse `/cronflow <job_id>` for the full flow diagram of one job.")
        return "\n".join(lines)

    job = cron_jobs.get_job(arg) or cron_jobs.resolve_job_ref(arg)
    if not job:
        return f"No cron job found matching {arg!r}. Try `/cronflow` with no args to list all jobs."
    return _render_flow_text(build_flow(job))


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def register(ctx) -> None:
    ctx.register_tool(
        name="cron_flow_visualize",
        toolset="cronjob",
        schema=_TOOL_SCHEMA,
        handler=lambda args, **kw: _handle_cron_flow_visualize(args, **kw),
        emoji="🔀",
    )
    ctx.register_command(
        name="cronflow",
        handler=_cmd_cronflow,
        description="Visualize cron job data flow (trigger -> agent/script -> connections -> delivery).",
        args_hint="[job_id]",
    )
