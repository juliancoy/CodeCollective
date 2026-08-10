from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_root_requirements_include_selenium_for_datacenter_smoke():
    requirements = (ROOT / "requirements.txt").read_text().splitlines()
    assert "selenium" in requirements


def test_datacenter_selenium_wrapper_reuses_local_site_and_docker_grid():
    wrapper = (ROOT / "datacenters" / "scripts" / "run-selenium-datacenters-smoke.sh").read_text()
    assert "serve_local.sh" in wrapper
    assert 'SITE_PORT="${SITE_PORT:-8765}"' in wrapper
    assert 'SITE_CONTAINER_NAME="${SITE_CONTAINER_NAME:-codecollective-local-site}"' in wrapper
    assert "canonical_site_running()" in wrapper
    assert "restarting ${SITE_CONTAINER_NAME} on 0.0.0.0:${SITE_PORT}" in wrapper
    assert "port ${SITE_PORT} is occupied by a non-canonical server" in wrapper
    assert "selenium/standalone-chrome:latest" in wrapper
    assert "host.docker.internal:host-gateway" in wrapper
    assert "/datacenters.html" in wrapper
    assert "SELENIUM_URL" in wrapper
    assert "DATACENTERS_BASE_URL" in wrapper


def test_datacenter_selenium_probe_targets_sdat_parcel_hover_metrics():
    script = (ROOT / "datacenters" / "scripts" / "selenium-datacenters-smoke.py").read_text()
    assert "https://host.docker.internal:8765/datacenters.html" in script
    assert "PlanningCadastre/MD_ParcelBoundaries/MapServer/0/query" in script
    assert "show-parcels" in script
    assert "hover-parcels" in script
    assert "parcel-status" in script
    assert "resultRecordCount=1" in script
    assert "hover_to_detail_ms" in script


def test_datacenter_selenium_probe_verifies_webgl_power_plant_meshes():
    script = (ROOT / "datacenters" / "scripts" / "selenium-datacenters-smoke.py").read_text()

    assert "def verify_power_plant_webgl" in script
    assert "diagnostics?.ready && diagnostics.renderCount > 1" in script
    assert 'document.querySelectorAll(\'.dc-map-marker--plant\').length' in script
    assert 'diagnostics["lastGlError"] != 0' in script
    assert 'getDiagnostics?.().hoveredRecordId' in script
    assert '"IGS Solar I - BWI2"' in script
    assert "style.animationName !== 'dc-aerial-push-in'" in script
    assert "aerial animation limits did not apply" in script
    assert "same-feature hover refreshed the inspector gallery" in script
    assert "pinned inspector was replaced by hover" in script
    assert 'find_element(By.ID, "close-record-detail").click()' in script
    assert "power output scaling did not vary WebGL bolt sizes" in script
    assert "larger WebGL bolts were not assigned the highest draw order" in script
    assert "power output was absent from point scaling options" in script
    assert "verified entity image was not attributed above the aerial" in script
    assert "dc-entity-image" in script
    assert '"Calvert Cliffs Nuclear Power Plant"' in script
    assert '"Fourmile Ridge"' in script
    assert 'datacenters-power-webgl-hover-1.png' in script
    assert "WebGL lightning bolt frames did not animate" in script


def test_datacenter_selenium_probe_verifies_neon_i95_default_and_broader_street_scope():
    script = (ROOT / "datacenters" / "scripts" / "selenium-datacenters-smoke.py").read_text()

    assert "def verify_neon_streets" in script
    assert "non-I-95 roads leaked into the default neon view" in script
    assert "ordinary streets remained visible beneath the default neon overlay" in script
    assert "hover arbiter did not choose the highest rendered z-value" in script
    assert "inspector did not show the one chosen hover target" in script
    assert "datacenters-neon-i95.png" in script
    assert "neon_streets = verify_neon_streets" in script


def test_datacenter_selenium_probe_verifies_transmission_color_key():
    script = (ROOT / "datacenters" / "scripts" / "selenium-datacenters-smoke.py").read_text()

    assert "def verify_transmission_color_key" in script
    assert 'remote-electric-transmission-lines-line' in script
    assert 'dc-feature-color-key' in script
    assert "transmission heat theme was not reflected in hover" in script
    assert "transmission heat theme options were incomplete" in script
    assert "transmission hover included a full legend" in script
    assert "datacenters-transmission-color-key.png" in script


