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


def test_datacenter_page_is_map_first_with_compact_filter_hierarchy():
    page = (ROOT / "datacenters.html").read_text()
    assert 'class="dc-hero"' not in page
    assert 'class="dc-overview"' not in page
    assert 'class="dc-map-intro"' in page
    assert 'class="dc-filter-bar"' in page
    assert 'class="dc-explorer"' in page
    assert 'class="dc-workspace"' in page
    assert 'class="dc-controls"' in page
    assert 'class="dc-map-panel"' in page
    assert 'class="dc-detail"' in page
    disclosures = re.findall(r'<details class="[^"]*\bdc-disclosure\b[^"]*"[^>]*>', page)
    assert len(disclosures) == 2
    assert all(" open" not in disclosure for disclosure in disclosures)
    assert '<option value="data_center">Data centers</option>' in page
    assert '<option value="power_plant">Power plants</option>' in page
    assert '<option value="all">All infrastructure</option>' in page
    assert 'id="show-datacenters"' not in page
    assert 'id="show-plants"' not in page
    assert 'id="show-enviroscreen" type="checkbox" checked' not in page
    assert 'id="show-parcels" type="checkbox" checked' not in page
    assert "maplibre-gl@5.24.0" in page
    assert "leaflet" not in page.lower()
    assert 'id="map-theme"' in page
    for theme in ("collective", "dark", "fiord", "positron", "bright", "liberty"):
        assert f'<option value="{theme}">' in page


def test_collective_map_theme_scales_road_widths_by_zoom():
    script = (ROOT / "datacenters" / "js" / "datacenters.js").read_text()
    assert "function roadWidth(semantic)" in script
    assert "setPaint(layer, 'line-width', roadWidth(semantic))" in script
    assert "['interpolate', ['exponential', 1.25], ['zoom']" in script
    assert "function roadOpacity(semantic)" in script


def test_power_plant_images_have_complete_provenance_and_fallback_coverage():
    plants = load("power-plants.json")
    images = load("power-plant-images.json")
    plant_ids = {plant["id"] for plant in plants}
    required = {
        "plant_id", "local_path", "source_page_url", "creator",
        "license", "image_kind", "alt",
    }
    assert len({image["plant_id"] for image in images}) == len(images)
    for image in images:
        assert set(image) == required
        assert image["plant_id"] in plant_ids
        assert image["image_kind"] == "verified_site_photograph"
        assert image["source_page_url"].startswith("https://commons.wikimedia.org/")
        path = ROOT / image["local_path"].lstrip("/")
        assert path.is_file()
        assert path.stat().st_size > 10_000

    fallback = ROOT / "datacenters/images/power-plants/fallback/energy-infrastructure-illustration.webp"
    assert fallback.is_file()
    assert fallback.stat().st_size > 10_000
    assert all(plant["latitude"] is not None and plant["longitude"] is not None for plant in plants)


def test_power_plant_markers_preview_on_hover_and_keyboard_focus():
    script = (ROOT / "datacenters" / "js" / "datacenters.js").read_text()
    assert "element.addEventListener('pointerenter'" in script
    assert "element.addEventListener('focus'" in script
    assert "USGSImageryOnly/MapServer" in script
    assert "Coordinate-specific aerial context" in script
    assert "Generated fallback illustration" in script


def test_map_markers_encode_documented_energy_sources_with_gradients():
    page = (ROOT / "datacenters.html").read_text()
    script = (ROOT / "datacenters" / "js" / "datacenters.js").read_text()
    styles = (ROOT / "datacenters" / "css" / "datacenters.css").read_text()
    plant_codes = {
        code
        for plant in load("power-plants.json")
        for code in (plant["generation_fuel_codes"] or plant["energy_source_codes"])
    }

    assert "function markerSourceCodes(record)" in script
    assert "function markerGradient(sourceCodes)" in script
    assert "conic-gradient(from -35deg" in script
    assert "linear-gradient(145deg" in script
    assert "element.style.setProperty('--marker-source-gradient'" in script
    assert all(f"{code}: {{" in script for code in plant_codes)
    assert "onSite.includes('battery')" in script
    assert "/diesel|fuel oil/.test(backup)" in script
    assert "Energy color key" in page
    assert "Data-center colors describe documented on-site or backup generation" in page
    assert "background: var(--marker-source-gradient" in styles


def test_facility_filters_cover_type_lifecycle_energy_and_public_response():
    page = (ROOT / "datacenters.html").read_text()
    script = (ROOT / "datacenters" / "js" / "datacenters.js").read_text()
    for filter_id in ("map-search", "type-filter", "status-filter", "energy-filter", "sentiment-filter"):
        assert f'id="{filter_id}"' in page
    for stage in ("operating", "development", "proposal", "paused"):
        assert f'<option value="{stage}">' in page
    assert "function lifecycleStage(record)" in script
    assert "if (record.record_type === 'power_plant') return 'operating'" in script
    assert "function matchesEnergySource(record, energyFilter)" in script
    assert "if (sentimentFilter === 'supportive'" in script


def test_mde_enviroscreen_is_lazy_and_uses_the_official_score_classes():
    script = (ROOT / "datacenters" / "js" / "datacenters.js").read_text()
    assert "mdgeodata.md.gov/imap/rest/services/Environment/MD_EnviroScreen/FeatureServer/0" in script
    assert "function addEnviroScreenLayers(map, data)" in script
    assert "if (!enviroScreenData)" in script
    assert "'#01856f', 25" in script
    assert "'#81ccbf', 50" in script
    assert "'#dec17e', 75" in script
    assert "'#a6601b'" in script


def test_mdp_sdat_parcels_are_zoom_gated_and_hover_queried():
    script = (ROOT / "datacenters" / "js" / "datacenters.js").read_text()
    assert "PlanningCadastre/MD_ParcelBoundaries/MapServer" in script
    assert "const PARCEL_MIN_ZOOM = 13" in script
    assert "function loadParcelBoundaries(map)" in script
    assert "geometryType: 'esriGeometryEnvelope'" in script
    assert "map.on('moveend', () => loadParcelBoundaries(map))" in script
    assert "type: 'line'" in script
    assert "function scheduleParcelLookup(map, lngLat)" in script
    assert "spatialRel: 'esriSpatialRelIntersects'" in script
    assert "resultRecordCount: '1'" in script
    assert "function renderParcelDetail(properties)" in script
    assert "function renderEnviroScreenDetail(properties)" in script
