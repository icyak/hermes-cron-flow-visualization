"""Tests for profiles.py — shared custom-profile storage."""

from __future__ import annotations

import json


def test_load_profiles_missing_file_returns_empty(profiles_module):
    assert profiles_module.load_profiles() == {}


def test_load_profiles_invalid_json_returns_empty(profiles_module, tmp_path):
    path = tmp_path / "cron_flow_profiles.json"
    path.write_text("not valid json {{{", encoding="utf-8")
    assert profiles_module.load_profiles() == {}


def test_load_profiles_non_dict_json_returns_empty(profiles_module, tmp_path):
    path = tmp_path / "cron_flow_profiles.json"
    path.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    assert profiles_module.load_profiles() == {}


def test_save_profiles_writes_valid_json_atomically(profiles_module, tmp_path):
    data = {"job-1": {"name": "Job One", "process": [{"label": "1. Go", "detail": "run"}]}}
    profiles_module.save_profiles(data)

    path = tmp_path / "cron_flow_profiles.json"
    assert path.exists()
    assert not (tmp_path / "cron_flow_profiles.json.tmp").exists()

    with open(path, "r", encoding="utf-8") as f:
        on_disk = json.load(f)
    assert on_disk == data


def test_save_profiles_creates_parent_directory(profiles_module, tmp_path):
    nested_home = tmp_path / "nested" / "home"
    profiles_module.get_hermes_home = lambda: nested_home  # noqa: E731 - simple override for this test

    profiles_module.save_profiles({"job-1": {"name": "x"}})

    assert (nested_home / "cron_flow_profiles.json").exists()


def test_upsert_get_delete_round_trip(profiles_module):
    job_id = "job-42"
    profile = {"name": "My Job", "connections": [{"type": "api", "label": "Weather"}]}

    saved = profiles_module.upsert_profile(job_id, profile)
    assert saved == profile
    assert profiles_module.get_profile(job_id) == profile

    updated = {"name": "My Job v2"}
    profiles_module.upsert_profile(job_id, updated)
    assert profiles_module.get_profile(job_id) == updated

    assert profiles_module.delete_profile(job_id) is True
    assert profiles_module.get_profile(job_id) == {}
    assert profiles_module.delete_profile(job_id) is False


def test_get_profile_missing_job_returns_empty_dict(profiles_module):
    assert profiles_module.get_profile("does-not-exist") == {}


def test_multiple_profiles_coexist(profiles_module):
    profiles_module.upsert_profile("job-a", {"name": "A"})
    profiles_module.upsert_profile("job-b", {"name": "B"})

    all_profiles = profiles_module.load_profiles()
    assert set(all_profiles.keys()) == {"job-a", "job-b"}
    assert all_profiles["job-a"]["name"] == "A"
    assert all_profiles["job-b"]["name"] == "B"
