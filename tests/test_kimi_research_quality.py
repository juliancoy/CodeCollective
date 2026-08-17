import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).parents[1]
DATACENTERS = ROOT / "datacenters"
sys.path.insert(0, str(DATACENTERS))


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


quality = load_module("kimi_research_quality", DATACENTERS / "kimi_research_quality.py")
research = load_module("research_inventory_with_kimi", DATACENTERS / "research_inventory_with_kimi.py")
promote = load_module("promote_kimi_research", DATACENTERS / "promote_kimi_research.py")
auditor = load_module("audit_kimi_research", DATACENTERS / "audit_kimi_research.py")
generator = load_module("generate_datacenter_energy_data", DATACENTERS / "generate_datacenter_energy_data.py")


def facility():
    return {
        "id": "eia-123",
        "record_type": "power_plant",
        "eia_plant_code": 123,
        "name": "Example Solar Plant",
        "operator": "Example Energy",
        "state": "MD",
        "permit_status": "not researched at plant level",
        "air_permit_status": "not included in this inventory; Form EIA-860 does not report air-permit decisions",
        "legal_status": "not researched at plant level",
        "status_source_ids": ["existing-source"],
    }


def source(url="https://agency.example.gov/permit"):
    return {
        "title": "Example Solar Plant Permit",
        "publisher": "Example Agency",
        "url": url,
        "document_date": "2026-01-01",
        "source_type": "primary government",
        "supports": "Example Solar Plant permit was approved.",
    }


def fetched(text):
    return quality.FetchResult(
        url="https://agency.example.gov/permit",
        final_url="https://agency.example.gov/permit",
        status_code=200,
        content_type="text/html",
        content_sha256="abc123",
        text=text,
        error=None,
    )


def test_positive_facility_specific_permit_can_become_promotion_ready():
    facet = {
        "value": "Permit approved in January 2026.",
        "confidence": "high",
        "basis": "The agency decision directly names the facility and approval.",
        "sources": [source()],
    }
    cache = {
        quality.normalize_url(source()["url"]): fetched(
            "Example Solar Plant permit application was approved by the agency in January 2026."
        )
    }

    decision = quality.audit_facet("permit_status", facet, facility(), cache)

    assert decision["promotion_ready"] is True
    assert decision["sources"][0]["identity_match"] is True
    assert decision["sources"][0]["facet_match"] is True


def test_negative_air_claim_is_not_accepted_from_generation_data():
    eia_source = source("https://www.eia.gov/electricity/data/eia860/example.zip")
    facet = {
        "value": "No air permit is required for this solar facility.",
        "confidence": "high",
        "basis": "Solar generation has no combustion emissions.",
        "sources": [eia_source],
    }
    cache = {
        quality.normalize_url(eia_source["url"]): quality.FetchResult(
            eia_source["url"], eia_source["url"], 200, "application/zip", "abc", "", None
        )
    }

    decision = quality.audit_facet("air_permit_status", facet, facility(), cache)

    assert decision["promotion_ready"] is False
    assert decision["recommended_action"] == "regulatory_rule"
    assert "air-permit non-applicability requires a reviewed regulatory rule" in decision["reasons"]


def test_negative_legal_claim_always_requires_review():
    facet = {
        "value": "No litigation was identified for the facility.",
        "confidence": "medium",
        "basis": "The court docket was searched using the facility name.",
        "sources": [source()],
    }
    cache = {
        quality.normalize_url(source()["url"]): fetched(
            "Example Solar Plant court case docket search litigation appeal"
        )
    }

    decision = quality.audit_facet("legal_status", facet, facility(), cache)

    assert decision["promotion_ready"] is False
    assert decision["recommended_action"] == "human_review"
    assert "negative legal findings require human review" in decision["reasons"]


