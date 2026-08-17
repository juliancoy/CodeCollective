import importlib.util
import json
import sys
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "datacenters" / "kimi_research_dashboard.py"
SPEC = importlib.util.spec_from_file_location("kimi_research_dashboard", SCRIPT)
dashboard = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
sys.modules[SPEC.name] = dashboard
SPEC.loader.exec_module(dashboard)


def status(processed=0, cost=0, searches=0, state="running"):
    return {
        "run_id": "run-12345678",
        "pipeline_id": "pipeline-123",
        "state": state,
        "elapsed_seconds": 60,
        "total": 100,
        "submitted": processed + 2,
        "processed": processed,
        "queued": 98 - processed,
        "in_flight": {"facility": "primary"},
        "workers": 2,
        "max_workers": 2,
        "verbose": True,
        "status_counts": {"ok": processed, "review": 0, "error": 0},
        "metrics": {
            "search_count": searches,
            "http_retry_count": 0,
            "estimated_cost_usd": cost,
        },
    }


def test_forecast_uses_pilot_prior_then_blends_live_results():
    state = dashboard.DashboardState("http://127.0.0.1:1", 1)
    state.record(status(), sampled_at=100)
    initial = state.metrics()["forecast"]
    assert initial["cost_per_record_usd"] == round(dashboard.PILOT_COST_PER_RECORD, 6)

    state.record(status(processed=10, cost=0.5, searches=50), sampled_at=160)
    forecast = state.metrics()["forecast"]
    expected = (0.5 + dashboard.PILOT_COST_PER_RECORD * 10) / 20
    assert forecast["cost_per_record_usd"] == round(expected, 6)
    assert forecast["records_per_minute"] == 10
    assert forecast["eta_seconds"] == 540


def test_status_transitions_create_activity_records():
    state = dashboard.DashboardState("http://127.0.0.1:1", 1)
    state.record(status(), sampled_at=100)
    changed = status(processed=1, cost=0.03, searches=3, state="paused")
    changed["in_flight"] = {"next-facility": "retry"}
    state.record(changed, sampled_at=110)

    messages = [item["message"] for item in state.metrics()["activity"]]
    assert any("state changed to paused" in message for message in messages)
    assert any("Completed 1 facility" in message for message in messages)
    assert any("entered retry" in message for message in messages)


def test_downsample_preserves_latest_sample():
    samples = [{"timestamp": index} for index in range(100)]
    result = dashboard.downsample(samples, 10)
    assert len(result) == 10
    assert result[-1] == samples[-1]


def test_received_record_store_summarizes_facets_and_sources(tmp_path):
    checkpoint = tmp_path / "research.jsonl"
    row = {
        "run_id": "run-12345678",
        "facility_id": "plant-1",
        "facility_name": "Plant One",
        "record_type": "power_plant",
        "status": "review",
        "requested_facets": ["permit_status"],
        "metrics": {"search_count": 3, "estimated_cost_usd": 0.02},
        "final_result": {
            "facets": {
                "permit_status": {
                    "confidence": "low",
                    "sources": [
                        {
                            "source_type": "primary government",
                            "url": "https://example.gov/permit",
                        }
                    ],
                }
            }
        },
    }
    checkpoint.write_text(json.dumps(row) + "\n")
    store = dashboard.ResearchRecords(checkpoint)

    summaries = store.summaries("run-12345678")
    aggregate = store.aggregate("run-12345678")

    assert summaries[0]["confidences"] == {"permit_status": "low"}
    assert summaries[0]["source_count"] == 1
    assert store.detail("run-12345678", "plant-1") == row
    assert store.latest_run_id() == "run-12345678"
    assert aggregate["records"] == 1
    assert aggregate["confidences"] == {"low": 1}
    assert aggregate["source_types"] == {"primary government": 1}


def test_received_record_summary_scores_record_quality():
    row = {
        "facility_id": "dc-1",
        "facility_name": "Data Center One",
        "final_result": {
            "facets": {
                "location": {"confidence": "high", "sources": []},
                "owner": {"confidence": "medium", "sources": []},
                "capacity": {"confidence": "low", "sources": []},
                "utility": {"confidence": "insufficient", "sources": []},
            }
        },
    }

    summary = dashboard.ResearchRecords.summarize(row)

    assert summary["quality_counts"] == {
        "high": 1,
        "medium": 1,
        "low": 1,
        "insufficient": 1,
        "unknown": 0,
    }
    assert summary["quality_score"] == 52
    assert summary["quality_label"] == "low"


def test_received_store_can_aggregate_all_runs_and_lookup_exact_run(tmp_path):
    checkpoint = tmp_path / "research.jsonl"
    rows = [
        {
            "run_id": "run-old",
            "pipeline_id": "pipeline-1",
            "facility_id": "same-id",
            "facility_name": "Older Record",
            "status": "ok",
            "final_result": {"facets": {"owner": {"confidence": "high", "sources": []}}},
        },
        {
            "run_id": "run-new",
            "pipeline_id": "pipeline-1",
            "facility_id": "same-id",
            "facility_name": "Newer Record",
            "status": "review",
            "final_result": {"facets": {"owner": {"confidence": "low", "sources": []}}},
        },
    ]
    checkpoint.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
    store = dashboard.ResearchRecords(checkpoint)

    assert store.aggregate(None)["records"] == 2
    assert store.aggregate("run-new")["records"] == 1
    assert store.detail(None, "same-id")["facility_name"] == "Newer Record"
    assert store.detail_for_run("run-old", "same-id")["facility_name"] == "Older Record"
    assert {row["run_id"] for row in store.summaries(None)} == {"run-old", "run-new"}


def test_service_settings_store_api_key_without_returning_secret(tmp_path):
    env_file = tmp_path / ".env.kimi"
    state = dashboard.DashboardState("http://127.0.0.1:1", 1)
    state.env_file = env_file

    result = state.update_service_settings({"moonshot_api_key": "sk-test-secret-123"})

    assert result["kimi_key_configured"] is True
    assert "sk-test-secret-123" not in json.dumps(result)
    assert env_file.read_text() == "MOONSHOT_API_KEY=sk-test-secret-123\n"
    assert oct(env_file.stat().st_mode & 0o777) == "0o600"
