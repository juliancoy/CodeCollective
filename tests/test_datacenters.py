import hashlib
import base64
import json
import math
import re
import struct
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "datacenters" / "data"


def load(name):
    return json.loads((DATA / name).read_text())


def infrastructure(record_type=None):
    records = load("infrastructure.json")
    if record_type is None:
        return records
    return [record for record in records if record["record_type"] == record_type]


def test_data_files_are_flat_arrays_with_unique_ids():
    for name in (
        "infrastructure.json",
        "residential-electricity-rates.json",
        "sources.json",
    ):
        records = load(name)
        assert isinstance(records, list)
        assert all(isinstance(record, dict) for record in records)
        ids = [record["id"] for record in records]
        assert len(ids) == len(set(ids))


def test_datacenters_share_a_complete_flat_schema():
    records = infrastructure("data_center")
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


def test_data_center_contestation_is_ranked_and_source_backed():
    centers = infrastructure("data_center")
    source_ids = {source["id"] for source in load("sources.json")}
    required = {
        "contestation_score", "contestation_label", "contestation_category",
        "contestation_basis", "contestation_source_ids", "salient_news_source_ids",
        "contestation_assessed_date",
    }
    for record in centers:
        assert required <= set(record), record["id"]
        assert record["contestation_score"] in range(5)
        assert record["contestation_basis"]
        assert record["contestation_assessed_date"] == "2026-08-09"
        assert set(record["contestation_source_ids"]) <= source_ids
        assert set(record["salient_news_source_ids"]) <= source_ids
        assert set(record["salient_news_source_ids"]) <= set(record["contestation_source_ids"])

    by_id = {record["id"]: record for record in centers}
    assert by_id["brightseat-tech-park-landover"]["contestation_score"] == 4
    assert by_id["atmosphere-dickerson"]["contestation_score"] == 4
    assert by_id["amazon-bwi150-153-frederick"]["contestation_score"] == 4
    assert by_id["aligned-iad04-frederick"]["contestation_score"] == 3
    assert by_id["ainet-beltsville"]["contestation_category"] == "operator and federal-contract legal allegation"
    assert "allegations, not a conviction" in by_id["ainet-beltsville"]["contestation_basis"]
    assert by_id["cogent-elkridge"]["contestation_score"] == 0


def test_hover_inspector_prominently_links_salient_contestation_coverage():
    script = (ROOT / "datacenters" / "js" / "datacenters.js").read_text()
    styles = (ROOT / "datacenters" / "css" / "datacenters.css").read_text()
    assert "function renderContestationSpotlight(record, sourceById)" in script
    assert "${renderContestationSpotlight(record, sourceById)}" in script
    assert 'class="dc-salient-news-link"' in script
    assert "record.salient_news_source_ids" in script
    assert "Contestation: ${record.contestation_label}" in script
    assert ".dc-contestation" in styles
    assert ".dc-salient-news-link" in styles


def test_infrastructure_is_one_flat_tagged_inventory():
    records = infrastructure()
    assert len(records) == 238
    assert {record["record_type"] for record in records} == {"data_center", "power_plant"}
    assert len(infrastructure("data_center")) == 29
    assert len(infrastructure("power_plant")) == 209
    assert all(record["technology_tags"] for record in records)
    assert all(len(tags := record["technology_tags"]) == len(set(tags)) for record in records)
    assert not (DATA / "datacenters.json").exists()
    assert not (DATA / "power-plants.json").exists()

    by_id = {record["id"]: record for record in records}
    assert by_id["eia-65945"]["technology_tags"] == [
        "Natural Gas Internal Combustion Engine",
        "Solar Photovoltaic",
        "Batteries",
    ]
    assert by_id["eia-58207"]["technology_tags"] == [
        "Natural Gas Fired Combined Cycle",
        "Natural Gas Fired Combustion Turbine",
        "Petroleum Liquids",
        "Natural Gas Internal Combustion Engine",
    ]


def test_datacentermap_baltimore_directory_listings_are_covered():
    by_id = {record["id"]: record for record in infrastructure("data_center")}
    expected_ids = {
        "ainet-one-market-center-baltimore",
        "tierpoint-baltimore-bal",
        "tierpoint-baltimore-bwi",
        "expedient-owings-mills",
        "cogent-elkridge",
        "expedient-tide-point",
        "ainet-cybernap-glen-burnie",
        "databank-bwi1-baltimore",
        "crown-castle-baltimore",
        "databank-111-market-place",
        "infradms-bal01-baltimore",
        "amazon-cronridge-owings-mills",
        "woodlawn-drive-1500-proposal",
        "comcast-nottingham",
        "gi-partners-eternal-rings-laurel",
        "gi-partners-sandy-farm-severn",
        "lumen-baltimore",
        "candler-building-baltimore",
    }
    assert expected_ids <= set(by_id)
    for record_id in expected_ids:
        record = by_id[record_id]
        assert record["estimated_power_draw_mw"] is not None
        assert record["estimated_power_draw_basis"]
    assert by_id["infradms-bal01-baltimore"]["reported_power_capacity_mw"] == 0.65
    assert by_id["woodlawn-drive-1500-proposal"]["reported_power_capacity_mw"] == 150
    assert by_id["databank-111-market-place"]["street_address"] == "111 Market Place"

    for facility_id in (
        "cogent-elkridge",
        "atlantech-rockville",
        "atlantech-silver-spring",
        "ainet-beltsville",
        "ainet-laurel",
        "ainet-cybernap-glen-burnie",
    ):
        assert facility_id in by_id


def test_statewide_colocation_audit_keeps_directory_listings_distinct_from_buildings():
    centers = infrastructure("data_center")
    addresses = [
        (record["street_address"] or "").lower().replace("street", "st").strip()
        for record in centers
    ]
    assert addresses.count("300 west lexington st") == 3
    assert addresses.count("111 market place") == 3
    assert all(
        "retained" in (record.get("notes") or "").lower()
        for record in centers
        if record["id"] in {
            "ainet-one-market-center-baltimore",
            "lumen-baltimore",
            "crown-castle-baltimore",
            "databank-111-market-place",
            "candler-building-baltimore",
        }
    )
    cogent = next(record for record in centers if record["id"] == "cogent-elkridge")
    assert cogent["street_address"] == "6050 Race Road"
    assert cogent["reported_power_capacity_mw"] == 7.5
    assert "Two 250 kVA UPS units" in cogent["ups_technology"]
    assert cogent["backup_generator_capacity_mw"] is None


def test_every_entity_has_source_backed_year_and_status_metadata():
    source_ids = {source["id"] for source in load("sources.json")}
    required = {
        "year_built", "year_built_status", "year_built_basis",
        "development_status", "permit_status", "air_permit_status", "legal_status",
        "status_tags", "year_built_source_ids", "status_source_ids",
    }
    for record in infrastructure():
        assert required <= set(record), record["id"]
        assert record["year_built_status"] in {"documented", "not built", "unknown"}
        assert record["year_built_basis"]
        assert record["development_status"]
        assert record["permit_status"]
        assert record["air_permit_status"]
        assert record["legal_status"]
        assert record["status_tags"]
        assert set(record["year_built_source_ids"]) <= source_ids
        assert set(record["status_source_ids"]) <= source_ids


def test_data_center_years_distinguish_structures_from_unbuilt_projects():
    by_id = {record["id"]: record for record in infrastructure("data_center")}
    assert by_id["annapolis-state-data-center"]["year_built"] == 1988
    assert by_id["tierpoint-baltimore-bal"]["year_built"] == 1955
    assert by_id["amazon-bwi150-153-frederick"]["year_built"] == 2025
    assert by_id["amazon-bwi150-153-frederick"]["development_status"] == "under development / not operating"
    assert by_id["databank-bwi1-baltimore"]["year_built_status"] == "unknown"
    for record_id in (
        "aligned-iad04-frederick",
        "atmosphere-dickerson",
        "brightseat-tech-park-landover",
        "jhu-bayview-research-data-center",
    ):
        assert by_id[record_id]["year_built"] is None
        assert by_id[record_id]["year_built_status"] == "not built"


def test_data_center_power_scale_uses_demand_then_capacity_without_backup_inference():
    centers = infrastructure("data_center")
    source_ids = {source["id"] for source in load("sources.json")}
    required = {
        "power_scale_class", "power_scale_label", "power_scale_mw",
        "power_scale_value_kind", "power_scale_detail", "power_scale_tag",
        "power_scale_source_ids", "estimated_power_draw_mw",
        "estimated_power_draw_basis", "estimated_power_draw_confidence",
        "estimated_power_draw_source_ids",
        "projected_power_demand_mw", "projected_power_demand_basis",
        "projected_power_demand_confidence", "projected_power_demand_source_ids",
    }
    for record in centers:
        assert required <= set(record), record["id"]
        assert record["power_scale_class"] in {
            "sub-megawatt", "small", "medium", "large", "very-large", "unknown"
        }
        assert record["estimated_power_draw_mw"] is not None, record["id"]
        assert record["estimated_power_draw_mw"] > 0, record["id"]
        assert record["estimated_power_draw_basis"], record["id"]
        assert record["estimated_power_draw_confidence"] in {"high", "medium", "low"}
        assert set(record["estimated_power_draw_source_ids"]) <= source_ids
        assert record["power_scale_detail"]
        assert record["power_scale_tag"]
        assert set(record["power_scale_source_ids"]) <= source_ids
        if record["reported_grid_demand_mw"] is not None:
            assert record["power_scale_value_kind"] == "reported grid demand"
            assert record["power_scale_mw"] == record["reported_grid_demand_mw"]
        elif record["estimated_power_draw_mw"] is not None:
            assert record["power_scale_value_kind"] == "estimated grid demand"
            assert record["power_scale_mw"] == record["estimated_power_draw_mw"]
        else:
            assert record["power_scale_value_kind"] == "reported power-capacity proxy"
            assert record["power_scale_mw"] == record["reported_power_capacity_mw"]
            assert "not measured operating draw" in record["power_scale_detail"]

    by_id = {record["id"]: record for record in centers}
    assert by_id["databank-bwi1-baltimore"]["power_scale_class"] == "sub-megawatt"
    assert by_id["expedient-tide-point"]["power_scale_class"] == "small"
    assert by_id["cogent-elkridge"]["power_scale_class"] == "medium"
    assert by_id["ainet-cybernap-glen-burnie"]["power_scale_class"] == "large"
    assert by_id["aligned-iad04-frederick"]["power_scale_class"] == "very-large"
    assert by_id["aligned-iad04-frederick"]["power_scale_mw"] == 300
    assert by_id["aligned-iad04-frederick"]["backup_generator_capacity_mw"] == 508

    projected = {
        record["id"]: record["projected_power_demand_mw"]
        for record in centers
        if record["projected_power_demand_mw"] is not None
    }
    assert projected == {
        "aligned-iad04-frederick": 300,
        "amazon-bwi150-153-frederick": 160,
        "atmosphere-dickerson": 360,
        "brightseat-tech-park-landover": 300,
        "jhu-bayview-research-data-center": 5,
        "woodlawn-drive-1500-proposal": 150,
        "woodlawn-drive-1500-proposal": 150,
    }
    assert all(
        record["projected_power_demand_mw"] is None
        for record in centers
        if record["status"] == "operating"
    )


