"""Tests for __init__.py's flow-building logic (build_flow and friends)."""

from __future__ import annotations

import json


def test_build_flow_no_agent_uses_generic_script_steps(flow_module):
    job = {
        "id": "job-1",
        "name": "Backup job",
        "schedule": {"display": "every day at 8am", "expr": "0 8 * * *"},
        "no_agent": True,
        "script": "/opt/scripts/backup.sh",
        "deliver": "local",
    }

    flow = flow_module.build_flow(job)

    assert flow["id"] == "job-1"
    assert flow["name"] == "Backup job"
    assert flow["has_custom_profile"] is False
    labels = [step["label"] for step in flow["process"]]
    assert labels == ["1. Trigger", "2. Run script", "3. Deliver"]
    assert "backup.sh" in flow["process"][1]["detail"]
    assert flow["process"][0]["detail"] == "Cron fires on: every day at 8am"


def test_build_flow_no_agent_missing_script_notes_it(flow_module):
    job = {"id": "job-2", "no_agent": True}

    flow = flow_module.build_flow(job)

    assert "(no script set)" in flow["process"][1]["detail"]


def test_build_flow_agent_with_skills_script_and_context_from(flow_module):
    job = {
        "id": "job-3",
        "name": "Digest job",
        "schedule": {"expr": "0 7 * * *"},
        "skills": ["deep-research", "dataviz"],
        "script": "/opt/scripts/pull.py",
        "context_from": ["job-1", "job-2"],
        "deliver": "telegram",
    }

    flow = flow_module.build_flow(job)

    labels = [step["label"] for step in flow["process"]]
    assert labels == ["1. Trigger", "2. Agent run", "2a. Script context", "2b. Chained context", "3. Deliver"]
    assert "deep-research, dataviz" in flow["process"][1]["detail"]
    assert flow["process"][2]["detail"] == "Script stdout injected into prompt: /opt/scripts/pull.py"
    assert flow["process"][3]["detail"] == "Injects last output of job(s): ['job-1', 'job-2']"
    assert flow["process"][0]["detail"] == "Cron fires on: 0 7 * * *"


def test_build_flow_agent_no_skills_no_script_no_context(flow_module):
    job = {"id": "job-4", "deliver": "email"}

    flow = flow_module.build_flow(job)

    labels = [step["label"] for step in flow["process"]]
    assert labels == ["1. Trigger", "2. Agent run", "3. Deliver"]
    assert flow["process"][1]["detail"] == "LLM agent runs the job prompt"


def test_generic_connections_script_workdir_provider_and_deliver(flow_module):
    job = {
        "id": "job-5",
        "script": "/opt/scripts/x.py",
        "workdir": "/opt/scripts",
        "provider": "anthropic",
        "model": "claude-sonnet-5",
        "deliver": "telegram",
    }

    flow = flow_module.build_flow(job)

    types_ = [c["type"] for c in flow["connections"]]
    labels = [c["label"] for c in flow["connections"]]
    assert labels == ["Script", "Working directory", "Model provider", "Delivery channel"]
    assert types_ == ["file", "file", "api", "api"]
    assert flow["connections"][2]["detail"] == "anthropic / claude-sonnet-5"
    assert flow["connections"][3]["detail"] == "telegram"


def test_generic_connections_local_deliver_not_added(flow_module):
    job = {"id": "job-6", "deliver": "local"}

    flow = flow_module.build_flow(job)

    assert flow["connections"] == []


def test_generic_connections_provider_or_model_alone(flow_module):
    job = {"id": "job-7", "model": "claude-haiku-4-5-20251001"}

    flow = flow_module.build_flow(job)

    assert flow["connections"][0]["detail"] == "default / claude-haiku-4-5-20251001"