def test_negative_on_site_generation_claim_requires_review():
    facet = {
        "value": "No on-site natural gas power plant was identified.",
        "confidence": "medium",
        "basis": "The facility records did not identify combustion generation.",
        "sources": [source()],
    }
    cache = {
        quality.normalize_url(source()["url"]): fetched(
            "Example Solar Plant permit record discusses natural gas generator equipment."
        )
    }

    decision = quality.audit_facet(
        "on_site_natural_gas_power_plant", facet, facility(), cache
    )

    assert decision["promotion_ready"] is False
    assert decision["recommended_action"] == "human_review"
    assert "negative or absence finding requires human review" in decision["reasons"]


def test_financing_claim_cannot_be_promoted_as_permit_status():
    facet = {
        "value": "Conditional use approved; PILOT agreement authorized in 2023.",
        "confidence": "high",
        "basis": "The county approved both actions.",
        "sources": [source()],
    }
    cache = {
        quality.normalize_url(source()["url"]): fetched(
            "Example Solar Plant conditional use permit approved and PILOT agreement authorized."
        )
    }

    decision = quality.audit_facet("permit_status", facet, facility(), cache)

    assert decision["promotion_ready"] is False
    assert decision["recommended_action"] == "human_review"
    assert "out-of-scope financing" in decision["reasons"][0]


def test_excerpt_prefers_closest_facility_and_facet_passage():
    text = (
        "Example Solar Plant navigation " + "unrelated " * 200
        + "Example Solar Plant received permit 24-123 after agency approval."
    )

    excerpt = quality.evidence_excerpt(text, facility(), "permit_status")

    assert "received permit 24 123" in excerpt


def test_promotion_writes_source_override_inventory_and_history(tmp_path, monkeypatch):
    record = facility()
    facets = ("permit_status",)
    fingerprint = research.hashlib.sha256(
        research.canonical_json(research.target_context(record, facets)).encode()
    ).hexdigest()
    audit_source = {
        **source(),
        "normalized_url": quality.normalize_url(source()["url"]),
        "source_class": "government",
        "final_url": source()["url"],
        "usable": True,
    }
    audit = {
        "facility_id": record["id"],
        "facility_name": record["name"],
        "run_id": "run-1",
        "pipeline_id": "pipeline-1",
        "input_fingerprint": fingerprint,
        "facets": {
            "permit_status": {
                "promotion_ready": True,
                "value": "Permit approved in January 2026.",
                "sources": [audit_source],
                "judge": {"supported_urls": [source()["url"]]},
            }
        },
    }
    inventory = tmp_path / "infrastructure.json"
    sources = tmp_path / "sources.json"
    audits = tmp_path / "audit.jsonl"
    overrides = tmp_path / "overrides.json"
    history = tmp_path / "history.jsonl"
    inventory.write_text(json.dumps([record]) + "\n")
    sources.write_text(json.dumps([{
        "id": "existing-source",
        "title": "Existing",
        "publisher": "EIA",
        "document_date": "2024",
        "retrieved_date": "2025-01-01",
        "url": "https://www.eia.gov/existing",
        "local_path": None,
        "local_sha256": None,
        "source_tier": "primary",
        "used_for": "existing status",
    }]) + "\n")
    audits.write_text(json.dumps(audit) + "\n")
    monkeypatch.setattr(sys, "argv", [
        "promote_kimi_research.py",
        "--audit", str(audits),
        "--inventory", str(inventory),
        "--sources", str(sources),
        "--overrides", str(overrides),
        "--history", str(history),
        "--apply",
        "--skip-tests",
    ])

    assert promote.main() == 0

    promoted = json.loads(inventory.read_text())[0]
    source_rows = json.loads(sources.read_text())
    override = json.loads(overrides.read_text())
    events = [json.loads(line) for line in history.read_text().splitlines()]
    assert promoted["permit_status"] == "Permit approved in January 2026."
    assert len(source_rows) == 2
    assert source_rows[1]["id"] in promoted["status_source_ids"]
    assert override["facilities"][record["id"]]["permit_status"] == promoted["permit_status"]
    assert [event["event"] for event in events] == ["promotion_prepared", "promotion_committed"]