def test_power_plant_year_and_status_come_from_final_eia_860():
    plants = infrastructure("power_plant")
    assert all(isinstance(plant["year_built"], int) for plant in plants)
    assert min(plant["year_built"] for plant in plants) == 1925
    assert max(plant["year_built"] for plant in plants) == 2024
    by_id = {plant["id"]: plant for plant in plants}
    assert by_id["eia-1563"]["generator_status_codes"] == ["SB"]
    assert by_id["eia-1563"]["development_status"] == "standby / backup"
    assert by_id["eia-50060"]["generator_status_codes"] == ["OA"]
    assert by_id["eia-59026"]["generator_status_codes"] == ["OP", "OS"]


def test_browser_fetches_only_the_unified_infrastructure_inventory():
    page = (ROOT / "datacenters.html").read_text()
    script = (ROOT / "datacenters" / "js" / "datacenters.js").read_text()
    assert "infrastructure: '/datacenters/data/infrastructure.json'" in script
    assert "const allRecords = data.infrastructure.map" in script
    assert "record.technology_tags" in script
    assert "/datacenters/data/datacenters.json" not in page + script
    assert "/datacenters/data/power-plants.json" not in page + script
    assert "window.__codeCollectiveDatacenterUiReady = true" in script


def test_eia_generator_retains_every_generator_technology():
    generator = (ROOT / "datacenters" / "generate_datacenter_energy_data.py").read_text()
    assert '"technology_tags": [str(value) for value in technology_capacity.index]' in generator
    assert 'rows["Operating Year"]' in generator
    assert 'rows["Status"]' in generator
    assert '"generator_status_codes": status_codes' in generator
    assert "infrastructure = load_data_centers(args.output) + records" in generator
    assert "def classify_data_center_power(record):" in generator
    assert "def apply_estimated_power_draw(record):" in generator
    assert "def apply_projected_power_demand(record):" in generator
    assert 'any(term in status for term in ("development", "proposed", "concept", "planned"))' in generator
    assert 'record.get("estimated_power_draw_mw")' in generator
    assert 'record.get("reported_grid_demand_mw")' in generator
    assert 'record.get("reported_power_capacity_mw")' in generator
    assert '"power_scale_value_kind": value_kind' in generator


def test_entity_photographs_render_above_live_usgs_aerials_when_associated():
    page = (ROOT / "datacenters.html").read_text()
    script = (ROOT / "datacenters" / "js" / "datacenters.js").read_text()
    assert "/datacenters/data/datacenter-images.json" not in page
    assert "entityImages: '/datacenters/data/power-plant-images.json'" in script
    assert "const entityImageByRecordId = new Map" in script
    assert "entity_image: record.entity_image || entityImageByRecordId.get(record.id) || null" in script
    assert "function renderDatacenterImage(record)" in script
    assert "${renderDatacenterImage(record)}" in script
    assert "function renderEntityImage(record)" in script
    assert "return renderEntityImage(record) + renderSiteAnimation(record)" in script
    assert 'class="dc-entity-image"' in script
    assert "Entity photograph" in script
    assert "Image source" in script
    assert 'data-live-aerial-url="${escapeHtml(liveUrl)}"' in script
    assert "function hydrateLiveAerialImage(detail, image, record)" in script
    assert "hydrateLiveAerialImage(detail, animation.querySelector" in script
    assert "caches.open(AERIAL_IMAGE_CACHE)" in script
    assert "await cache.match(url)" in script
    assert "fetch(url, { cache: 'no-store', mode: 'cors' })" in script
    assert "cache.put(url, cacheCopy)" in script
    assert "Cached aerial context" in script
    assert "Fresh USGS aerial context" in script
    assert "image.classList.add('is-aerial-ready')" in script
    assert "image.closest('.dc-entity-image')?.remove()" in script
    assert "size: `${AERIAL_IMAGE_WIDTH},${AERIAL_IMAGE_HEIGHT}`" in script
    assert not (ROOT / "datacenters" / "data" / "datacenter-images.json").exists()
    assert not (ROOT / "datacenters" / "images" / "datacenters" / "aerial").exists()
    assert ".dc-entity-image" in (ROOT / "datacenters" / "css" / "datacenters.css").read_text()


def test_hover_inspector_keeps_one_animated_aerial_without_switching_displays():
    script = (ROOT / "datacenters" / "js" / "datacenters.js").read_text()
    styles = (ROOT / "datacenters" / "css" / "datacenters.css").read_text()
    assert "function renderSiteAnimation(record)" in script
    assert script.count('data-live-aerial-url="${escapeHtml(liveUrl)}"') == 1
    assert 'data-site-animation aria-label="Animated aerial view"' in script
    assert "function setupInspectorAnimation(detail, record)" in script
    assert "data-gallery-previous" not in script
    assert "data-gallery-next" not in script
    assert "setInterval(() => activate" not in script
    assert "function initializeInspectorBuildingModel" not in script
    assert 'data-gallery-kind="model"' not in script
    assert ".dc-gallery-controls" not in styles
    assert ".dc-building-mockup" not in styles
    assert "prefers-reduced-motion: reduce" in styles
    assert "animation: dc-aerial-push-in var(--dc-aerial-duration, 18s) ease-in-out infinite alternate" in styles
    assert "@keyframes dc-aerial-push-in" in styles
    assert "--dc-aerial-zoom, 2" in styles


def test_hover_animation_outlines_the_live_mdp_sdat_parcel_geometry():
    script = (ROOT / "datacenters" / "js" / "datacenters.js").read_text()
    styles = (ROOT / "datacenters" / "css" / "datacenters.css").read_text()
    assert 'data-parcel-outline viewBox="0 0 ${AERIAL_IMAGE_WIDTH} ${AERIAL_IMAGE_HEIGHT}"' in script
    assert "function aerialBoundsForRecord(record)" in script
    assert "function parcelGeometryPath(geometry, bounds)" in script
    assert "function parcelGeometryBounds(geometry)" in script
    assert "function hydrateInspectorParcelOutline(detail, animation, record)" in script
    assert "spatialRel: 'esriSpatialRelIntersects'" in script
    assert "outFields: 'ACCTID,ADDRESS,ACRES,DESCLU'" in script
    assert "fetch(`${PARCEL_SERVICE}/0/query?${parameters}`" in script
    assert "initialAerial.then(() => scheduleInspectorParcelOutline(detail, animation, record))" in script
    assert "function scheduleInspectorParcelOutline(detail, animation, record)" in script
    assert "window.requestIdleCallback(hydrate, { timeout: 2500 })" in script
    assert "window.setTimeout(hydrate, 0)" in script
    assert "if (!detail.contains(animation)) return" in script
    assert "path.setAttribute('d', parcelGeometryPath(feature.geometry, parcelBounds))" in script
    assert "image.dataset.liveAerialUrl = usgsAerialImageUrlForBounds(parcelBounds)" in script
    assert "Aerial extent matches the exact MDP/SDAT parcel bounding box" in script
    assert ".dc-parcel-outline path" in styles
    assert "stroke: #ffd582" in styles
    assert ".dc-parcel-outline-status" in styles


def test_aerial_animation_gear_controls_speed_distance_and_persists_settings():
    script = (ROOT / "datacenters" / "js" / "datacenters.js").read_text()
    styles = (ROOT / "datacenters" / "css" / "datacenters.css").read_text()
    assert 'class="dc-aerial-settings"' in script
    assert 'summary aria-label="Adjust aerial animation"' in script
    assert "data-aerial-speed" in script
    assert "data-aerial-distance" in script
    assert "function normalizeAerialAnimationSettings(settings = {})" in script
    assert 'data-aerial-speed type="range" min="0.025" max="10" step="0.025"' in script
    assert 'data-aerial-distance type="range" min="0.025" max="2" step="0.025"' in script
    assert "Math.min(10, Math.max(.025" in script
    assert "Math.min(2, Math.max(.025" in script
    assert "gallery.style.setProperty('--dc-aerial-zoom', String(1 + distance))" in script
    assert "function setupAerialAnimationControls(gallery)" in script
    assert "gallery.style.setProperty('--dc-aerial-duration'" in script
    assert "gallery.style.setProperty('--dc-aerial-zoom'" in script
    assert "parameters.has('animation')" in script
    assert "url.searchParams.set('animation'" in script
    assert ".dc-aerial-settings" in styles
    assert "top: .42rem" in styles and "right: .42rem" in styles


def test_source_references_and_archived_file_hashes_resolve():
    sources = load("sources.json")
    required = {
        "id", "title", "publisher", "document_date", "retrieved_date", "url",
        "local_path", "local_sha256", "source_tier", "used_for",
    }
    assert all(required <= set(source) for source in sources)
    source_by_id = {source["id"]: source for source in sources}
    for record in infrastructure("data_center"):
        assert record["source_ids"]
        assert set(record["source_ids"]) <= set(source_by_id)
        assert set(record["sentiment_source_ids"]) <= set(source_by_id)
        assert set(record["year_built_source_ids"]) <= set(source_by_id)
        assert set(record["status_source_ids"]) <= set(source_by_id)
        assert set(record["power_scale_source_ids"]) <= set(source_by_id)
        assert set(record["estimated_power_draw_source_ids"]) <= set(source_by_id)
        if record["public_sentiment_score"] is not None:
            assert record["sentiment_source_ids"]
    for plant in infrastructure("power_plant"):
        assert plant["capacity_source_id"] in source_by_id
        assert plant["generation_source_id"] in source_by_id
        assert plant["planning_output_source_id"] in source_by_id
        assert set(plant["year_built_source_ids"]) <= set(source_by_id)
        assert set(plant["status_source_ids"]) <= set(source_by_id)
    for rate in load("residential-electricity-rates.json"):
        assert rate["source_id"] in source_by_id

    for source in sources:
        if not source.get("local_path"):
            continue
        path = ROOT / source["local_path"].lstrip("/")
        assert path.is_file()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == source["local_sha256"]