def test_build_flow_with_custom_profile_overrides_generic(flow_module, profiles_module):
    job_id = "job-8"
    custom_profile = {
        "name": "Custom Name",
        "connections": [{"type": "api", "label": "Custom API", "detail": "..."}],
        "process": [{"label": "1. Custom step", "detail": "does a custom thing"}],
    }
    profiles_module.upsert_profile(job_id, custom_profile)

    job = {
        "id": job_id,
        "name": "Fallback Name",
        "script": "/opt/scripts/should-not-appear.py",
        "deliver": "email",
    }
    flow = flow_module.build_flow(job)

    assert flow["name"] == "Custom Name"
    assert flow["has_custom_profile"] is True
    assert flow["connections"] == custom_profile["connections"]
    assert flow["process"] == custom_profile["process"]


def test_build_flow_no_job_id_skips_profile_lookup(flow_module):
    job = {"name": "No id job", "deliver": "local"}

    flow = flow_module.build_flow(job)

    assert flow["id"] is None
    assert flow["has_custom_profile"] is False


def test_build_flow_name_falls_back_to_job_name_then_job_id(flow_module):
    flow_with_job_name = flow_module.build_flow({"id": "job-9", "deliver": "local"})
    assert flow_with_job_name["name"] == "job-9"

    flow_with_name = flow_module.build_flow({"id": "job-10", "name": "Named", "deliver": "local"})
    assert flow_with_name["name"] == "Named"


def test_handle_cron_flow_visualize_list(flow_module, fake_cron_jobs):
    fake_cron_jobs([
        {"id": "job-1", "name": "One", "enabled": True, "deliver": "local"},
        {"id": "job-2", "name": "Two", "enabled": False, "deliver": "local"},
    ])

    result = json.loads(flow_module._handle_cron_flow_visualize({"action": "list"}))

    assert result["success"] is True
    assert result["count"] == 1
    assert result["jobs"][0]["id"] == "job-1"


def test_handle_cron_flow_visualize_list_include_disabled(flow_module, fake_cron_jobs):
    fake_cron_jobs([
        {"id": "job-1", "name": "One", "enabled": True, "deliver": "local"},
        {"id": "job-2", "name": "Two", "enabled": False, "deliver": "local"},
    ])

    result = json.loads(
        flow_module._handle_cron_flow_visualize({"action": "list", "include_disabled": True})
    )

    assert result["count"] == 2


def test_handle_cron_flow_visualize_show_missing_job(flow_module, fake_cron_jobs):
    fake_cron_jobs([])

    result = json.loads(flow_module._handle_cron_flow_visualize({"action": "show", "job_id": "nope"}))

    assert result["success"] is False
    assert "nope" in result["error"]


def test_handle_cron_flow_visualize_show_requires_job_id(flow_module, fake_cron_jobs):
    fake_cron_jobs([])

    result = json.loads(flow_module._handle_cron_flow_visualize({"action": "show"}))

    assert result["success"] is False
    assert "job_id" in result["error"]


def test_handle_cron_flow_visualize_set_and_delete_profile(flow_module, fake_cron_jobs):
    fake_cron_jobs([{"id": "job-1", "name": "One", "enabled": True, "deliver": "local"}])

    set_result = json.loads(flow_module._handle_cron_flow_visualize({
        "action": "set_profile",
        "job_id": "job-1",
        "profile_json": json.dumps({"name": "Custom"}),
    }))
    assert set_result["success"] is True
    assert set_result["profile"]["name"] == "Custom"

    show_result = json.loads(flow_module._handle_cron_flow_visualize({"action": "show", "job_id": "job-1"}))
    assert show_result["flow"]["name"] == "Custom"
    assert show_result["flow"]["has_custom_profile"] is True

    delete_result = json.loads(
        flow_module._handle_cron_flow_visualize({"action": "delete_profile", "job_id": "job-1"})
    )
    assert delete_result["success"] is True
    assert delete_result["removed"] is True


def test_handle_cron_flow_visualize_set_profile_invalid_json(flow_module, fake_cron_jobs):
    fake_cron_jobs([{"id": "job-1", "name": "One", "enabled": True, "deliver": "local"}])

    result = json.loads(flow_module._handle_cron_flow_visualize({
        "action": "set_profile",
        "job_id": "job-1",
        "profile_json": "{not json",
    }))

    assert result["success"] is False
    assert "not valid JSON" in result["error"]


