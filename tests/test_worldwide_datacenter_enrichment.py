import importlib.util
import sys
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "datacenters" / "prepare_worldwide_datacenter_enrichment.py"
sys.path.insert(0, str(SCRIPT.parent))
SPEC = importlib.util.spec_from_file_location("prepare_worldwide_enrichment", SCRIPT)
prepare = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
sys.modules[SPEC.name] = prepare
SPEC.loader.exec_module(prepare)

PROMOTE_SPEC = importlib.util.spec_from_file_location(
    "promote_worldwide_enrichment",
    SCRIPT.parent / "promote_worldwide_datacenter_enrichment.py",
)
promote = importlib.util.module_from_spec(PROMOTE_SPEC)
assert PROMOTE_SPEC.loader
sys.modules[PROMOTE_SPEC.name] = promote
PROMOTE_SPEC.loader.exec_module(promote)


def test_prepare_prioritizes_identified_osm_records_and_defers_weak_identity():
    payload = {
        "type": "FeatureCollection",
        "metadata": {"inventory": "test", "source_timestamp": "2026-01-01"},
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [-77.0, 39.0]},
                "properties": {
                    "osm_type": "way",
                    "osm_id": 42,
                    "name": "Example Campus",
                    "operator": "Example",
                    "website": "https://example.com/campus",
                    "country_code": "US",
                },
            },
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [-78.0, 40.0]},
                "properties": {"osm_type": "node", "osm_id": 43, "country_code": "US"},
            },
        ],
    }

    records, report = prepare.prepare(payload)

    assert [record["id"] for record in records] == ["osm-way-42"]
    assert records[0]["research_priority"] == 1
    assert records[0]["power_profile"] == "not yet researched"
    assert report["eligible_count"] == 1
    assert report["deferred_reasons"] == {"weak_identity": 1}


def test_overlay_promotion_requires_audited_supported_source_and_osm_identity():
    url = "https://agency.example.gov/facility"
    base = {
        "type": "FeatureCollection",
        "metadata": {"inventory": "test", "source_timestamp": "2026-01-01"},
        "features": [{
            "geometry": {"type": "Point", "coordinates": [0, 0]},
            "properties": {"osm_type": "way", "osm_id": 42},
        }],
    }
    audit = {
        "facility_id": "osm-way-42",
        "run_id": "run-1",
        "pipeline_id": "pipeline-1",
        "facets": {"power_profile": {
            "promotion_ready": True,
            "confidence": "high",
            "value": "Published 24 MW capacity envelope.",
            "basis": "Facility-specific agency record.",
            "fields": {"reported_power_capacity_mw": 24, "value_scope": "facility"},
            "field_evidence": {"reported_power_capacity_mw": [url]},
            "judge": {"supported_urls": [url]},
            "sources": [{
                "url": url,
                "final_url": url,
                "title": "Facility decision",
                "publisher": "Agency",
                "source_class": "government",
                "content_sha256": "abc",
                "usable": True,
            }],
        }},
    }

    overlay = promote.candidate_overlay([audit], base)

    assert overlay["record_count"] == 1
    assert overlay["records"][0]["power_profile"]["reported_power_capacity_mw"] == 24
    audit["facets"]["power_profile"]["judge"]["supported_urls"] = []
    assert promote.candidate_overlay([audit], base)["record_count"] == 0