def test_capacity_is_not_presented_as_reported_grid_demand():
    for record in infrastructure("data_center"):
        if record["reported_grid_demand_mw"] is not None:
            assert record["reported_grid_demand_mw"] != record["backup_generator_capacity_mw"]


def test_power_plant_coordinates_and_values_are_sane():
    plants = infrastructure("power_plant")
    assert len(plants) >= 200
    coordinate_counts = {}
    for plant in plants:
        assert plant["record_type"] == "power_plant"
        assert 37.8 <= plant["latitude"] <= 39.8
        assert -79.6 <= plant["longitude"] <= -75.0
        assert plant["nameplate_capacity_mw"] >= 0
        assert "planning_sustained_output_mw" in plant
        assert "annual_capacity_factor" in plant
        assert "planning_output_basis" in plant
        assert "planning_output_source_id" in plant
        assert plant["planning_output_basis"]
        if plant["planning_sustained_output_mw"] is not None:
            assert 0 <= plant["planning_sustained_output_mw"] <= plant["nameplate_capacity_mw"]
            assert 0 <= plant["annual_capacity_factor"] <= 1
            assert math.isclose(
                plant["annual_capacity_factor"],
                plant["planning_sustained_output_mw"] / plant["nameplate_capacity_mw"],
                rel_tol=0.02,
                abs_tol=0.001,
            )
        assert plant["coordinate_confidence"] in {"high", "medium", "low"}
        assert plant["coordinate_confidence_basis"]
        assert plant["latitude_decimal_places"] >= 0
        assert plant["longitude_decimal_places"] >= 0
        assert plant["shared_coordinate_count"] >= 1
        assert (plant["aerial_frame_width_m"], plant["aerial_frame_height_m"]) in {
            (700, 650),
            (2750, 2000),
        }
        coordinate = (plant["latitude"], plant["longitude"])
        coordinate_counts[coordinate] = coordinate_counts.get(coordinate, 0) + 1

    shared_groups = {coordinate: count for coordinate, count in coordinate_counts.items() if count > 1}
    assert len(shared_groups) == 6
    assert sum(shared_groups.values()) == 17
    assert sum(plant["aerial_frame_width_m"] == 700 for plant in plants) == 165
    assert sum(plant["aerial_frame_width_m"] == 2750 for plant in plants) == 44
    for plant in plants:
        assert plant["shared_coordinate_count"] == coordinate_counts[(plant["latitude"], plant["longitude"])]
        if plant["shared_coordinate_count"] > 1:
            assert plant["coordinate_confidence"] == "low"


def test_power_plant_planning_output_is_distinct_from_nameplate_capacity():
    plants = {plant["id"]: plant for plant in infrastructure("power_plant")}
    calvert = plants["eia-6011"]
    brandon = plants["eia-602"]
    assert calvert["nameplate_capacity_mw"] > calvert["planning_sustained_output_mw"]
    assert brandon["nameplate_capacity_mw"] > brandon["planning_sustained_output_mw"]
    assert "8,760 hours" in calvert["planning_output_basis"]
    assert "not a peak, dispatchable, accredited, or reliability-capacity rating" in calvert["planning_output_basis"]


def test_power_plant_aerial_imagery_uses_adaptive_meter_frames():
    script = (ROOT / "datacenters" / "js" / "datacenters.js").read_text()

    assert "function aerialFrameForRecord(record)" in script
    assert "record.aerial_frame_width_m" in script
    assert "record.aerial_frame_height_m" in script
    assert "metersPerLongitudeDegree" in script
    assert "coordinate_confidence_basis" in script
    assert "× ${number(dimensions.heightMeters)} m provisional frame" in script
    assert "function aerialDimensionsForRecord(record)" in script
    assert "function usgsAerialImageUrl(record)" in script
    assert "widthMeters: frame.widthMeters * 1.8" in script
    assert "Detail aerial" not in script
    assert "const halfLongitude = .016" not in script
    assert "const halfLatitude = .009" not in script


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
    assert 'class="dc-filter-bar"' not in page
    assert 'id="layer-search"' in page
    assert "Facility, operator, county" not in page
    assert "No layer-specific filters applied" not in page
    assert "Reset layer filters" not in page
    assert 'class="dc-explorer"' in page
    assert 'class="dc-workspace"' in page
    assert 'class="dc-controls"' in page
    assert 'class="dc-map-panel"' in page
    assert 'class="dc-detail"' in page
    disclosures = re.findall(r'<details class="[^"]*\bdc-disclosure\b[^"]*"[^>]*>', page)
    assert len(disclosures) == 2
    assert all(" open" not in disclosure for disclosure in disclosures)
    assert 'id="type-filter"' not in page
    assert 'id="result-list"' not in page
    assert 'id="show-datacenters" type="checkbox" checked' in page
    assert 'id="show-power-plants" type="checkbox" checked' in page
    assert 'id="show-enviroscreen" type="checkbox" checked' in page
    assert 'id="show-parcels" type="checkbox" checked' in page
    assert 'class="dc-layer-gear"' in page
    assert 'id="layer-filter-modal"' in page
    assert "maplibre-gl@5.24.0" in page
    assert "deck.gl@9.2.11" in page
    assert "@loaders.gl/i3s@4.3.4" in page
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


def test_neon_streets_default_to_i95_and_restore_the_regular_road_map_when_disabled():
    page = (ROOT / "datacenters.html").read_text()
    script = (ROOT / "datacenters" / "js" / "datacenters.js").read_text()

    assert 'id="show-neon-streets" type="checkbox" checked' in page
    assert 'id="hover-neon-streets" type="checkbox" checked' in page
    assert 'data-layer-config="neon-streets"' in page
    assert "neonStreets: { scope: 'i95', lineWidth: 1 }" in script
    assert "['==', ['get', 'network'], 'us-interstate'], ['==', ['get', 'ref'], '95']" in script
    assert "id: NEON_STREET_GLOW_LAYER_ID" in script
    assert "'line-blur': ['interpolate'" in script
    assert "id: NEON_STREET_CORE_LAYER_ID" in script
    assert "id: NEON_STREET_LABEL_LAYER_ID" in script
    assert "streetBaseVisible && !enabled ? 'visible' : 'none'" in script
    assert "['i95', 'I-95 only']" in script
    assert "['all', 'All streets']" in script
    assert "neonStreets: { ...layerFilters.neonStreets }" in script


def test_street_and_imagery_base_layers_are_independent_persisted_controls():
    page = (ROOT / "datacenters.html").read_text()
    script = (ROOT / "datacenters" / "js" / "datacenters.js").read_text()
    styles = (ROOT / "datacenters" / "css" / "datacenters.css").read_text()

    assert 'id="show-street-map" class="dc-base-layer-toggle" type="checkbox" checked' in page
    for layer_id in ("md-six-inch-imagery", "esri-world-imagery", "usgs-imagery"):
        assert f'id="show-{layer_id}" class="dc-base-layer-toggle" type="checkbox"' in page
        assert f"id: '{layer_id}'" in script
    assert "SixInch/SixInchImagery/MapServer/export?bbox={bbox-epsg-3857}" in script
    assert "World_Imagery/MapServer/tile/{z}/{y}/{x}" in script
    assert "`${USGS_IMAGERY_SOURCE}/tile/{z}/{y}/{x}`" in script
    assert "function applyBaseLayerState(map)" in script
    assert "classList.toggle('dc-map--no-base', activeId === null)" in script
    assert "function ensureMapFallbackBackground(map)" in script
    assert "id: MAP_FALLBACK_BACKGROUND_LAYER_ID" in script
    assert "'background-color': '#002a61'" in script
    assert "activeId === 'street-map' ? 'none' : 'visible'" in script
    assert "#datacenter-map.dc-map--no-base" in styles
    assert "function setupBaseLayerControls(map)" in script
    assert "streetStyleLayerIds" in script
    assert "url.searchParams.set('base', state.baseLayer)" in script
    assert "parameters.has('base')" in script


def test_map_download_exports_a_high_resolution_attributed_png():
    page = (ROOT / "datacenters.html").read_text()
    script = (ROOT / "datacenters" / "js" / "datacenters.js").read_text()
    assert 'id="download-map-png"' in page
    assert 'id="map-download-status"' in page
    assert 'id="map-title-input"' in page
    assert 'id="show-map-title"' in page
    assert "function downloadMapPng(map)" in script
    assert "pixelRatio: Math.max(window.devicePixelRatio || 1, 3)" in script
    assert "antialias: true" in script
    assert "preserveDrawingBuffer: true" in script
    assert "context.drawImage(source, 0, 0)" in script
    assert "function drawExportDataCenterMarkers(map, context, scaleX, scaleY)" in script
    assert "function drawExportPowerPlantMarkers(map, context, scaleX, scaleY)" in script
    assert "function drawExportMapTitle(context, title, scaleX, scaleY)" in script
    assert "getExportEntries()" in script
    assert "dataCenterMarkerCount" in script
    assert "powerPlantMarkerCount" in script
    assert "maplibregl-ctrl-attrib" in script
    assert "output.toBlob" in script
    assert "maryland-infrastructure-map-z${map.getZoom().toFixed(2)}.png" in script


def test_map_title_overlay_is_editable_optional_and_persisted():
    script = (ROOT / "datacenters" / "js" / "datacenters.js").read_text()
    styles = (ROOT / "datacenters" / "css" / "datacenters.css").read_text()
    assert "function setupMapTitleControls(map)" in script
    assert "overlay.className = 'dc-rendered-map-title'" in script
    assert "overlay.hidden = !checkbox.checked" in script
    assert "state.mapTitle" in script
    assert "state.showMapTitle" in script
    assert ":not(#show-map-title)" in script
    assert "input.id !== 'show-map-title'" in script
    assert "url.searchParams.set('mapTitle', state.mapTitle)" in script
    assert "url.searchParams.set('showTitle', state.showMapTitle ? '1' : '0')" in script
    assert ".dc-rendered-map-title" in styles


def test_power_plant_images_have_complete_provenance_and_fallback_coverage():
    plants = infrastructure("power_plant")
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
    page = (ROOT / "datacenters.html").read_text()
    script = (ROOT / "datacenters" / "js" / "datacenters.js").read_text()
    for layer in ("datacenters", "power-plants", "enviroscreen", "parcels"):
        assert f'id="hover-{layer}" type="checkbox" checked' in page
    assert "map.on('mousemove', (event) => handleMapHover" in script
    assert "powerPlantBoltLayer?.hitTest(point)" in script
    assert "function showHoverTarget(map, target)" in script
    assert "document.getElementById('hover-power-plants').checked" in script
    assert "document.getElementById('hover-enviroscreen').checked" in script
    assert "document.getElementById('hover-parcels').checked" in script
    assert "element.addEventListener('focus'" in script
    assert "element.title =" not in script
    assert "USGSImageryOnly/MapServer" in script
    assert "Cached aerial context" in script
    assert "Fresh USGS aerial context" in script
    assert "Generated fallback illustration" in script


