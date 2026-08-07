import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "datacenters" / "data"


def load(name):
    return json.loads((DATA / name).read_text())


def test_data_files_are_flat_arrays_with_unique_ids():
    for name in (
        "datacenters.json",
        "power-plants.json",
        "residential-electricity-rates.json",
        "sources.json",
    ):
        records = load(name)
        assert isinstance(records, list)
        assert all(isinstance(record, dict) for record in records)
        ids = [record["id"] for record in records]
        assert len(ids) == len(set(ids))


def test_datacenters_share_a_complete_flat_schema():
    records = load("datacenters.json")
    assert len(records) >= 10
    expected = set(records[0])
    for record in records:
        assert set(record) == expected
        assert record["record_type"] == "data_center"
        assert 37.8 <= record["latitude"] <= 39.8
        assert -79.6 <= record["longitude"] <= -75.0
        assert record["state"] == "MD"
        assert record["public_sentiment_score"] in (-2, -1, 0, 1, 2, None)
        assert record["sentiment_confidence"] in ("high", "medium", "low", "insufficient")
        if record["public_sentiment_score"] is None:
            assert record["public_sentiment_label"] == "insufficient evidence"


def test_source_references_and_archived_file_hashes_resolve():
    sources = load("sources.json")
    required = {
        "id", "title", "publisher", "document_date", "retrieved_date", "url",
        "local_path", "local_sha256", "source_tier", "used_for",
    }
    assert all(required <= set(source) for source in sources)
    source_by_id = {source["id"]: source for source in sources}
    for record in load("datacenters.json"):
        assert record["source_ids"]
        assert set(record["source_ids"]) <= set(source_by_id)
        assert set(record["sentiment_source_ids"]) <= set(source_by_id)
        if record["public_sentiment_score"] is not None:
            assert record["sentiment_source_ids"]
    for plant in load("power-plants.json"):
        assert plant["capacity_source_id"] in source_by_id
        assert plant["generation_source_id"] in source_by_id
    for rate in load("residential-electricity-rates.json"):
        assert rate["source_id"] in source_by_id

    for source in sources:
        if not source.get("local_path"):
            continue
        path = ROOT / source["local_path"].lstrip("/")
        assert path.is_file()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == source["local_sha256"]


def test_capacity_is_not_presented_as_reported_grid_demand():
    for record in load("datacenters.json"):
        if record["reported_grid_demand_mw"] is not None:
            assert record["reported_grid_demand_mw"] != record["backup_generator_capacity_mw"]


def test_power_plant_coordinates_and_values_are_sane():
    plants = load("power-plants.json")
    assert len(plants) >= 200
    for plant in plants:
        assert plant["record_type"] == "power_plant"
        assert 37.8 <= plant["latitude"] <= 39.8
        assert -79.6 <= plant["longitude"] <= -75.0
        assert plant["nameplate_capacity_mw"] >= 0


def test_projects_page_and_shared_dropdown_have_the_same_order():
    page = (ROOT / "projects.html").read_text()
    script = (ROOT / "js" / "reusableComponents.js").read_text()
    page_links = re.findall(r'class="project-card-link" href="([^"]+)"', page)
    block = re.search(r"const PROJECT_NAV_LINKS = \[(.*?)\];", script, re.S)
    assert block
    nav_links = re.findall(r"href: '([^']+)'", block.group(1))
    assert page_links == nav_links
    assert nav_links[0] == "/datacenters.html"