def test_datacenter_selenium_probe_verifies_maryland_imagery_base_layer():
    script = (ROOT / "datacenters" / "scripts" / "selenium-datacenters-smoke.py").read_text()

    assert "def verify_base_layers" in script
    assert "base-md-six-inch-imagery" in script
    assert "datacenters-maryland-six-inch-imagery.png" in script
    assert 'imagery["backgroundVisibility"] != "none"' in script
    assert "datacenters-parcel-hover-report.json" in script
    assert "verify_baltimore_zoning" in script
    assert "def verify_no_base_and_png_export" in script
    assert "datacenters-no-base-blue.png" in script
    assert 'exported["type"] != "image/png"' in script
    assert "def verify_layer_search" in script
    assert "layer search changed map records instead of card visibility" in script
    assert "queryRenderedFeatures" in script
    assert "datacenters-baltimore-zoning-visible.png" in script
    assert '"--zoning-only"' in script


def test_datacenter_selenium_probe_verifies_compact_persisted_layer_colors():
    script = (ROOT / "datacenters" / "scripts" / "selenium-datacenters-smoke.py").read_text()

    assert "def verify_layer_color_controls" in script
    assert 'cardHeight' in script
    assert '["Render", "Hover"]' in script
    assert "color, render, and hover controls were not on the same row" in script
    assert "#19c37d" in script
    assert "codecollective.datacenters.ui-state.v1" in script
    assert "datacenters-layer-color-controls.png" in script
    assert "layer_color_controls = verify_layer_color_controls" in script


def test_datacenter_selenium_probe_verifies_power_scale_tags_and_filter():
    script = (ROOT / "datacenters" / "scripts" / "selenium-datacenters-smoke.py").read_text()

    assert "def verify_data_center_power_scale" in script
    assert 'Cogent Elkridge' in script
    assert 'Power envelope:' in script
    assert "not measured operating draw" in script
    assert '["all", "sub-megawatt", "small", "medium", "large", "very-large", "unknown"]' in script
    assert "datacenters-power-scale-filter.png" in script
    assert "data_center_power_scale = verify_data_center_power_scale" in script


def test_datacenter_selenium_probe_verifies_net_and_total_draw_icon_scaling():
    script = (ROOT / "datacenters" / "scripts" / "selenium-datacenters-smoke.py").read_text()

    assert "def verify_data_center_draw_scaling" in script
    assert "Net draw · reported grid demand" in script
    assert "Total draw · published power envelope" in script
    assert "AiNET CyberNAP" in script
    assert "Aligned Data Centers IAD04" in script
    assert "undisclosed net draw did not use the smallest marker size" in script
    assert '"datacenters-total-draw-icon-scaling.png"' in script
    assert "data_center_draw_scaling = verify_data_center_draw_scaling" in script


def test_datacenter_selenium_probe_verifies_contestation_glow_dimension():
    script = (ROOT / "datacenters" / "scripts" / "selenium-datacenters-smoke.py").read_text()

    assert "def verify_data_center_glow" in script
    assert "Amazon Data Services BWI-150 through BWI-153" in script
    assert "AiNET Beltsville Data Center" in script
    assert "contested facility did not receive a red glow" in script
    assert "quiet facility did not receive a white glow" in script
    assert "intermediate facility received a misleading glow" in script
    assert '"datacenters-contestation-glow.png"' in script
    assert "data_center_glow = verify_data_center_glow" in script
    assert 'parser.add_argument("--glow-only"' in script


def test_datacenter_selenium_probe_verifies_mobile_layout_and_inspector():
    script = (ROOT / "datacenters" / "scripts" / "selenium-datacenters-smoke.py").read_text()

    assert "def verify_mobile_layout" in script
    assert "Emulation.setDeviceMetricsOverride" in script
    assert "mobile page scrolls horizontally" in script
    assert "mobile map controls are too small for touch" in script
    assert "pinned mobile inspector is not a bottom sheet" in script
    assert "mobile filter dialog actions are not reachable" in script
    assert '"datacenters-mobile-overview.png"' in script
    assert '"datacenters-mobile-inspector.png"' in script
    assert '"datacenters-mobile-layer-dialog.png"' in script
    assert 'parser.add_argument("--mobile-only"' in script