def test_hover_heading_renders_all_record_tags_as_bubbles():
    script = (ROOT / "datacenters" / "js" / "datacenters.js").read_text()
    styles = (ROOT / "datacenters" / "css" / "datacenters.css").read_text()
    assert "title: `${category} - ${colorMeaning}`" not in script
    assert "...(record.technology_tags || []).map" in script
    assert "function recordYearBuiltTag(record)" in script
    assert "...(record.status_tags || []).map" in script
    assert "record.power_scale_tag" in script
    assert "function powerScaleTagColor(record)" in script


def test_data_center_power_scale_is_filterable_and_explained_in_inspector():
    script = (ROOT / "datacenters" / "js" / "datacenters.js").read_text()
    styles = (ROOT / "datacenters" / "css" / "datacenters.css").read_text()
    plan = (ROOT / "datacentersplan.md").read_text()

    assert "powerScale: 'all'" in script
    assert "powerScale: [" in script
    assert "Power scale', 'powerScale'" in script
    assert "record.power_scale_class !== powerScaleFilter" in script
    assert "['Power class'" in script
    assert "['Classification basis', known(record.power_scale_detail)]" in script
    assert "record.power_scale_source_ids" in script
    assert "Never present a backup-generator-derived estimate as measured operating load." in plan
    assert "...colorPalette.map" in script
    assert "...outlinePalette.map" in script
    assert 'class="dc-hover-tags" aria-label="Record tags"' in script
    assert 'class="dc-hover-tag"' in script
    assert ".dc-hover-tags" in styles
    assert ".dc-hover-tag" in styles
    assert "border-radius: 999px" in styles


def test_hover_tag_bubbles_split_slashes_and_the_word_and():
    script = (ROOT / "datacenters" / "js" / "datacenters.js").read_text()
    assert "function splitTagLabel(label)" in script
    assert ".split(/\\s*(?:\\/|\\band\\b)\\s*/i)" in script
    assert ".flatMap((tag) => splitTagLabel(tag.label)" in script


def test_hover_arbitration_selects_one_target_by_rendered_layer_z_order():
    script = (ROOT / "datacenters" / "js" / "datacenters.js").read_text()

    assert "function topMapHoverTarget(map, point, sourceById)" in script
    assert "function layerZIndex(layerId)" in script
    assert "z: layerZIndex(deckHoverTarget.layerId)" in script
    assert "const z = layerZIndex('datacenters')" in script
    assert "const layerZ = layerZIndex('power-plants')" in script
    assert "z: layerZIndex(target.layerId)" in script
    assert "candidates.sort((left, right) => right.z - left.z)" in script
    assert "return candidates[0] || null" in script
    assert "powerPlantBoltLayer?.setHoveredRecord(target?.kind === 'power-plant' ? target.record : null)" in script
    assert "if (target.kind !== 'parcel') clearParcelHighlight(map)" in script
    assert "window.__lastHoverArbitration" in script
    assert "const dataCenter = topDataCenterHoverRecord(map, point)" in script
    assert "document.elementsFromPoint(clientX, clientY)" in script
    assert "Number.MAX_SAFE_INTEGER" not in script.split("function topMapHoverTarget(map, point, sourceById)", 1)[1].split("function topDataCenterHoverRecord", 1)[0]
    assert "layerId: 'datacenters'" in script
    assert "layerId: 'power-plants'" in script
    assert "layerId: 'enviroscreen'" in script
    assert "layerId: config.id" in script


def test_selected_layers_are_drag_ordered_and_persisted_as_z_order():
    page = (ROOT / "datacenters.html").read_text()
    script = (ROOT / "datacenters" / "js" / "datacenters.js").read_text()
    styles = (ROOT / "datacenters" / "css" / "datacenters.css").read_text()

    assert 'id="selected-layer-order-section"' in page
    assert 'id="selected-layer-controls"' in page
    assert "Selected layer order" in page
    assert "function normalizeLayerOrder(order)" in script
    assert "function renderedLayerIdsForUiLayer(layerId)" in script
    assert "function selectedOverlayLayerIds()" in script
    assert "function applyMapLayerOrder(map)" in script
    assert "map.moveLayer(renderLayerId)" in script
    assert "selectedOverlayLayerIds().slice().reverse().forEach((layerId) =>" in script
    assert "return index === -1 ? -1 : ordered.length - index" in script
    assert "function setupLayerOrdering(map)" in script
    assert "card.addEventListener('dragstart'" in script
    assert "card.addEventListener('drop'" in script
    assert "moveLayerOrderItem(layerOrderDragId" in script
    assert "renderLayerOrderControls(map)" in script
    assert "parameters.has('order')" in script
    assert "url.searchParams.set('order', state.layerOrder.join(','))" in script
    assert "syncDataCenterMarkerZOrder()" in script
    assert ".dc-layer-option.is-layer-selected-order" in styles
    assert ".dc-layer-option.is-layer-drop-target" in styles


def test_inspector_tags_filter_records_and_render_removable_header_chips():
    page = (ROOT / "datacenters.html").read_text()
    script = (ROOT / "datacenters" / "js" / "datacenters.js").read_text()
    styles = (ROOT / "datacenters" / "css" / "datacenters.css").read_text()
    assert "Map documented facilities, lifecycle stages" not in page
    assert 'id="active-tag-filters"' in page
    assert 'id="active-tag-filter-list"' in page
    assert 'id="clear-tag-filters"' in page
    assert 'id="tag-filter-mode"' in page
    assert 'data-tag-filter-mode="and"' in page
    assert 'data-tag-filter-mode="or"' in page
    assert "Matching all" not in page
    assert "Matching all" not in script
    assert 'data-filter-tag="${escapeHtml(tag.label)}"' in script
    assert "function bindInspectorTagFilters(detail)" in script
    assert "function recordFilterTagLabels(record)" in script
    assert "activeTagFilters.some((tag) => recordTags.has(tag.toLowerCase()))" in script
    assert "activeTagFilters.every((tag) => recordTags.has(tag.toLowerCase()))" in script
    assert "function renderActiveTagFilters()" in script
    assert 'data-remove-tag="${escapeHtml(tag)}"' in script
    assert "tagFilters: [...activeTagFilters]" in script
    assert "tagFilterMode," in script
    assert "url.searchParams.set('tags', JSON.stringify(state.tagFilters))" in script
    assert "url.searchParams.set('tagMode', state.tagFilterMode)" in script
    assert ".dc-active-tag-filters.has-active-tags" in styles
    assert '.dc-tag-filter-mode button[aria-pressed="true"]' in styles
    assert '.dc-hover-tag[aria-pressed="true"]' in styles


def test_hover_and_click_highlight_the_source_layer_card():
    page = (ROOT / "datacenters.html").read_text()
    script = (ROOT / "datacenters" / "js" / "datacenters.js").read_text()
    styles = (ROOT / "datacenters" / "css" / "datacenters.css").read_text()

    assert "let inspectorHoverLayerId = null" in script
    assert "let inspectorPinnedLayerId = null" in script
    assert "function updateLayerSelectionHighlight()" in script
    assert "card.classList.toggle('is-source-hovered', isHovered)" in script
    assert "card.classList.toggle('is-source-pinned', isPinned)" in script
    assert "pinInspector(target.key, target.render, target.layerId)" in script
    assert "renderHoveredInspector(target.key, target.render, target.layerId)" in script
    assert "renderHoveredInspector(`parcel:${properties.ACCTID || 'unknown'}`, () => renderParcelDetail(properties), 'parcels')" in script
    assert ".dc-layer-option.is-source-hovered" in styles
    assert ".dc-layer-option.is-source-pinned" in styles
    assert 'content: "hovered"' in styles
    assert 'content: "pinned"' in styles


def test_dom_markers_enable_subpixel_positioning_for_smooth_zoom_tracking():
    script = (ROOT / "datacenters" / "js" / "datacenters.js").read_text()
    styles = (ROOT / "datacenters" / "css" / "datacenters.css").read_text()
    assert "subpixelPositioning: true" in script
    assert ".setSubpixelPositioning(true)" in script
    assert "position: absolute;" in styles
    assert "left: 0;" in styles
    assert "top: 0;" in styles
    assert "position: relative;" not in styles.split(".dc-map-marker {", 1)[1].split("}", 1)[0]
    assert ".maplibregl-marker.dc-map-marker--plant {" in styles
    assert "width: 44px;" in styles
    assert "height: 44px;" in styles
    assert "transform: translate(-50%, -50%)" not in styles


def test_map_markers_encode_documented_energy_sources_with_gradients():
    page = (ROOT / "datacenters.html").read_text()
    script = (ROOT / "datacenters" / "js" / "datacenters.js").read_text()
    styles = (ROOT / "datacenters" / "css" / "datacenters.css").read_text()
    plant_codes = {
        code
        for plant in infrastructure("power_plant")
        for code in (plant["generation_fuel_codes"] or plant["energy_source_codes"])
    }

    assert "function markerSourceCodes(record)" in script
    assert "function markerGradient(sourceCodes)" in script
    assert "function iconFillForRecord(record, attribute)" in script
    assert "function outlineColorForRecord(record, attribute)" in script
    assert "conic-gradient(from -35deg" in script
    assert "linear-gradient(145deg" in script
    assert "element.style.setProperty('--marker-icon-fill'" in script
    assert "element.style.setProperty('--marker-outline-color'" in script
    assert all(f"{code}: {{" in script for code in plant_codes)
    assert "onSite.includes('battery')" in script
    assert "/diesel|fuel oil/.test(backup)" in script
    assert "Energy color key" not in page
    assert "background: var(--marker-icon-fill" in styles
    assert "WND: '#dce6ec'" in script
    assert "NUC: '#52ef82'" in script
    assert ".dc-energy-swatch--wind { background: linear-gradient(145deg, #ffffff" in styles
    assert ".dc-energy-swatch--nuclear { background: linear-gradient(145deg, #9affbd" in styles