def test_generator_reapplies_research_overrides(tmp_path):
    records = [facility()]
    overrides = tmp_path / "overrides.json"
    overrides.write_text(json.dumps({
        "version": 1,
        "facilities": {
            "eia-123": {"permit_status": "Approved", "status_source_ids": ["source-1"]}
        },
    }))

    result = generator.apply_research_overrides(records, overrides)

    assert result[0]["permit_status"] == "Approved"
    assert result[0]["status_source_ids"] == ["source-1"]


def test_lexical_candidate_is_not_promotion_ready_without_judgment():
    audits = [{
        "facility_id": "eia-123",
        "facets": {
            "permit_status": {
                "state": "promotion_ready",
                "promotion_ready": True,
                "reasons": [],
            }
        }
    }]

    auditor.apply_judgments(audits, None, "kimi-k2.6", 1, 10)

    decision = audits[0]["facets"]["permit_status"]
    assert decision["state"] == "candidate"
    assert decision["promotion_ready"] is False
    assert "judge has not approved" in decision["reasons"][0]


def test_repair_queue_only_contains_research_actions():
    audit = {
        "facility_id": "eia-123",
        "facility_name": "Example Solar Plant",
        "record_type": "power_plant",
        "input_fingerprint": "fingerprint",
        "facets": {
            "permit_status": {
                "recommended_action": "research",
                "reasons": ["source did not support the proposed value"],
            },
            "legal_status": {
                "recommended_action": "human_review",
                "reasons": ["negative legal findings require human review"],
            },
        },
    }
    source_row = {"attempts": [{"search_queries": ["Example Solar Plant permit"]}]}

    item = auditor.repair_item(audit, source_row)

    assert item["facets"] == ["permit_status"]
    assert item["prior_search_queries"] == ["Example Solar Plant permit"]


def test_review_queue_contains_human_and_regulatory_actions_only():
    audit = {
        "facility_id": "eia-123",
        "facility_name": "Example Solar Plant",
        "record_type": "power_plant",
        "run_id": "run-1",
        "facets": {
            "legal_status": {
                "recommended_action": "human_review",
                "confidence": "medium",
                "value": "No litigation identified.",
                "reasons": [],
            },
            "air_permit_status": {
                "recommended_action": "regulatory_rule",
                "confidence": "medium",
                "value": "Not applicable.",
                "reasons": [],
            },
            "permit_status": {
                "recommended_action": "research",
                "confidence": "low",
                "value": "Unknown.",
                "reasons": [],
            },
        },
    }

    item = auditor.review_item(audit)

    assert sorted(item["facets"]) == ["air_permit_status", "legal_status"]


def test_research_container_is_a_finite_job():
    runner = (ROOT / "run.py").read_text()
    assert 'research["restart_policy"] = {"Name": "no"}' in runner


def test_audit_merges_latest_facets_into_one_facility():
    rows = [
        {
            "facility_id": "eia-123",
            "facility_name": "Example Solar Plant",
            "pipeline_id": "pipeline-1",
            "run_id": "run-1",
            "input_fingerprint": "original",
            "requested_facets": ["permit_status", "legal_status"],
            "final_result": {"facets": {
                "permit_status": {"value": "Old permit"},
                "legal_status": {"value": "Human review"},
            }},
        },
        {
            "facility_id": "eia-123",
            "facility_name": "Example Solar Plant",
            "pipeline_id": "pipeline-1",
            "run_id": "run-2",
            "input_fingerprint": "repair",
            "requested_facets": ["permit_status"],
            "final_result": {"facets": {"permit_status": {"value": "New permit"}}},
        },
    ]

    selected, pipeline_id = auditor.select_records(rows, None, None)

    assert pipeline_id == "pipeline-1"
    assert len(selected) == 1
    assert selected[0]["final_result"]["facets"]["permit_status"]["value"] == "New permit"
    assert selected[0]["final_result"]["facets"]["legal_status"]["value"] == "Human review"
    assert selected[0]["_facet_origins"]["permit_status"]["input_fingerprint"] == "repair"
    assert selected[0]["_facet_origins"]["legal_status"]["input_fingerprint"] == "original"
