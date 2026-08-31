import copy
import importlib.util
import json
import sys
from pathlib import Path

import pytest


SCRIPT = Path(__file__).parents[1] / "datacenters" / "research_inventory_with_kimi.py"
SPEC = importlib.util.spec_from_file_location("kimi_inventory_research", SCRIPT)
research = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
sys.modules[SPEC.name] = research
SPEC.loader.exec_module(research)


def record(**updates):
    value = {
        "id": "eia-123",
        "record_type": "power_plant",
        "name": "Example Plant",
        "state": "MD",
        "permit_status": "not researched at plant level",
        "air_permit_status": "not included in this inventory; Form EIA-860 does not report air-permit decisions",
        "legal_status": "not researched at plant level",
    }
    value.update(updates)
    return value


def test_find_targets_groups_unresolved_facets_by_facility():
    targets = research.find_targets([record()], set(), set())

    assert len(targets) == 1
    assert targets[0].facets == ("permit_status", "air_permit_status", "legal_status")


def test_find_targets_honors_type_and_id_filters():
    records = [record(), record(id="dc-1", record_type="data_center")]

    targets = research.find_targets(records, {"data_center"}, {"dc-1"})

    assert [target.record["id"] for target in targets] == ["dc-1"]


def test_find_targets_honors_state_filters():
    records = [record(id="md-1", state="MD"), record(id="va-1", state="VA")]

    targets = research.find_targets(records, set(), set(), states={"VA"})

    assert [target.record["id"] for target in targets] == ["va-1"]


def test_find_targets_uses_repair_queue_facet_overrides():
    repair = {
        "eia-123": {
            "facility_id": "eia-123",
            "facets": ["legal_status"],
            "evidence_gaps": {"legal_status": ["negative legal finding"]},
        }
    }

    targets = research.find_targets([record()], set(), set(), facet_overrides=repair)

    assert targets[0].facets == ("legal_status",)
    assert targets[0].repair_context == repair["eia-123"]
    prompt = research.build_user_prompt(targets[0], [], 1)
    assert "negative legal finding" in prompt


def test_parse_json_object_accepts_fenced_json():
    assert research.parse_json_object('```json\n{"ok": true}\n```') == {"ok": True}


def test_worldwide_power_profile_requires_numeric_cited_fields():
    source_url = "https://agency.example.gov/data-center"
    facet = {
        "value": "The facility has a published 24 MW capacity envelope.",
        "confidence": "high",
        "basis": "The facility-specific planning decision states the capacity and scope.",
        "fields": {
            "reported_grid_demand_mw": None,
            "reported_power_capacity_mw": 24,
            "projected_power_demand_mw": None,
            "estimated_power_draw_mw": None,
            "estimated_power_draw_method": None,
            "on_site_generation_capacity_mw": None,
            "energy_source_codes": [],
            "lifecycle_status": "operating",
            "value_scope": "facility",
            "as_of_date": "2026-01-01",
        },
        "field_evidence": {"reported_power_capacity_mw": [source_url]},
        "sources": [{
            "title": "Planning decision",
            "publisher": "Example Agency",
            "url": source_url,
            "document_date": "2026-01-01",
            "source_type": "primary government",
            "supports": "Facility power capacity is 24 MW.",
        }],
    }

    assert research.facet_validation_errors("power_profile", facet) == []
    facet["fields"]["reported_power_capacity_mw"] = "24 MW"
    assert any("JSON number" in error for error in research.facet_validation_errors("power_profile", facet))


def test_validate_result_requires_searches_and_citations():
    target = research.find_targets([record()], set(), set())[0]
    result = {
        "facility_id": "eia-123",
        "facility_name": "Example Plant",
        "researched_at": "2026-08-16",
        "facets": {
            facet: {
                "value": "No facility-specific proceeding identified in reviewed records as of 2026-08-16.",
                "confidence": "medium",
                "basis": "The agency facility record was reviewed and did not identify the requested proceeding.",
                "sources": [{
                    "title": "Facility record",
                    "publisher": "Maryland agency",
                    "url": "https://example.gov/facility",
                    "document_date": None,
                    "source_type": "primary government",
                    "supports": "Facility-specific status and agency record coverage.",
                }],
            }
            for facet in target.facets
        },
        "research_notes": None,
    }

    research.validate_result(result, target, ["query one", "query two"], 2)
    with pytest.raises(research.KimiError, match="distinct searches"):
        research.validate_result(result, target, ["query one"], 2)


