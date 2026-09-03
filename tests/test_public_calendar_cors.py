from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_worker_applies_cors_to_public_calendar_assets():
    worker = (ROOT / "cloudflare/worker.js").read_text()

    assert "function isPublicCalendarAsset(path)" in worker
    assert 'path === "/upcoming_events.json"' in worker
    assert 'path === "/cc_events.ics"' in worker
    assert "(?:upcoming_events|manual_events|scrape_errors|skipped_events|calendar_lenses)\\.json" in worker
    assert "applyPublicCors(headers)" in worker
    assert '"access-control-allow-origin", "*"' in worker
    assert '"access-control-allow-methods", "GET,HEAD,OPTIONS"' in worker
    assert 'request.method === "OPTIONS" && isPublicCalendarAsset(path)' in worker


def test_cloudflare_site_headers_document_calendar_cors_contract():
    build_script = (ROOT / "cloudflare/scripts/build_cloudflare_site.sh").read_text()

    assert "/:city/upcoming_events.json" in build_script
    assert "/:city/cc_events.ics" in build_script
    assert "Access-Control-Allow-Origin: *" in build_script
    assert "Access-Control-Allow-Methods: GET,HEAD,OPTIONS" in build_script
    assert "Access-Control-Max-Age: 86400" in build_script
