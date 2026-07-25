"""Tests for dashboard/plugin_api.py — the FastAPI backend the dashboard
tab actually talks to at runtime (GET /jobs, GET /jobs/{id},
PUT /jobs/{id}/profile, DELETE /jobs/{id}/profile).
"""

from __future__ import annotations

import importlib.util
import sys

import pytest
from conftest import (
    REPO_ROOT,
    install_fake_cron_jobs_module,
    uninstall_fake_cron_jobs_module,
)
from fastapi import FastAPI
from fastapi.testclient import TestClient

_PLUGIN_API_CACHE_KEYS = (
    "_hermes_cron_flow_viz_profiles",
    "_hermes_cron_flow_viz_pkg",
    "_hermes_cron_flow_viz_pkg.profiles",
    "_hermes_cron_flow_viz_pkg.__init__",
)


def _load_plugin_api_module():
    """Import a fresh copy of dashboard/plugin_api.py, evicting the sibling
    modules it caches in sys.modules under its own private keys (see
    _load_sibling_module in plugin_api.py)."""
    for key in _PLUGIN_API_CACHE_KEYS:
        sys.modules.pop(key, None)
    spec = importlib.util.spec_from_file_location(
        "plugin_api", REPO_ROOT / "dashboard" / "plugin_api.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["plugin_api"] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


@pytest.fixture
def plugin_api_module(monkeypatch, tmp_path):
    """Fresh plugin_api.py with its internally-loaded profiles.py copy
    pointed at tmp_path, mirroring the profiles_module fixture above."""
    module = _load_plugin_api_module()
    profiles_mod = module._profiles_module()
    monkeypatch.setattr(profiles_mod, "get_hermes_home", lambda: tmp_path)
    yield module
    for key in _PLUGIN_API_CACHE_KEYS:
        sys.modules.pop(key, None)
    sys.modules.pop("plugin_api", None)


@pytest.fixture
def client(plugin_api_module):
    app = FastAPI()
    app.include_router(plugin_api_module.router)
    return TestClient(app)


@pytest.fixture
def jobs():
    return {
        "job-1": {
            "id": "job-1",
            "name": "Backup job",
            "enabled": True,
            "schedule": {"display": "every day at 8am", "expr": "0 8 * * *"},
            "no_agent": True,
            "script": "/opt/scripts/backup.sh",
            "deliver": "local",
        },
        "job-2": {
            "id": "job-2",
            "name": "Disabled digest job",
            "enabled": False,
            "schedule": {"expr": "0 9 * * *"},
            "skills": ["deep-research"],
            "deliver": "telegram",
        },
    }


@pytest.fixture(autouse=True)
def _fake_cron(jobs):
    install_fake_cron_jobs_module(jobs)
    yield
    uninstall_fake_cron_jobs_module()


def test_get_jobs_returns_flow_for_each_job(client, plugin_api_module, jobs):
    resp = client.get("/jobs")

    assert resp.status_code == 200
    payload = resp.json()
    flow_module = plugin_api_module._flow_module()
    expected = flow_module.build_flow(jobs["job-1"])
    actual = next(j for j in payload["jobs"] if j["id"] == "job-1")
    assert actual == expected


def test_get_jobs_default_includes_disabled_jobs(client):
    # plugin_api.py's route signature defaults include_disabled to True,
    # unlike __init__.py's cron_flow_visualize tool (action="list"), which
    # defaults include_disabled to False. This test documents the dashboard
    # route's current (more permissive) default -- it is intentionally not
    # "fixed" to match the tool, since the dashboard tab is expected to show
    # paused jobs too.
    resp = client.get("/jobs")

    assert resp.status_code == 200
    ids = {j["id"] for j in resp.json()["jobs"]}
    assert ids == {"job-1", "job-2"}


def test_get_jobs_include_disabled_false_filters_disabled(client):
    resp = client.get("/jobs", params={"include_disabled": False})

    assert resp.status_code == 200
    ids = {j["id"] for j in resp.json()["jobs"]}
    assert ids == {"job-1"}


def test_get_job_flow_existing_job(client):
    resp = client.get("/jobs/job-2")

    assert resp.status_code == 200
    flow = resp.json()["flow"]
    assert flow["id"] == "job-2"
    assert flow["name"] == "Disabled digest job"
    assert flow["enabled"] is False
    assert flow["skills"] == ["deep-research"]


def test_get_job_flow_missing_job_returns_404(client):
    resp = client.get("/jobs/does-not-exist")

    assert resp.status_code == 404
    assert "does-not-exist" in resp.json()["detail"]


def test_put_profile_sets_custom_profile(client, profiles_module):
    body = {
        "name": "Custom Backup Name",
        "connections": [{"type": "file", "label": "Backup target", "detail": "/mnt/backups"}],
        "process": [{"label": "1. Custom step", "detail": "Runs a custom backup script"}],
    }

    resp = client.put("/jobs/job-1/profile", json=body)

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["ok"] is True
    assert payload["job_id"] == "job-1"
    assert payload["profile"] == body

    # Verify via profiles.py's own get_profile (same tmp_path-backed file).
    assert profiles_module.get_profile("job-1") == body

    flow_resp = client.get("/jobs/job-1")
    flow = flow_resp.json()["flow"]
    assert flow["has_custom_profile"] is True
    assert flow["name"] == "Custom Backup Name"
    assert flow["connections"] == body["connections"]
    assert flow["process"] == body["process"]


def test_put_profile_omits_unset_fields(client, profiles_module):
    resp = client.put("/jobs/job-1/profile", json={"name": "Just a name"})

    assert resp.status_code == 200
    assert resp.json()["profile"] == {"name": "Just a name"}
    assert profiles_module.get_profile("job-1") == {"name": "Just a name"}


def test_delete_profile_removes_existing_profile(client, profiles_module):
    profiles_module.upsert_profile("job-1", {"name": "Temp"})

    resp = client.delete("/jobs/job-1/profile")

    assert resp.status_code == 200
    payload = resp.json()
    assert payload == {"ok": True, "removed": True, "job_id": "job-1"}
    assert profiles_module.get_profile("job-1") == {}


def test_delete_profile_missing_profile_returns_removed_false(client):
    resp = client.delete("/jobs/job-1/profile")

    assert resp.status_code == 200
    assert resp.json() == {"ok": True, "removed": False, "job_id": "job-1"}