def test_normalize_result_discards_only_unrequested_facets():
    target = research.find_targets([record()], set(), set())[0]
    requested = {facet: {"value": facet} for facet in target.facets}
    result = {
        "facility_id": "eia-123",
        "facets": {**requested, "unrequested_facet": {"value": "discard me"}},
    }

    normalized, ignored = research.normalize_result(result, target)

    assert normalized["facets"] == requested
    assert ignored == ["unrequested_facet"]
    assert "unrequested_facet" in result["facets"]


def test_completed_checkpoint_requires_same_pipeline_and_fingerprint(tmp_path):
    checkpoint = tmp_path / "research.jsonl"
    checkpoint.write_text(json.dumps({
        "status": "ok",
        "facility_id": "eia-123",
        "input_fingerprint": "abc",
        "pipeline_id": "pipeline-123",
    }) + "\n")

    assert research.load_completed(checkpoint, "pipeline-123") == {("eia-123", "abc")}
    assert research.load_completed(checkpoint, "different-pipeline") == set()


def test_agent_loop_preserves_reasoning_and_returns_formula_result():
    target = research.find_targets([record()], set(), set())[0]
    client = object.__new__(research.KimiClient)
    client.formula_uri = "moonshot/web-search:latest"
    client.max_tool_rounds = 3
    client.max_searches = 4
    client.tools = [{"type": "function", "function": {"name": "web_search"}}]
    calls = []
    final = {
        "facility_id": "eia-123",
        "facility_name": "Example Plant",
        "facets": {},
    }

    def fake_request(method, path, body=None, _metrics=None):
        calls.append((method, path, copy.deepcopy(body)))
        if path.endswith("/fibers"):
            return {"context": {"encrypted_output": "encrypted search evidence"}}
        chat_calls = [call for call in calls if call[1] == "/chat/completions"]
        if len(chat_calls) == 1:
            return {"choices": [{"message": {
                "role": "assistant",
                "content": None,
                "reasoning_content": "I should search the agency record.",
                "tool_calls": [{
                    "id": "web_search:0",
                    "type": "function",
                    "function": {"name": "web_search", "arguments": '{"query":"Example Plant permit"}'},
                }],
            }}]}
        return {"choices": [{"message": {"role": "assistant", "content": json.dumps(final)}}]}

    client._request = fake_request
    stage = research.Stage(
        name="primary",
        model="kimi-k2.6",
        thinking="disabled",
        minimum_searches=1,
    )

    run = client.research(target, [], stage)

    assert run.result == final
    assert run.queries == ["Example Plant permit"]
    chat_bodies = [call[2] for call in calls if call[1] == "/chat/completions"]
    assert chat_bodies[0]["tool_choice"] == {
        "type": "function",
        "function": {"name": "web_search"},
    }
    second_chat_body = chat_bodies[1]
    assert second_chat_body["model"] == "kimi-k2.6"
    assert second_chat_body["thinking"] == {"type": "disabled"}
    assert second_chat_body["tool_choice"] == "auto"
    assert second_chat_body["messages"][-2]["reasoning_content"] == "I should search the agency record."
    assert second_chat_body["messages"][-1] == {
        "role": "tool",
        "tool_call_id": "web_search:0",
        "content": "encrypted search evidence",
    }


def test_prompt_profile_selects_system_prompt():
    target = research.find_targets([record()], set(), set())[0]

    assert (
        research.system_prompt_for_target(target, "worldwide-datacenter-power")
        == research.WORLDWIDE_POWER_SYSTEM_PROMPT
    )
    assert (
        research.system_prompt_for_target(target, "maryland-infrastructure")
        == research.SYSTEM_PROMPT
    )


def test_agent_loop_forces_each_required_search_before_json_synthesis():
    target = research.find_targets([record()], set(), set())[0]
    client = object.__new__(research.KimiClient)
    client.formula_uri = "moonshot/web-search:latest"
    client.max_tool_rounds = 4
    client.max_searches = 4
    client.tools = [{"type": "function", "function": {"name": "web_search"}}]
    chat_bodies = []
    search_index = 0

    def fake_request(method, path, body=None, _metrics=None):
        nonlocal search_index
        if path.endswith("/fibers"):
            search_index += 1
            return {"context": {"encrypted_output": f"evidence {search_index}"}}
        chat_bodies.append(copy.deepcopy(body))
        if len(chat_bodies) <= 2:
            return {"choices": [{"message": {
                "role": "assistant",
                "content": None,
                "tool_calls": [{
                    "id": f"web_search:{len(chat_bodies) - 1}",
                    "type": "function",
                    "function": {
                        "name": "web_search",
                        "arguments": json.dumps({"query": f"distinct query {len(chat_bodies)}"}),
                    },
                }],
            }}]}
        return {"choices": [{"message": {"role": "assistant", "content": "{}"}}]}

    client._request = fake_request
    stage = research.Stage("retry", "kimi-k2.6", 2, thinking="disabled")

    run = client.research(target, [], stage)

    assert run.queries == ["distinct query 1", "distinct query 2"]
    forced_choice = {"type": "function", "function": {"name": "web_search"}}
    assert [body["tool_choice"] for body in chat_bodies] == [
        forced_choice,
        forced_choice,
        "auto",
    ]


