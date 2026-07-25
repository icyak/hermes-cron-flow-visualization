"""Shared custom-profile storage for the Cron Flow Visualization plugin.

Both the model tool (``cron_flow_visualize``, used from a normal Hermes
agent session) and the dashboard backend (``dashboard/plugin_api.py``)
read the same file, so a profile added from either surface shows up in
the other.

Profiles are stored at ``~/.hermes/cron_flow_profiles.json`` (per-profile,
since it lives under the active ``HERMES_HOME``):

.. code-block:: json

    {
      "<job_id>": {
        "name": "Optional display name override",
        "connections": [
          {"type": "api", "label": "Weather API", "detail": "...",
           "direction": "read", "auth": "API key"}
        ],
        "process": [
          {"label": "1. Fetch data", "detail": "..."}
        ]
      }
    }
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

try:
    from hermes_constants import get_hermes_home
except ImportError:  # pragma: no cover - only importable inside a Hermes install
    def get_hermes_home() -> Path:  # type: ignore[misc]
        return Path.home() / ".hermes"


def _profiles_file() -> Path:
    return get_hermes_home() / "cron_flow_profiles.json"


def load_profiles() -> Dict[str, Any]:
    """Return the custom profiles dict, or {} if the file is missing/invalid."""
    path = _profiles_file()
    try:
        if not path.exists():
            return {}
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_profiles(profiles: Dict[str, Any]) -> None:
    path = _profiles_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(profiles, f, indent=2, ensure_ascii=False)
    tmp.replace(path)


def upsert_profile(job_id: str, profile: Dict[str, Any]) -> Dict[str, Any]:
    profiles = load_profiles()
    profiles[job_id] = profile
    save_profiles(profiles)
    return profile


def get_profile(job_id: str) -> Dict[str, Any]:
    return load_profiles().get(job_id, {})


def delete_profile(job_id: str) -> bool:
    profiles = load_profiles()
    if job_id in profiles:
        del profiles[job_id]
        save_profiles(profiles)
        return True
    return False
