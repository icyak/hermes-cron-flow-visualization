"""Cron Flow Visualization — dashboard backend routes.

Mounted at /api/plugins/hermes-cron-flow-visualization/ by the dashboard
plugin system. Reads jobs directly from ``cron.jobs`` (in-process, no
extra CORS endpoint needed — this replaces the original BACKEND-SETUP.md
approach of patching a Hermes WebUI's ``api/routes.py`` + ``server.py``,
which doesn't apply to Hermes Agent's own native dashboard plugin system).

Custom per-job profiles are shared with the ``cron_flow_visualize`` model
tool (see ``../__init__.py``) via ``../profiles.py``, so a profile set from
a normal agent session appears here too, and vice versa.

Note on imports: the dashboard plugin loader imports this file directly
via ``importlib.util.spec_from_file_location`` (it is not imported as
part of the ``hermes-cron-flow-visualization`` package, since the plugin
directory name contains hyphens and isn't a valid Python package name).
That means relative imports (``from . import profiles``) do not work
here — both sibling modules are loaded by path instead.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

_PLUGIN_DIR = Path(__file__).resolve().parent.parent


def _load_sibling_module(mod_name: str, filename: str):
    """Load a module that lives next to this plugin's dashboard/ dir.

    Cached in ``sys.modules`` under a private key so repeated calls (and
    calls from different route handlers) reuse the same module instance.
    """
    cache_key = f"_hermes_cron_flow_viz_{mod_name}"
    if cache_key in sys.modules:
        return sys.modules[cache_key]
    spec = importlib.util.spec_from_file_location(cache_key, _PLUGIN_DIR / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[cache_key] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def _profiles_module():
    return _load_sibling_module("profiles", "profiles.py")


def _flow_module():
    # __init__.py itself does `from . import profiles`, which only works
    # when imported as a real package. Pre-seed sys.modules with a fake
    # parent package pointing profiles at our already-loaded module so
    # that relative import resolves instead of raising ImportError.
    import types

    pkg_name = "_hermes_cron_flow_viz_pkg"
    if pkg_name not in sys.modules:
        pkg = types.ModuleType(pkg_name)
        pkg.__path__ = [str(_PLUGIN_DIR)]  # mark as a package
        sys.modules[pkg_name] = pkg
        sys.modules[f"{pkg_name}.profiles"] = _profiles_module()

    cache_key = f"{pkg_name}.__init__"
    if cache_key in sys.modules:
        return sys.modules[cache_key]

    spec = importlib.util.spec_from_file_location(
        cache_key, _PLUGIN_DIR / "__init__.py",
        submodule_search_locations=[str(_PLUGIN_DIR)],
    )
    module = importlib.util.module_from_spec(spec)
    module.__package__ = pkg_name
    sys.modules[cache_key] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


@router.get("/jobs")
def get_jobs(include_disabled: bool = True):
    """Return flow-visualization payloads for all cron jobs."""
    from cron import jobs as cron_jobs

    flow = _flow_module()
    all_jobs = cron_jobs.list_jobs(include_disabled=include_disabled)
    return {"jobs": [flow.build_flow(j) for j in all_jobs]}


@router.get("/jobs/{job_id}")
def get_job_flow(job_id: str):
    from cron import jobs as cron_jobs

    job = cron_jobs.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"No cron job found with id {job_id!r}")
    flow = _flow_module()
    return {"flow": flow.build_flow(job)}


class ProfileBody(BaseModel):
    name: Optional[str] = None
    connections: Optional[list] = None
    process: Optional[list] = None


@router.put("/jobs/{job_id}/profile")
def put_profile(job_id: str, body: ProfileBody):
    flow_profiles = _profiles_module()
    profile: Dict[str, Any] = {k: v for k, v in body.model_dump().items() if v is not None}
    saved = flow_profiles.upsert_profile(job_id, profile)
    return {"ok": True, "job_id": job_id, "profile": saved}


@router.delete("/jobs/{job_id}/profile")
def delete_profile(job_id: str):
    flow_profiles = _profiles_module()
    removed = flow_profiles.delete_profile(job_id)
    return {"ok": True, "removed": removed, "job_id": job_id}