def test_confidence_retry_stops_before_k3():
    target = research.find_targets([record()], set(), set())[0]
    stages = [
        research.Stage("primary", "kimi-k2.6", 1, thinking="disabled"),
        research.Stage("retry", "kimi-k2.6", 2, thinking="disabled"),
        research.Stage("escalation", "kimi-k3", 2, reasoning_effort="low"),
    ]
    calls = []

    def result(confidence):
        return {
            "facility_id": "eia-123",
            "facility_name": "Example Plant",
            "researched_at": "2026-08-16",
            "facets": {
                facet: {
                    "value": "Facility-specific status found in the reviewed agency record.",
                    "confidence": confidence,
                    "basis": "The cited agency facility record directly reports the requested status.",
                    "sources": [{
                        "title": "Facility record",
                        "publisher": "Maryland agency",
                        "url": "https://example.gov/facility",
                        "document_date": None,
                        "source_type": "primary government",
                        "supports": "Facility-specific status.",
                    }],
                }
                for facet in target.facets
            },
            "research_notes": None,
        }

    class FakeClient:
        def research(
            self,
            _target,
            _sources,
            stage,
            request_metrics,
            queries_out,
            prior_result,
            prior_queries,
        ):
            calls.append(stage.name)
            confidence = "low" if stage.name == "primary" else "medium"
            if stage.name == "primary":
                queries_out.append("query 0")
                assert prior_result is None
                assert prior_queries == []
            else:
                assert prior_result == result("low")
                assert prior_queries == ["query 0"]
                queries_out.append("query 1")
            return research.ResearchRun(result(confidence), queries_out, request_metrics)

    entry = research.research_one(
        FakeClient(), target, {}, stages, "medium", "run-123", "pipeline-123"
    )

    assert entry["status"] == "ok"
    assert entry["final_stage"] == "retry"
    assert calls == ["primary", "retry"]
    assert entry["attempts"][1]["search_queries"] == ["query 1"]


def test_complete_low_confidence_result_skips_synthesis_only_retry():
    target = research.find_targets([record()], set(), set())[0]
    valid_facet = {
        "value": "No facility-specific decision was identified in the reviewed records.",
        "confidence": "low",
        "basis": "The cited agency facility record was reviewed for the requested status.",
        "sources": [{
            "title": "Facility record",
            "publisher": "Maryland agency",
            "url": "https://example.gov/facility",
            "document_date": None,
            "source_type": "primary government",
            "supports": "Facility-specific status.",
        }],
    }
    result = {
        "facility_id": target.record["id"],
        "facility_name": target.record["name"],
        "facets": {facet: valid_facet for facet in target.facets},
    }
    calls = []

    class FakeClient:
        def research(self, *_args):
            stage = _args[2]
            request_metrics = _args[3]
            queries_out = _args[4]
            calls.append(stage.name)
            queries_out.extend(["query 0", "query 1"])
            return research.ResearchRun(result, queries_out, request_metrics)

    entry = research.research_one(
        FakeClient(),
        target,
        {},
        [
            research.Stage("primary", "kimi-k2.6", 1, thinking="disabled"),
            research.Stage("retry", "kimi-k2.6", 2, thinking="disabled"),
        ],
        "medium",
        "run-123",
        "pipeline-123",
    )

    assert entry["status"] == "review"
    assert calls == ["primary"]
    assert entry["attempts"][1]["status"] == "skipped"
    assert entry["metrics"]["stage_count"] == 1