def test_handle_cron_flow_visualize_set_profile_connection_missing_type(
    flow_module, fake_cron_jobs, profiles_module
):
    fake_cron_jobs([{"id": "job-1", "name": "One", "enabled": True, "deliver": "local"}])

    result = json.loads(flow_module._handle_cron_flow_visualize({
        "action": "set_profile",
        "job_id": "job-1",
        "profile_json": json.dumps({
            "connections": [{"label": "Weather API", "detail": "..."}],
        }),
    }))

    assert result["success"] is False
    assert "validation" in result["error"]
    assert profiles_module.get_profile("job-1") == {}


def test_handle_cron_flow_visualize_set_profile_connection_invalid_type(
    flow_module, fake_cron_jobs, profiles_module
):
    fake_cron_jobs([{"id": "job-1", "name": "One", "enabled": True, "deliver": "local"}])

    result = json.loads(flow_module._handle_cron_flow_visualize({
        "action": "set_profile",
        "job_id": "job-1",
        "profile_json": json.dumps({
            "connections": [{"type": "ftp", "label": "Legacy drop"}],
        }),
    }))

    assert result["success"] is False
    assert "validation" in result["error"]
    assert profiles_module.get_profile("job-1") == {}


def test_handle_cron_flow_visualize_set_profile_valid_connections_and_process_round_trip(
    flow_module, fake_cron_jobs
):
    fake_cron_jobs([{"id": "job-1", "name": "One", "enabled": True, "deliver": "local"}])

    profile = {
        "name": "Custom",
        "connections": [
            {"type": "api", "label": "Weather API", "detail": "...", "direction": "read", "auth": "API key"},
        ],
        "process": [{"label": "1. Fetch data", "detail": "..."}],
    }

    set_result = json.loads(flow_module._handle_cron_flow_visualize({
        "action": "set_profile",
        "job_id": "job-1",
        "profile_json": json.dumps(profile),
    }))

    assert set_result["success"] is True
    assert set_result["profile"] == profile

    show_result = json.loads(flow_module._handle_cron_flow_visualize({"action": "show", "job_id": "job-1"}))
    assert show_result["flow"]["connections"] == profile["connections"]
    assert show_result["flow"]["process"] == profile["process"]


def test_handle_cron_flow_visualize_unknown_action(flow_module, fake_cron_jobs):
    fake_cron_jobs([])

    result = json.loads(
        flow_module._handle_cron_flow_visualize({"action": "bogus", "job_id": "job-1"})
    )

    assert result["success"] is False
    assert "Unknown action" in result["error"]


def test_cmd_cronflow_no_args_lists_jobs(flow_module, fake_cron_jobs):
    fake_cron_jobs([
        {"id": "job-1", "name": "One", "enabled": True, "deliver": "local",
         "schedule": {"display": "daily"}},
    ])

    text = flow_module._cmd_cronflow("")

    assert "Cron jobs — flow overview" in text
    assert "job-1" in text
    assert "One" in text


def test_cmd_cronflow_no_jobs(flow_module, fake_cron_jobs):
    fake_cron_jobs([])

    text = flow_module._cmd_cronflow("")

    assert text == "No cron jobs found."


def test_cmd_cronflow_with_job_id_renders_flow(flow_module, fake_cron_jobs):
    fake_cron_jobs([
        {"id": "job-1", "name": "One", "enabled": True, "deliver": "local",
         "schedule": {"display": "daily"}, "skills": ["deep-research"]},
    ])

    text = flow_module._cmd_cronflow("job-1")

    assert "## One" in text
    assert "job-1" in text
    assert "Skills:" in text
    assert "Generic flow" in text


def test_cmd_cronflow_unknown_job(flow_module, fake_cron_jobs):
    fake_cron_jobs([])

    text = flow_module._cmd_cronflow("nope")

    assert "No cron job found matching 'nope'" in text