def test_power_plant_markers_use_a_custom_webgl_layer_with_instanced_bolts():
    script = (ROOT / "datacenters" / "js" / "datacenters.js").read_text()
    model_path = ROOT / "datacenters" / "models" / "lightning-bolt.gltf"
    model = json.loads(model_path.read_text())

    assert model["asset"]["version"] == "2.0"
    assert model["asset"]["generator"] == "generate_lightning_bolt_gltf.py"
    assert model["nodes"][0]["name"] == "LightningBolt"
    assert "pivot_top" in [node["name"] for node in model["nodes"]]
    assert "const POWER_PLANT_WEBGL_LAYER_ID = 'power-plant-bolt-webgl';" in script
    assert "function createPowerPlantBoltLayer(map)" in script
    assert "type: 'custom'" in script
    assert "renderingMode: '2d'" in script
    assert "ANGLE_instanced_arrays" in script
    assert "drawElementsInstanced" in script
    assert "async function loadLightningBoltMesh()" in script
    assert "fetch('/datacenters/models/lightning-bolt.gltf')" in script
    assert model["meshes"][0]["extras"]["outline2d"]
    assert "function buildLightningOutlineMesh(points)" in script
    assert "outline: buildLightningOutlineMesh(outline2d.map(([x, y]) => ({ x, y })))" in script
    assert "const outlineWidth = .045" in script
    assert "const winding = polygonArea(points) >= 0 ? 1 : -1" in script
    assert "options.defaultProjectionData.mainMatrix" in script
    assert "attribute vec3 a_position" in script
    assert "attribute vec3 a_normal" in script
    assert "attribute vec3 a_outlineColor" in script
    assert "-((rotated.y * cos(tilt)) - (rotated.z * sin(tilt)))" in script
    assert "mix(v_accentColor, vec3(1.0), 0.3)" in script
    assert "attribute float a_hover" in script
    assert "float glowAlpha = mix(0.38, 0.92, v_hover);" in script
    assert "if (filled < 0.5) discard;" in script
    assert "gl_FragColor = vec4(litColor, 1.0);" in script
    assert "gl_FragColor = vec4(outlineColor, mix(0.92, 1.0, v_hover));" in script
    assert "indices.push(base, nextBase, nextBase + 1, base, nextBase + 1, base + 1);" in script
    assert "function normalizeBoltOutlineScale(value)" in script
    assert "Math.max(.5, Math.min(2, scale))" in script
    assert "outlineScale: 1.04" in script
    assert "Bolt outline size" in script
    assert "use values below 1 for inset outlines or above 1" in script
    assert "normalizeBoltOutlineScale(formData.get('outlineScale'))" in script
    assert "gl.uniform1f(state.uniforms.scale, boltOutlineScale)" in script
    assert "outlineScale: normalizeBoltOutlineScale(layerFilters.powerPlants.outlineScale)" in script
    assert "a_outlineColor" in script
    assert "v_outlineColor" in script
    assert "Float32Array(state.entries.length * 12)" in script
    assert "uniform mediump float u_outlineOnly;" in script
    assert "drawElementsInstanced(gl.TRIANGLES, state.outlineIndexCount" in script
    assert "outlineIndexCount: state.outlineIndexCount" in script
    assert "if (state.antialiasSamples > 1) gl.enable(gl.SAMPLE_ALPHA_TO_COVERAGE)" in script
    assert "antialiasSamples: state.antialiasSamples" in script
    assert "outline: rgbToHex(entry.outline)" in script
    assert "const cullFaceEnabled = gl.isEnabled(gl.CULL_FACE)" in script
    assert "gl.enable(gl.CULL_FACE);" in script
    assert "gl.cullFace(gl.BACK);" in script
    assert "gl.frontFace(gl.CCW);" in script
    assert "if (!cullFaceEnabled) gl.disable(gl.CULL_FACE);" in script
    assert "setHoveredRecord(record)" in script
    assert "setHoveredRecord(target?.kind === 'power-plant' ? target.record : null)" in script
    assert "function createLightningBoltTextureCanvas" not in script
    assert "function ensurePowerPlantBoltLayer(map)" in script
    assert "map.addLayer(powerPlantBoltLayer);" in script
    assert "powerPlantBoltLayer?.setRecords" in script
    assert "context.fillStyle = entry.accent" in script
    assert "context.strokeStyle = entry.accent" in script
    assert ".sort((left, right) => left.size - right.size" in script
    assert "gl.disable(gl.DEPTH_TEST)" in script
    assert "entry.size > best.size" in script
    assert "zOffset: state.entries.length ? best.size / Math.max(...state.entries.map((entry) => entry.size), 1) : 0" in script
    assert "z: layerZ + Math.min(.99, Math.max(0, hit.zOffset || 0))" in script
    assert "topmostSize: state.entries.at(-1)?.size || 0" in script


def test_generated_lightning_bolt_gltf_has_consistent_face_winding():
    model_path = ROOT / "datacenters" / "models" / "lightning-bolt.gltf"
    model = json.loads(model_path.read_text())
    buffer = base64.b64decode(model["buffers"][0]["uri"].split(",", 1)[1])
    primitive = model["meshes"][0]["primitives"][0]

    def read_accessor(index):
        accessor = model["accessors"][index]
        view = model["bufferViews"][accessor["bufferView"]]
        component_count = {"SCALAR": 1, "VEC2": 2, "VEC3": 3}[accessor["type"]]
        fmt = {5126: "f", 5125: "I"}[accessor["componentType"]]
        stride = view.get("byteStride") or struct.calcsize("<" + (fmt * component_count))
        offset = view.get("byteOffset", 0) + accessor.get("byteOffset", 0)
        values = []
        for item_index in range(accessor["count"]):
            unpacked = struct.unpack_from(
                "<" + (fmt * component_count),
                buffer,
                offset + (item_index * stride),
            )
            values.append(unpacked if component_count > 1 else unpacked[0])
        return values

    positions = [tuple(value) for value in read_accessor(primitive["attributes"]["POSITION"])]
    indices = read_accessor(primitive["indices"])
    front_normals = set()
    back_normals = set()
    side_normals = []

    for offset in range(0, len(indices), 3):
        a, b, c = [positions[index] for index in indices[offset:offset + 3]]
        ab = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
        ac = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
        normal = (
            (ab[1] * ac[2]) - (ab[2] * ac[1]),
            (ab[2] * ac[0]) - (ab[0] * ac[2]),
            (ab[0] * ac[1]) - (ab[1] * ac[0]),
        )
        area = math.sqrt(sum(component * component for component in normal)) / 2
        assert area > 0
        if abs(a[2] - b[2]) < 1e-9 and abs(b[2] - c[2]) < 1e-9:
            normal_z = round(normal[2] / (2 * area), 6)
            if a[2] > 0:
                front_normals.add(normal_z)
            else:
                back_normals.add(normal_z)
        else:
            side_normals.append((round(normal[0] / (2 * area), 6), round(normal[1] / (2 * area), 6)))

    assert front_normals == {1.0}
    assert back_normals == {-1.0}
    assert len(side_normals) == 14
    assert all(abs(normal[0]) > 0 or abs(normal[1]) > 0 for normal in side_normals)


def test_facility_filters_cover_type_lifecycle_energy_and_public_response():
    page = (ROOT / "datacenters.html").read_text()
    script = (ROOT / "datacenters" / "js" / "datacenters.js").read_text()
    assert 'id="layer-filter-modal"' in page
    assert 'id="layer-search"' in page
    for removed_id in ("map-search", "active-layer-filters", "reset-layer-filters"):
        assert f'id="{removed_id}"' not in page
    for layer_id in ("datacenters", "power-plants", "enviroscreen", "parcels"):
        assert f'data-layer-config="{layer_id}"' in page
    assert "document.getElementById('show-datacenters').checked" in script
    assert "document.getElementById('show-power-plants').checked" in script
    for stage in ("operating", "development", "proposal", "paused"):
        assert f"['{stage}'," in script
    assert "const FILTER_OPTIONS" in script
    assert "layerFilters.datacenters" in script
    assert "layerFilters.powerPlants" in script
    assert "function lifecycleStage(record)" in script
    assert "if (record.record_type === 'power_plant') return 'operating'" in script
    assert "function matchesEnergySource(record, energyFilter)" in script
    assert "if (sentimentFilter === 'supportive'" in script
    assert "fieldMarkup('Icon color uses', 'colorBy'" in script
    assert "fieldMarkup('Icon outline uses', 'outlineBy'" in script
    assert "fieldMarkup('Icon glow uses', 'glowBy'" in script
    assert "datacenterIconColor" in script
    assert "datacenterIconGlow" in script
    assert "plantIconOutline" not in script
    assert "function filterLayerCards(query)" in script
    assert "indexedText.includes(normalized)" in script
    assert "const textFilter = isDataCenter ? layerFilters.datacenters.text : layerFilters.powerPlants.text" in script


def test_map_state_persists_center_zoom_and_orientation_in_ui_state_and_query_params():
    script = (ROOT / "datacenters" / "js" / "datacenters.js").read_text()
    assert "if (parameters.has('c'))" in script
    assert "state.center = [lng, lat];" in script
    assert "const center = map.getCenter();" in script
    assert "center: [" in script
    assert "url.searchParams.set('c'," in script
    assert "center: Array.isArray(restoredUiState.center) ? restoredUiState.center : [-76.75, 39.05]," in script
    assert "map.on('moveend', persistMapView);" in script
    assert "url.searchParams.set('z', String(state.zoom))" in script
    assert "url.searchParams.set('o', `${state.orientation.bearing},${state.orientation.pitch}`)" in script


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
    assert "map.on('moveend', () => {" in script
    assert "loadParcelBoundaries(map);" in script
    assert "type: 'line'" in script
    assert "function scheduleParcelLookup(map, lngLat)" in script
    assert "spatialRel: 'esriSpatialRelIntersects'" in script


def test_esri_3d_buildings_stream_through_a_persisted_hoverable_layer():
    page = (ROOT / "datacenters.html").read_text()
    script = (ROOT / "datacenters" / "js" / "datacenters.js").read_text()
    assert "Esri3D_Buildings_v1/SceneServer/layers/0" in script
    assert "id: 'esri-3d-buildings'" in script
    assert "new deck.MapboxOverlay" in script
    assert "new deck.Tile3DLayer" in script
    assert "loader: loaders.I3SLoader" in script
    assert "pickable: true" in script
    assert "renderEsriBuildingDetail(info)" in script
    assert 'id="show-${ESRI_BUILDINGS.id}" type="checkbox"' in script
    assert 'id="hover-${ESRI_BUILDINGS.id}" type="checkbox" checked' in script
    assert "input[id^=\"show-\"]" in script
    assert "input[id^=\"hover-\"]" in script
    assert "20260810-layer-zoom-ranges" in page