def test_research_one_preserves_valid_facets_from_partial_result():
    target = research.find_targets([record()], set(), set())[0]
    valid_facet = {
        "value": "Facility-specific status found in the reviewed agency record.",
        "confidence": "medium",
        "basis": "The cited agency facility record directly reports the requested status.",
        "sources": [{
            "title": "Facility record",
            "publisher": "Maryland agency",
            "url": "https://example.gov/facility",
            "document_date": None,
            "source_type": "primary government",
            "supports": "Facility-specific status.",
        }],
    }
    partial = {
        "facility_id": target.record["id"],
        "facility_name": target.record["name"],
        "facets": {
            target.facets[0]: valid_facet,
            target.facets[1]: {"value": "missing evidence"},
        },
    }
    calls = []

    class FakeClient:
        def research(self, *_args):
            stage = _args[2]
            request_metrics = _args[3]
            queries_out = _args[4]
            calls.append(stage.name)
            queries_out.append(f"{stage.name} query")
            return research.ResearchRun(partial, queries_out, request_metrics)

    entry = research.research_one(
        FakeClient(),
        target,
        {},
        [
            research.Stage("primary", "kimi-k2.6", 1, thinking="disabled"),
            research.Stage("retry", "kimi-k2.6", 2, thinking="disabled"),
        ],
        "medium",
        "run-123",
        "pipeline-123",
    )

    assert calls == ["primary", "retry"]
    assert entry["status"] == "review"
    assert set(entry["final_result"]["facets"]) == {target.facets[0]}
    assert entry["attempts"][0]["status"] == "partial"
    assert entry["attempts"][0]["salvaged_facets"] == [target.facets[0]]
    assert target.facets[1] in entry["error"]


def test_research_one_records_invalid_result_for_analysis():
    target = research.find_targets([record()], set(), set())[0]
    invalid = {
        "facility_id": "eia-123",
        "facility_name": "Example Plant",
        "facets": {},
    }

    class FakeClient:
        def research(
            self, _target, _sources, _stage, request_metrics, queries_out, *_prior
        ):
            queries_out.append("facility permit")
            return research.ResearchRun(invalid, queries_out, request_metrics)

    entry = research.research_one(
        FakeClient(),
        target,
        {},
        [research.Stage("primary", "kimi-k2.6", 1, thinking="disabled")],
        "medium",
        "run-123",
        "pipeline-123",
    )

    assert entry["status"] == "error"
    assert entry["attempts"][0]["invalid_result"] == invalid


def test_research_one_accepts_requested_facets_and_records_ignored_extras():
    target = research.find_targets([record()], set(), set())[0]
    valid_facet = {
        "value": "Facility-specific status found in the reviewed agency record.",
        "confidence": "medium",
        "basis": "The cited agency facility record directly reports the requested status.",
        "sources": [{
            "title": "Facility record",
            "publisher": "Maryland agency",
            "url": "https://example.gov/facility",
            "document_date": None,
            "source_type": "primary government",
            "supports": "Facility-specific status.",
        }],
    }
    result = {
        "facility_id": "eia-123",
        "facility_name": "Example Plant",
        "facets": {
            **{facet: valid_facet for facet in target.facets},
            "unrequested_facet": valid_facet,
        },
    }

    class FakeClient:
        def research(
            self, _target, _sources, _stage, request_metrics, queries_out, *_prior
        ):
            queries_out.append("facility permit")
            return research.ResearchRun(result, queries_out, request_metrics)

    entry = research.research_one(
        FakeClient(),
        target,
        {},
        [research.Stage("primary", "kimi-k2.6", 1, thinking="disabled")],
        "medium",
        "run-123",
        "pipeline-123",
    )

    assert entry["status"] == "ok"
    assert set(entry["final_result"]["facets"]) == set(target.facets)
    assert entry["attempts"][0]["ignored_unrequested_facets"] == [
        "unrequested_facet"
    ]


def test_k3_stage_uses_low_reasoning_without_thinking_parameter():
    target = research.find_targets([record()], set(), set())[0]
    client = object.__new__(research.KimiClient)
    client.formula_uri = "moonshot/web-search:latest"
    client.max_tool_rounds = 1
    client.max_searches = 2
    client.tools = [{"type": "function", "function": {"name": "web_search"}}]
    bodies = []

    def fake_request(_method, path, body=None, _metrics=None):
        assert path == "/chat/completions"
        bodies.append(copy.deepcopy(body))
        return {"choices": [{"message": {"role": "assistant", "content": "{}"}}]}

    client._request = fake_request
    stage = research.Stage(
        "escalation", "kimi-k3", 2, reasoning_effort="low"
    )

    client.research(target, [], stage)

    assert bodies[0]["model"] == "kimi-k3"
    assert bodies[0]["reasoning_effort"] == "low"
    assert bodies[0]["tool_choice"] == "auto"
    assert "thinking" not in bodies[0]


