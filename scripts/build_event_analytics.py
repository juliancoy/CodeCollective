#!/usr/bin/env python3
"""Create the compact dataset for /baltimore/analytics/ from event_history.json."""
import json
import math
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
source = ROOT / "baltimore/event_history.json"
rows = []
for event in json.loads(source.read_text()):
    location = event.get("location") or {}
    if not isinstance(location, dict):
        location = {}
    date = None
    weekday = None
    try:
        dt = datetime.fromisoformat(event.get("startDate", "").replace("Z", "+00:00"))
        if dt.tzinfo:
            dt = dt.astimezone(ZoneInfo("America/New_York"))
        date, weekday = dt.date().isoformat(), dt.weekday()
    except (ValueError, TypeError, AttributeError):
        pass
    coordinates = None
    try:
        lat, lon = float(location.get("latitude")), float(location.get("longitude"))
        status = str(location.get("geocode_status", "")).lower()
        if (math.isfinite(lat) and math.isfinite(lon) and -90 < lat < 90
                and -180 <= lon <= 180 and (lat, lon) != (0, 0)
                and not status.startswith(("failed", "skipped", "error"))):
            coordinates = [round(lat, 6), round(lon, 6)]
    except (ValueError, TypeError):
        pass
    tags = event.get("tags") or []
    if not isinstance(tags, list):
        tags = []
    rows.append({
        "name": event.get("name") or "Untitled", "date": date, "weekday": weekday,
        "url": event.get("url") or "", "tags": tags,
        "category": tags[0] if tags else "Uncategorized",
        "org": event.get("orgName") or event.get("org_name") or event.get("source_group") or "Unknown",
        "city": location.get("city") or "Unknown",
        "venue": location.get("name") or location.get("address") or "Unknown",
        "coordinates": coordinates,
    })
report = json.loads((ROOT / "baltimore/event_history.report.json").read_text())
result = {"events": rows, "snapshots": report["unique_json_blobs"],
          "records": report["event_records_read"], "timezone": "America/New_York"}
output = ROOT / "baltimore/analytics/data.json"
output.write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n")
print(f"{len(rows):,} events → {output} ({output.stat().st_size / 1024 / 1024:.1f} MiB)")