def test_optional_maryland_grid_layers_use_official_live_services():
    script = (ROOT / "datacenters" / "js" / "datacenters.js").read_text()
    for layer_id in (
        "md-imap-substations", "md-imap-transmission-lines",
        "bge-generation-hosting", "bge-load-capacity",
        "pepco-generation-hosting", "pepco-load-capacity",
        "delmarva-generation-hosting", "delmarva-load-capacity",
        "potomac-edison-generation-hosting", "smeco-generation-hosting",
    ):
        assert f"id: '{layer_id}'" in script
    assert "MD_PowerTransmission/MapServer/0" in script
    assert "MD_PowerTransmission/MapServer/1" in script
    assert "BGE_HOSTING_CAPACITY_AGOL/FeatureServer/37" in script
    assert "BGE_EV_Load_Capacity/FeatureServer/1" in script
    assert "PHI_Hosting_Capacity_Public/FeatureServer/0" in script
    assert "PHI_Hosting_Capacity_Public/FeatureServer/2" in script
    assert "PHI_EV_Load_Serving_Capacity/FeatureServer/0" in script
    assert "Full_Map_xfmr_MD/FeatureServer/0" in script
    assert "SMECO_2024_CIRCUITS_101024/FeatureServer/1" in script
    assert "function remoteService(config, zoom)" in script
    assert "const service = remoteService(config, zoom)" in script


def test_bge_polygon_layers_follow_their_published_renderer_fields_and_outlines():
    script = (ROOT / "datacenters" / "js" / "datacenters.js").read_text()
    assert "id: 'bge-generation-hosting'" in script
    assert "Sum_Hosting_Capacity_Remaining_kW" in script
    assert "lineColor: '#343434'" in script
    assert "id: 'bge-load-capacity'" in script
    assert "Max_FEEDER_AVAIL_CAP_MW_MIN" in script
    assert "lineColor: '#6e6e6e'" in script
    assert "lineWidth: ['interpolate', ['linear'], ['zoom'], 7, 0.4, 14, 0.8]" in script
    assert "Sum_FEEDER_AVAIL_CAP_MW_MIN'], 0], '#d73027'" not in script


def test_compact_layer_cards_preview_in_the_shared_inspector():
    page = (ROOT / "datacenters.html").read_text()
    script = (ROOT / "datacenters" / "js" / "datacenters.js").read_text()
    styles = (ROOT / "datacenters" / "css" / "datacenters.css").read_text()
    for layer_id in ("datacenters", "power-plants", "enviroscreen", "parcels"):
        assert f'data-layer-preview="{layer_id}"' in page
    assert 'aria-label="Map feature inspector"' in page
    assert '>Inspector<' not in page
    assert '>Evidence<' not in page
    assert "function renderHoveredIconHeading(record)" in script
    assert "function renderHoveredInspector(key, render, layerId = null)" in script
    assert "if (inspectorHoverKey === key) return false" in script
    assert "function selectHoveredRecord(record, sourceById)" in script
    assert "function updateHoveredDataCenterMarker(target)" in script
    assert 'class="dc-hover-tags" aria-label="Record tags"' in script
    assert "icon.tags.map" in script
    assert "Lightning Bolt icon -" not in script
    assert 'data-layer-preview="${escapeHtml(config.id)}"' in script
    assert "function setupLayerCardPreviews()" in script
    assert "card.addEventListener('pointerenter', preview)" in script
    assert "card.addEventListener('focusin', preview)" in script
    assert "function renderLayerCardPreview(config)" in script
    assert "document.getElementById('record-detail').innerHTML" in script
    assert "margin-bottom: .2rem" in styles
    assert "min-height: 3.35rem" in styles
    assert ".dc-layer-controls-row" in styles
    assert "resultRecordCount: '1'" in script
    assert "function renderParcelDetail(properties)" in script
    assert "function renderEnviroScreenDetail(properties)" in script


def test_layer_color_picker_is_adjacent_to_render_and_hover_and_persists():
    page = (ROOT / "datacenters.html").read_text()
    script = (ROOT / "datacenters" / "js" / "datacenters.js").read_text()
    styles = (ROOT / "datacenters" / "css" / "datacenters.css").read_text()

    assert 'id="layer-color-modal"' in page
    assert 'id="layer-color-input" name="color" type="color"' in page
    assert 'data-layer-color="datacenters"' in page
    assert '<input id="show-datacenters" type="checkbox" checked> Render' in page
    assert '<input id="hover-datacenters" type="checkbox" checked> Hover' in page
    assert 'data-layer-color="${escapeHtml(config.id)}"' in script
    assert '<input id="show-${config.id}" type="checkbox"> Render' in script
    assert '<input id="hover-${config.id}" type="checkbox" checked> Hover' in script
    assert "function setupLayerColorUi()" in script
    assert "function applyLayerColor(layerId)" in script
    assert "layerCustomColors.set(activeLayerColorId, input.value.toLowerCase())" in script
    assert "layerCustomColors.delete(activeLayerColorId)" in script
    assert "url.searchParams.set('colors', JSON.stringify(state.colors))" in script
    assert "colors: Object.fromEntries(layerCustomColors)" in script
    assert "layerCustomColors.get(config.id) || config.fillColor || config.color" in script
    assert ".dc-layer-color.has-custom-color" in styles


def test_clicking_a_facility_icon_replaces_the_pinned_inspector_until_it_is_closed():
    page = (ROOT / "datacenters.html").read_text()
    script = (ROOT / "datacenters" / "js" / "datacenters.js").read_text()
    styles = (ROOT / "datacenters" / "css" / "datacenters.css").read_text()

    assert 'id="close-record-detail"' in page
    assert 'aria-label="Close pinned map feature"' in page
    assert "let inspectorPinnedKey = null" in script
    assert "function pinInspector(key, render, layerId = null)" in script
    assert "function closePinnedInspector()" in script
    assert "function pinRecord(record, sourceById)" in script
    assert "if (inspectorPinnedKey && inspectorPinnedKey !== key) return false" not in script
    assert "if (inspectorPinnedKey) return;" in script
    assert "event.stopPropagation();" in script
    assert "pinHoverTarget({" in script
    assert "pinHoverTarget(topMapHoverTarget(map, event.point, sourceById))" in script
    assert "document.getElementById('close-record-detail').hidden = false" in script
    assert ".dc-inspector-close" in styles
    assert ".dc-inspector-close[hidden] { display: none; }" in styles


def test_energy_requirements_and_generation_are_prominent_in_each_record_inspector():
    script = (ROOT / "datacenters" / "js" / "datacenters.js").read_text()
    styles = (ROOT / "datacenters" / "css" / "datacenters.css").read_text()

    assert "function renderEnergySummary(record)" in script
    assert 'aria-label="Data center energy summary"' in script
    assert "Required grid power" in script
    assert "Normal on-site generation" in script
    assert "measured demand not public" in script
    assert "Estimated power draw" in script
    assert "estimated_power_draw_confidence" in script
    assert 'aria-label="Power plant generation summary"' in script
    assert "Planning output" in script
    assert "annual average, not peak capacity" in script
    assert "planning_sustained_output_mw" in script
    assert "annual_capacity_factor" in script
    assert "planning_output_basis" in script
    assert "Average generation" in script
    assert "record.net_generation_mwh" in script
    assert script.count("${renderEnergySummary(record)}") == 2
    render_detail = script.split("function renderDetail(record, sourceById)", 1)[1]
    data_center_template = render_detail.split("if (record.record_type === 'data_center') {", 1)[1].split("} else {", 1)[0]
    assert data_center_template.index("${renderHoveredIconHeading(record)}") < data_center_template.index("${renderEnergySummary(record)}")
    assert data_center_template.index("${renderEnergySummary(record)}") < data_center_template.index("<p class=\"dc-type\">Facility record")
    assert data_center_template.index("${renderEnergySummary(record)}") < data_center_template.index("${renderContestationSpotlight(record, sourceById)}")
    assert ".dc-energy-summary" in styles


def test_power_interchange_inventory_maps_crossings_without_inventing_line_flows():
    data = json.loads((ROOT / "datacenters" / "data" / "power-interchanges.json").read_text())
    metadata = data["metadata"]
    features = data["features"]

    assert data["type"] == "FeatureCollection"
    assert metadata["corridor_count"] == len(features) == 78
    assert metadata["line_crossing_count"] == sum(feature["properties"]["line_count"] for feature in features) == 107
    assert metadata["cluster_distance_meters"] == 120
    assert "not a measurement for any individual mapped line" in metadata["flow_scope"]
    assert "voltage-weighted" in metadata["estimated_crossing_flow_method"]
    assert len({feature["properties"]["crossing_id"] for feature in features}) == len(features)
    estimated_total = 0
    for feature in features:
        longitude, latitude = feature["geometry"]["coordinates"]
        properties = feature["properties"]
        assert -79.5 <= longitude <= -75.0
        assert 37.8 <= latitude <= 39.8
        assert properties["flow_capability"] == "Bidirectional interstate interchange corridor"
        assert properties["line_flow_measurement"] == "Actual direction and MW are not published for this individual crossing"
        assert properties["statewide_flow_direction"] == "Net import"
        assert properties["statewide_net_import_mwh"] == 27_111_098
        assert properties["statewide_flow_year"] == 2024
        assert properties["estimated_average_interchange_mw"] > 0
        assert 0 < properties["estimated_interchange_share_percent"] < 10
        assert properties["estimated_interchange_weight"] > 0
        assert "planning guess, not metered flow" in properties["estimated_interchange_basis"]
        estimated_total += properties["estimated_average_interchange_mw"]
    assert abs(estimated_total - features[0]["properties"]["statewide_average_net_import_mw"]) < len(features) * 0.1


def test_power_import_export_layer_is_optional_persisted_hoverable_and_clickable():
    page = (ROOT / "datacenters.html").read_text()
    script = (ROOT / "datacenters" / "js" / "datacenters.js").read_text()
    sources = json.loads((ROOT / "datacenters" / "data" / "sources.json").read_text())
    source_ids = {source["id"] for source in sources}

    assert "Power imports / exports" in script
    assert "staticDataUrl: '/datacenters/data/power-interchanges.json'" in script
    assert "pointSymbol: 'interchange-arrow'" in script
    assert "defaultSizeBy: 'estimated_average_interchange_mw'" in script
    assert "Estimated crossing average MW" in script
    assert "Estimated crossing average" in script
    assert "Estimate basis" in script
    assert "if (!map.isStyleLoaded())" in script
    assert "'text-field': '➤'" in script
    assert "['get', 'axis_rotation_degrees']" in script
    assert "'net import'], 0, 180" in script
    assert "line-blur" in script
    assert "#ff263f" in script
    assert "78 border corridors / 107 line crossings" in script
    assert "2024 statewide net import" in script
    assert "pinHoverTarget(topMapHoverTarget(map, event.point, sourceById))" in script
    assert "render: () => renderRemoteLayerDetail(config, feature.properties)" in script
    assert "derived official inventory" in script
    assert "stored locally for fast display and reproducible review" in script
    assert "Power interchange JSON" in page
    assert "planning guess, not a metered line-flow value" in page
    assert {
        "hifld-transmission-lines-2024",
        "md-imap-state-boundary",
        "eia-maryland-state-electricity-profile-2024",
        "census-tigerweb-state-boundaries",
        "pjm-maryland-dc-infrastructure-report-2025",
    } <= source_ids