def test_request_summary_records_usage_retries_and_conservative_cost():
    requests = [{
        "kind": "chat_completion",
        "elapsed_seconds": 2.5,
        "retry_count": 1,
        "usage": {
            "prompt_tokens": 10_000,
            "completion_tokens": 1_000,
            "total_tokens": 11_000,
            "prompt_tokens_details": {"cached_tokens": 2_000},
            "completion_tokens_details": {"reasoning_tokens": 300},
        },
    }]

    summary = research.summarize_requests(requests, "kimi-k2.6", search_count=1)

    assert summary["request_count"] == 1
    assert summary["http_retry_count"] == 1
    assert summary["cached_prompt_tokens"] == 2_000
    assert summary["reasoning_tokens"] == 300
    assert summary["estimated_cost_usd"] == pytest.approx(0.01692)


def test_load_env_value_supports_export_quotes_and_comments(tmp_path):
    env_file = tmp_path / ".env.kimi"
    env_file.write_text(
        "# Kimi credentials\n"
        "IGNORED=value\n"
        "export MOONSHOT_API_KEY='secret-value'\n"
    )

    assert research.load_env_value(env_file, "MOONSHOT_API_KEY") == "secret-value"
    assert research.load_env_value(env_file, "MISSING") is None


def test_validate_args_ignores_search_minimums_for_disabled_tiers():
    args = research.argparse.Namespace(
        workers=1,
        progress_every=1,
        retries=0,
        max_tool_rounds=2,
        max_searches=1,
        primary_minimum_searches=1,
        retry_minimum_searches=2,
        escalation_minimum_searches=2,
        max_tier="primary",
        limit=1,
        heartbeat_seconds=30,
        control_host="127.0.0.1",
        control_port=0,
        max_workers=4,
    )

    research.validate_args(args)


def test_control_api_reports_status_and_changes_runtime_controls():
    control = research.ControlState(
        "run-123", "pipeline-123", 10, 3, False, max_workers=4
    )
    server, thread = research.start_control_server("127.0.0.1", 0, control)
    base_url = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        status = research.requests.get(f"{base_url}/status", timeout=2)
        assert status.status_code == 200
        assert status.json()["state"] == "running"

        changed = research.requests.post(
            f"{base_url}/control",
            json={"paused": True, "workers": 1, "verbose": True},
            timeout=2,
        )
        assert changed.status_code == 200
        assert changed.json()["state"] == "paused"
        assert changed.json()["workers"] == 1
        assert changed.json()["verbose"] is True

        invalid = research.requests.post(
            f"{base_url}/control",
            json={"paused": False, "workers": 5},
            timeout=2,
        )
        assert invalid.status_code == 400
        assert control.snapshot()["state"] == "paused"

        increased = research.requests.post(
            f"{base_url}/control", json={"workers": 4}, timeout=2
        )
        assert increased.status_code == 200
        assert increased.json()["workers"] == 4

        stopped = research.requests.post(
            f"{base_url}/control", json={"stop": True}, timeout=2
        )
        assert stopped.status_code == 200
        assert stopped.json()["state"] == "stopping"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_graceful_stop_prevents_the_next_research_tier():
    target = research.find_targets(
        [record(air_permit_status="resolved", legal_status="resolved")], set(), set()
    )[0]
    result = {
        "facility_id": "eia-123",
        "facility_name": "Example Plant",
        "facets": {
            "permit_status": {
                "value": "No facility-specific permit was established.",
                "confidence": "insufficient",
                "basis": "The reviewed agency source did not expose the historical permit record.",
                "sources": [{
                    "title": "Facility record",
                    "publisher": "Maryland agency",
                    "url": "https://example.gov/facility",
                    "source_type": "primary government",
                    "supports": "Agency record coverage.",
                }],
            }
        },
    }
    control = research.ControlState("run-123", "pipeline-123", 1, 1, False)
    calls = []

    class FakeClient:
        def research(self, _target, _sources, stage, metrics, queries, *_prior):
            calls.append(stage.name)
            queries.append("facility permit")
            control.update({"stop": True})
            return research.ResearchRun(result, queries, metrics)

    entry = research.research_one(
        FakeClient(),
        target,
        {},
        [
            research.Stage("primary", "kimi-k2.6", 1, thinking="disabled"),
            research.Stage("retry", "kimi-k2.6", 2, thinking="disabled"),
        ],
        "medium",
        "run-123",
        "pipeline-123",
        control,
    )

    assert calls == ["primary"]
    assert entry["status"] == "review"
