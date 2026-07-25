"""Test bootstrap: make profiles.py / __init__.py importable without a Hermes install.

``__init__.py`` uses a relative import (``from . import profiles``), which only
resolves when the module is loaded as part of a real package. We mirror the
technique ``dashboard/plugin_api.py`` already uses to load these files outside
a Hermes plugin install: register a synthetic parent package in
``sys.modules`` pointing at the already-imported ``profiles`` module, then
load ``__init__.py`` via ``importlib`` with that package as its parent.

This file lives in ``tests/`` (not the repo root) on purpose: the repo root
itself is ``__init__.py`` (the plugin file), so a conftest.py placed there
would make pytest treat the repo root as an ancestor package when resolving
this file's own import path, forcing it to import that ``__init__.py`` as a
plain top-level module — which crashes because its relative import has no
package context. Keeping conftest.py in ``tests/`` (which has no
``__init__.py``) avoids that ancestor walk entirely; we only ever load the
repo root's modules explicitly, via importlib, below.
"""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _load_module_from_path(mod_name: str, file_path: Path):
    spec = importlib.util.spec_from_file_location(mod_name, file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def load_profiles_module():
    """Import a fresh copy of profiles.py, evicting any cached instance."""
    sys.modules.pop("profiles", None)
    return _load_module_from_path("profiles", REPO_ROOT / "profiles.py")


def load_flow_module(profiles_module):
    """Import __init__.py under a synthetic package so its relative import
    (``from . import profiles``) resolves to the given ``profiles_module``."""
    pkg_name = "_test_cron_flow_pkg"
    pkg = types.ModuleType(pkg_name)
    pkg.__path__ = [str(REPO_ROOT)]
    sys.modules[pkg_name] = pkg
    sys.modules[f"{pkg_name}.profiles"] = profiles_module

    cache_key = f"{pkg_name}.__init__"
    spec = importlib.util.spec_from_file_location(
        cache_key,
        REPO_ROOT / "__init__.py",
        submodule_search_locations=[str(REPO_ROOT)],
    )
    module = importlib.util.module_from_spec(spec)
    module.__package__ = pkg_name
    sys.modules[cache_key] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def install_fake_cron_jobs_module(jobs_by_id):
    """Install a lightweight fake ``cron.jobs`` module in sys.modules.

    ``__init__.py`` does ``from cron import jobs as cron_jobs`` lazily inside
    its handler functions, so tests never need a real ``cron`` package.
    """
    cron_pkg = types.ModuleType("cron")
    cron_pkg.__path__ = []
    jobs_mod = types.ModuleType("cron.jobs")

    def list_jobs(include_disabled=False):
        jobs = list(jobs_by_id.values())
        if not include_disabled:
            jobs = [j for j in jobs if j.get("enabled", True)]
        return jobs

    def get_job(job_id):
        return jobs_by_id.get(job_id)

    def resolve_job_ref(ref):
        return jobs_by_id.get(ref)

    jobs_mod.list_jobs = list_jobs
    jobs_mod.get_job = get_job
    jobs_mod.resolve_job_ref = resolve_job_ref

    cron_pkg.jobs = jobs_mod
    sys.modules["cron"] = cron_pkg
    sys.modules["cron.jobs"] = jobs_mod
    return jobs_mod


def uninstall_fake_cron_jobs_module():
    sys.modules.pop("cron", None)
    sys.modules.pop("cron.jobs", None)


@pytest.fixture
def profiles_module(monkeypatch, tmp_path):
    """Fresh import of profiles.py with the Hermes home directory patched."""
    mod = load_profiles_module()
    monkeypatch.setattr(mod, "get_hermes_home", lambda: tmp_path)
    yield mod
    sys.modules.pop("profiles", None)


@pytest.fixture
def flow_module(profiles_module):
    """__init__.py loaded so its `from . import profiles` resolves to the
    patched profiles_module fixture above."""
    module = load_flow_module(profiles_module)
    yield module
    for key in ("_test_cron_flow_pkg", "_test_cron_flow_pkg.profiles", "_test_cron_flow_pkg.__init__"):
        sys.modules.pop(key, None)


@pytest.fixture
def fake_cron_jobs():
    """Install/uninstall a fake `cron.jobs` module around a test."""
    jobs_by_id: dict = {}

    def _install(jobs):
        jobs_by_id.update({j["id"]: j for j in jobs})
        return install_fake_cron_jobs_module(jobs_by_id)

    yield _install
    uninstall_fake_cron_jobs_module()