def test_county_power_estimates_allocate_residential_load_without_meter_claims():
    data = json.loads((ROOT / "datacenters" / "data" / "power-estimates.json").read_text())
    metadata = data["metadata"]
    features = data["features"]

    assert data["type"] == "FeatureCollection"
    assert metadata["county_equivalent_count"] == len(features) == 24
    assert "ACS occupied housing units" in metadata["method"]
    assert "not utility-metered county load" in metadata["estimate_scope"]
    assert metadata["statewide_residential_sales_mwh"] == 27_327_356
    assert metadata["statewide_residential_average_mw"] == round(27_327_356 / 8784, 2)
    assert metadata["acs_occupied_housing_units_total"] > 2_000_000

    annual_total = 0
    for feature in features:
        properties = feature["properties"]
        assert feature["geometry"]["type"] in {"Polygon", "MultiPolygon"}
        assert properties["record_type"] == "county_power_estimate"
        assert properties["county"].endswith(("County", "city"))
        assert properties["occupied_housing_units"] > 0
        assert properties["estimated_residential_customers"] > 0
        assert properties["estimated_residential_average_mw"] > 0
        assert properties["estimated_residential_annual_mwh"] > 0
        assert "not utility-metered county load" in properties["estimate_basis"]
        annual_total += properties["estimated_residential_annual_mwh"]
    assert abs(annual_total - metadata["statewide_residential_sales_mwh"]) < len(features)


def test_county_power_estimates_layer_is_optional_hoverable_and_source_backed():
    page = (ROOT / "datacenters.html").read_text()
    script = (ROOT / "datacenters" / "js" / "datacenters.js").read_text()
    sources = json.loads((ROOT / "datacenters" / "data" / "sources.json").read_text())
    source_ids = {source["id"] for source in sources}

    assert "County power estimates" in script
    assert "staticDataUrl: '/datacenters/data/power-estimates.json'" in script
    assert "estimated_residential_average_mw" in script
    assert "residential demand estimates" in script
    assert "staticLayerStatus(config, data)" in script
    assert "County power estimates unavailable" in script
    assert "Derived Maryland county residential electricity estimates" in script
    assert "const queryPoint = { x: point.x, y: point.y }" in script
    assert "map.queryRenderedFeatures(queryPoint, { layers: layerIds })" in script
    assert "Power estimates JSON" in page
    assert "not utility-metered county load" in page
    assert "20260810-layer-zoom-ranges" in page
    assert {
        "eia-retail-sales-md-residential-2024",
        "acs-2024-b25003-md-counties",
        "census-tigerweb-county-boundaries",
    } <= source_ids


def test_worldsim_live_layers_are_lazy_viewport_queries_without_local_downloads():
    page = (ROOT / "datacenters.html").read_text()
    script = (ROOT / "datacenters" / "js" / "datacenters.js").read_text()
    assert "WorldSim3 and official data services" in page
    assert "Large official layers are queried only for the current view" in page
    for layer_id in (
        "dhcd-multifamily", "dhcd-qct", "dhcd-just-communities", "historic-properties",
        "dpw-storm-ms4", "dpw-stormwater", "dpw-water", "dpw-wastewater",
    ):
        assert f"id: '{layer_id}'" in script
    assert "BusinessEconomy/MD_MultifamilySites/FeatureServer/0" in script
    assert "BusinessEconomy/MD_HousingDesignatedAreas/FeatureServer/9" in script
    assert "Historic/MD_InventoryHistoricProperties/MapServer/0" in script
    assert "Hosted/Capital_Improvement_Projects/FeatureServer/3" in script
    assert "geometryType: 'esriGeometryEnvelope'" in script
    assert "function refreshRemoteLayers(map)" in script
    assert "function findRemoteHoverFeature(map, point, requireHover = true)" in script
    assert "remoteLayerStates.get(config.id)?.enabled" in script


def test_zoning_crime_and_grid_layers_follow_live_official_services():
    script = (ROOT / "datacenters" / "js" / "datacenters.js").read_text()
    for layer_id in (
        "mdp-generalized-zoning", "baltimore-city-zoning",
        "baltimore-nibrs-crime", "electric-transmission-lines",
    ):
        assert f"id: '{layer_id}'" in script
    assert "GeneralizedZoning2021_StoryMap/FeatureServer/3" in script
    assert 'where: "JURSCODE = \'BACI\'"' in script
    assert "NIBRS_GroupA_Crime_Data/FeatureServer/0" in script
    assert "US_Electric_Power_Transmission_Lines/FeatureServer/0" in script
    assert "if (config.geometry === 'line')" in script
    assert "config.fillColor || config.color" in script
    assert "config.lineColor || config.color" in script
    assert "data.exceededTransferLimit || count >= Number(remoteResultRecordCount(config, zoom))" in script
    assert "data-layer-locate" in script
    assert "map.easeTo({ center: config.focus.center" in script
    assert "window.__codeCollectiveDatacenterMap = map" in script
    assert "service returned records without map geometry" in script
    assert "id: 'mdp-generalized-zoning'" in script and "minZoom: 0" in script
    assert "id: 'baltimore-city-zoning'" in script and "minZoom: 0" in script
    assert "function remoteRequestPrecision(zoom)" in script
    assert "function remoteMaxAllowableOffset(config, zoom)" in script
    assert "function remoteResultRecordCount(config, zoom)" in script


def test_transmission_line_hover_explains_voltage_class_colors():
    script = (ROOT / "datacenters" / "js" / "datacenters.js").read_text()
    styles = (ROOT / "datacenters" / "css" / "datacenters.css").read_text()

    assert "const TRANSMISSION_VOLTAGE_COLORS" in script
    for value, color in (
        ("Under 100", "#69c7ff"),
        ("100-161", "#20b8d8"),
        ("220-287", "#a58bff"),
        ("345", "#f3a712"),
        ("500", "#ff665e"),
        ("735 And Above", "#ff4fc3"),
        ("DC", "#f8f9fa"),
    ):
        assert f"value: '{value}'" in script
        assert f"color: '{color}'" in script
    assert "field: 'VOLT_CLASS'" in script
    assert "function renderRemoteColorLegend(config, properties = {})" in script
    assert "const displayedValue = active?.label || value || legend.fallback.label" in script
    assert "<small>${escapeHtml(legend.label)} · ${escapeHtml(displayedValue)}</small>" in script
    assert "${renderRemoteColorLegend(config, properties)}" in script
    assert "dc-color-key-item" not in script
    assert ".dc-feature-color-key" in styles
    assert ".dc-color-key-swatch" in styles


def test_point_layer_gears_scale_markers_by_numeric_attributes():
    script = (ROOT / "datacenters" / "js" / "datacenters.js").read_text()
    styles = (ROOT / "datacenters" / "css" / "datacenters.css").read_text()

    assert "function numericPointScaleOptions(records, configuredFields = [])" in script
    assert "function dataCenterPointScaleOptions(records)" in script
    assert "function pointScaleFactors(records, field)" in script
    assert "Math.log1p(value)" in script
    assert "if (rawValue === null || rawValue === undefined || rawValue === '') return null" in script
    assert "if (!values.length)" in script
    assert "const powerPlantRecords = records.length > 0 && records.every((record) => record.record_type === 'power_plant')" in script
    assert "const sizeFloor = powerPlantRecords ? .18 : .65" in script
    assert "const sizeCeiling = powerPlantRecords ? 2.3 : 2" in script
    assert "const missingFactor = powerPlantRecords ? .18 : .55" in script
    assert "factors.set(record, missingFactor)" in script
    assert "factors.set(record, sizeFloor + (Math.max(0, Math.min(1, normalized)) * (sizeCeiling - sizeFloor)))" in script
    assert "function normalizePowerPlantLayerFilters(filters)" in script
    assert "filters.fillBy === 'resource-adjusted-utilization' && (!filters.sizeBy || filters.sizeBy === 'none')" in script
    assert "fieldMarkup('Icon size uses', 'sizeBy'" in script
    assert "Average generation / output (MWh)" in script
    assert "Planning output · annual average (MW)" in script
    assert "nameplate_capacity_mw: 'Nameplate capacity (MW)'" in script
    assert "estimated_power_draw_mw: 'Estimated power draw (MW)'" in script
    assert "reported_grid_demand_mw: 'Net draw · reported grid demand (MW)'" in script
    assert "reported_power_capacity_mw: 'Total draw · published envelope or projected demand (MW)'" in script
    assert "projected_power_demand_mw: 'Projected demand · unbuilt facilities (MW)'" in script
    assert "Projected demand · unbuilt facilities (${reportedCount('projected_power_demand_mw')} projects)" in script
    assert "plantBoltFill" in script
    assert "Resource-adjusted annual utilization" in script
    assert "function plantTechnologyUtilizationBenchmark(record)" in script
    assert "solar: .2" in script
    assert "wind: .35" in script
    assert "powerPlantResourceAdjustedUtilization(record)" in script
    assert "annual output to a technology-specific planning envelope" in script
    assert "Annual-average output / nameplate capacity" not in script
    assert "'capacity-factor'" not in script
    assert "Bolt fill uses" in script
    assert "fillFraction" in script
    assert "Estimated power draw (${reportedCount('estimated_power_draw_mw')} values)" in script
    assert "Net draw · reported grid demand (${reportedCount('reported_grid_demand_mw')} public values)" in script
    assert "record.reported_power_capacity_mw ?? record.projected_power_demand_mw" in script
    assert "Total draw · published envelope or projected demand" in script
    assert "dataCenterPointScaleOptions(records)" in script
    assert "Icons without the selected value use the smallest size" in script
    assert "size: 36 * sizeFactors.get(record)" in script
    assert "minimumSize: state.entries.length" in script
    assert "maximumSize: state.entries.length" in script
    assert "--marker-size" in script
    assert "width: var(--marker-size, 22px)" in styles
    assert "pointer-events: none" in styles.split(".dc-map-marker {", 1)[1].split("}", 1)[0]
    assert ".dc-map-marker.is-map-hovered .dc-map-icon" in styles
    assert "function updateHoveredDataCenterMarker(target)" in script
    assert "has-projected-demand" not in script
    assert "data-projected-demand" not in styles
    assert "exportProjectedDemand" not in script
    assert "['unbuilt', 'Unbuilt with projected demand']" in script
    assert "statusFilter === 'unbuilt'" in script
    assert "Projected grid demand" in script


def test_line_layer_gears_scale_zoom_dependent_widths():
    script = (ROOT / "datacenters" / "js" / "datacenters.js").read_text()

    assert "function normalizeLineWidthMultiplier(value)" in script
    assert "Math.max(.25, Math.min(5, width))" in script
    assert "function scaledLineWidth(expression, multiplier)" in script
    assert "neonStreets: { scope: 'i95', lineWidth: 1 }" in script
    assert "sizeBy: 'reported_power_capacity_mw'" in script
    assert "const LINE_WIDTH_OPTIONS = [" in script
    assert "['3', 'Heavy']" in script
    assert "const LINE_WIDTH_BY_DEFAULT = [['zoom', 'Zoom curve only']]" in script
    assert "function normalizeLineWidthBy(config, value)" in script
    assert "function lineWidthFieldOptions(config)" in script
    assert "function lineWidthExpressionForField(field, multiplier)" in script
    assert "lineWidthFields: [['VOLT_CLASS', 'Voltage class'], ['VOLTAGE', 'Voltage (kV)']]" in script
    assert "lineWidthFields: [['Capacity_MW', 'Available load capacity (MW)']" in script
    assert "lineWidthFields: [['Allowable_PV_kW', 'Allowable PV (kW)']" in script
    assert "config.geometry === 'line' ? fieldMarkup(" in script
    assert "'Line width scale'," in script
    assert "'Line width uses'," in script
    assert "remoteState.lineWidth = normalizeLineWidthMultiplier(savedFilter.lineWidth)" in script
    assert "remoteState.lineWidthBy = normalizeLineWidthBy(config, savedFilter.lineWidthBy)" in script
    assert "state.lineWidth = normalizeLineWidthMultiplier(formData.get('lineWidth'))" in script
    assert "state.lineWidthBy = normalizeLineWidthBy(config, formData.get('lineWidthBy'))" in script
    assert "function transmissionProposalExpression()" in script
    assert "transmissionLineWidthExpression(config)" in script
    assert "transmissionLineBlurExpression(config)" in script
    assert "if (lineWidthBy !== 'zoom') return lineWidthExpressionForField(lineWidthBy, multiplier)" in script
    assert "return scaledLineWidth(base, multiplier)" in script
    assert "proposalBase" not in script
    assert "function rehydrateRemoteLayerAfterStyleSettles(map, config)" in script
    assert "if (!remoteLayerRendered(map, config)) addRemoteLayer(map, config, state.data)" in script
    assert "map.addLayer({\n          id: lineId,\n          type: 'line'," in script
    assert "if (!style?.layers) return" in script


def test_layer_gear_exposes_persisted_zoom_ranges_and_enforces_visibility():
    page = (ROOT / "datacenters.html").read_text()
    script = (ROOT / "datacenters" / "js" / "datacenters.js").read_text()
    styles = (ROOT / "datacenters" / "css" / "datacenters.css").read_text()

    assert "const MAP_MIN_ZOOM = 0" in script
    assert "const MAP_MAX_ZOOM = 18" in script
    assert "const layerZoomRanges = new Map()" in script
    assert "function zoomRangeMarkup(layerId)" in script
    assert "'zoomMin'" in script and "'zoomMax'" in script
    assert "Visible zoom range" in script
    assert "applySubmittedZoomRange(activeLayerConfigId, formData)" in script
    assert "filters: {" in script and "zoomRanges," in script
    assert "state.filters?.zoomRanges" in script
    assert "layerShownAtZoom(layerId, zoom)" in script
    assert "layerShownAtZoom(config.id, map.getZoom())" in script
    assert "layerShownAtZoom('parcels', map.getZoom())" in script
    assert "layerShownAtZoom(ESRI_BUILDINGS.id, map.getZoom())" in script
    assert "applyZoomVisibility(map, allRecords, markerById)" in script
    assert "map.setLayerZoomRange(PARCEL_LAYER_ID" in script
    assert "data-layer-zoom=\"datacenters\"" in page
    assert "data-layer-zoom=\"parcels\"" in page
    assert "dc-layer-zoom" in styles
    assert ".dc-modal-fieldset" in styles
    assert ".dc-modal-two-col" in styles


def test_data_center_glow_is_an_independent_contestation_encoding_and_exports_to_png():
    script = (ROOT / "datacenters" / "js" / "datacenters.js").read_text()
    styles = (ROOT / "datacenters" / "css" / "datacenters.css").read_text()

    assert "function dataCenterGlow(record, glowBy)" in script
    assert "record.contestation_score >= 4" in script
    assert "record.contestation_score === 3" in script
    assert "record.contestation_score === 0" in script
    assert "['proposal', 'development'].includes(lifecycleStage(record))" in script
    assert "kind: 'planned-uncontested', color: '#fff15f'" in script
    assert "const PLANNED_UNCONTESTED_COLOR" in script
    assert "function isPlannedUncontestedDataCenter(record)" in script
    assert "if (isPlannedUncontestedDataCenter(record)) return [PLANNED_UNCONTESTED_COLOR]" in script
    assert "edgeColor: '#ffb000'" in script
    assert "edgeColor: '#32dfff'" in script
    assert "ringWidth: .12" in script
    assert "Contestation · red / planned yellow / quiet white" in script
    assert "Planned or developing facilities with no documented contestation glow yellow" in script
    assert "color: '#ff263f'" in script
    assert "color: '#ffffff'" in script
    assert "glowBy: 'contestation'" in script
    assert "glowDistance: 1" in script
    assert "glowBlur: 1" in script
    assert "function normalizeGlowDistance(value)" in script
    assert "function normalizeGlowBlur(value)" in script
    assert "numberFieldMarkup('Glow distance', 'glowDistance'" in script
    assert "numberFieldMarkup('Glow blur', 'glowBlur'" in script
    assert "element.dataset.glow = glow.kind" in script
    assert "element.dataset.exportGlowBlur" in script
    assert "element.dataset.exportGlowEdgeColor" in script
    assert "element.dataset.exportGlowRingWidth" in script
    assert "marker.dataset.exportGlowColor" in script
    assert "marker.dataset.exportGlowEdgeColor" in script
    assert "marker.dataset.exportGlowRingWidth" in script
    assert "marker.dataset.exportGlowBlur" in script
    assert "context.createRadialGradient" in script
    assert ".dc-map-marker--center::before" in styles
    assert "var(--marker-glow-color, transparent)" in styles
    assert "var(--marker-glow-opacity, 0)" in styles
    assert "var(--marker-glow-blur, 1)" in styles
    assert "var(--marker-glow-edge-color" in styles
    assert "var(--marker-glow-ring-width" in styles


def test_live_point_layers_offer_attribute_scaling_without_adding_it_to_lines_or_polygons():
    script = (ROOT / "datacenters" / "js" / "datacenters.js").read_text()

    assert "function scaleRemotePointData(config, data, sizeBy)" in script
    assert "if (config.geometry !== 'point'" in script
    assert "config.geometry === 'point' ? fieldMarkup(" in script
    assert "'Point size uses'" in script
    assert "_dcPointScale" in script
    assert "['coalesce', ['get', '_dcPointScale'], 1]" in script
    assert "scaleFields: [['ResUnits', 'Residential units']" in script
    assert "scaleFields: [['TRNFM_VOLT', 'Transformer voltage']]" in script
    assert "scaleFields: [['RemainNum', 'Remaining generation capacity']]" in script


def test_transmission_gears_offer_persisted_voltage_heat_themes():
    script = (ROOT / "datacenters" / "js" / "datacenters.js").read_text()

    assert "const TRANSMISSION_HEAT_PALETTES" in script
    assert "{ id: 'uniform', label: 'Uniform layer color', field, expression: null }" in script
    for theme_id in ("black-body", "forge", "stellar"):
        assert f"id: '{theme_id}'" in script
    assert "function transmissionHeatExpression(field, colors)" in script
    assert "lineColorThemes: transmissionLineThemes('Voltage_kV'" in script
    assert "lineColorThemes: transmissionLineThemes('VOLTAGE'" in script
    assert "function remoteLineColor(config)" in script
    assert "map.setPaintProperty(lineId, 'line-color', transmissionLineColorExpression(config))" in script
    assert "'Line color theme'" in script
    assert "They do not show live MW flow" in script
    assert "remoteState.colorTheme = String(savedFilter.colorTheme || (config.lineColorThemes ? 'uniform' : 'default'))" in script
    assert "colorTheme: remoteState?.colorTheme || defaultColorTheme" in script
    assert "colorTheme: config.lineColorThemes ? 'uniform' : 'default'" in script
    assert "if (selectedTheme?.id === 'uniform')" in script
    assert "Uniform line color" in script
    assert "function heatThemeColor(theme, value)" in script
    assert "Voltage proxy · ${escapeHtml(voltageLabel)}" in script


def test_official_maryland_state_and_county_political_boundaries_are_optional_layers():
    script = (ROOT / "datacenters" / "js" / "datacenters.js").read_text()
    for layer_id in ("maryland-state-boundary", "maryland-county-boundaries"):
        assert f"id: '{layer_id}'" in script
    assert "Boundaries/MD_PoliticalBoundaries/FeatureServer/0" in script
    assert "Boundaries/MD_PoliticalBoundaries/FeatureServer/1" in script
    assert "outFields: ['OBJECTID', 'State'" in script
    assert "outFields: ['COUNTY', 'DISTRICT'" in script
    assert "category: 'Political boundaries'" in script
    assert "config.fillOpacity ?? .3" in script
    assert "config.lineWidth || 0" in script
    assert "config.lineOpacity ?? 0" in script


def test_all_map_selections_persist_to_storage_and_shareable_query_parameters():
    script = (ROOT / "datacenters" / "js" / "datacenters.js").read_text()
    assert "codecollective.datacenters.ui-state.v1" in script
    assert "function readUiState()" in script
    assert "function applyUiState(state, themeSelect)" in script
    assert "function currentUiState(" in script
    assert "function persistUiState(" in script
    assert "function normalizedMapView(map)" in script
    assert "localStorage.setItem(UI_STATE_STORAGE_KEY" in script
    for parameter in ("theme", "layers", "hover", "q", "z", "o", "filters", "animation"):
        assert f"url.searchParams.set('{parameter}'" in script
    assert "parameters.has('layers')" in script
    assert "parameters.has('hover')" in script
    assert "parameters.has('z')" in script
    assert "parameters.has('o')" in script
    assert "parameters.has('filters')" in script
    assert "map.on('zoomend', persistMapView)" in script
    assert "map.on('rotateend', persistMapView)" in script
    assert "map.on('pitchend', persistMapView)" in script
