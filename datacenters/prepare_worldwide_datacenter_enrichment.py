#!/usr/bin/env python3
"""Prepare a deterministic, cost-bounded Kimi input from OSM data centers."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
WORLD_INPUT = ROOT / "data" / "data-centers-openstreetmap-world.json"
US_INPUT = ROOT / "data" / "data-centers-openstreetmap-us.json"
DEFAULT_OUTPUT = ROOT / "research" / "worldwide-datacenters" / "enrichment-input.json"
DEFAULT_REPORT = ROOT / "research" / "worldwide-datacenters" / "enrichment-input-report.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=WORLD_INPUT if WORLD_INPUT.exists() else US_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    return parser.parse_args()


def feature_record(feature: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    properties = feature.get("properties")
    geometry = feature.get("geometry")
    if not isinstance(properties, dict) or not isinstance(geometry, dict):
        return None, "malformed_feature"
    coordinates = geometry.get("coordinates")
    if geometry.get("type") != "Point" or not isinstance(coordinates, list) or len(coordinates) < 2:
        return None, "missing_point_geometry"
    osm_type = properties.get("osm_type")
    osm_id = properties.get("osm_id")
    if osm_type not in {"node", "way", "relation"} or not isinstance(osm_id, int):
        return None, "missing_osm_identity"
    name = str(properties.get("name") or "").strip()
    operator = str(properties.get("operator") or "").strip()
    website = str(properties.get("website") or "").strip()
    address = str(properties.get("street_address") or "").strip()
    locality = str(properties.get("city") or "").strip()
    if not any((name, operator, website, address)):
        return None, "weak_identity"
    if name and operator and website:
        priority = 1
    elif (name or operator) and address:
        priority = 2
    elif name or operator:
        priority = 3
    else:
        priority = 4
    facility_name = name or operator or f"OpenStreetMap {osm_type} {osm_id}"
    record = {
        "id": f"osm-{osm_type}-{osm_id}",
        "record_type": "data_center",
        "name": facility_name,
        "operator": operator or None,
        "owner": properties.get("owner"),
        "campus": properties.get("campus"),
        "website": website or None,
        "street_address": address or None,
        "city": locality or None,
        "state": properties.get("state"),
        "region": properties.get("state_name") or properties.get("region"),
        "postal_code": properties.get("postal_code"),
        "country": properties.get("country"),
        "country_code": properties.get("country_code"),
        "latitude": coordinates[1],
        "longitude": coordinates[0],
        "location_tags": properties.get("location_tags") or [],
        "facility_tags": properties.get("facility_tags") or [],
        "osm_type": osm_type,
        "osm_id": osm_id,
        "osm_url": properties.get("osm_url") or f"https://www.openstreetmap.org/{osm_type}/{osm_id}",
        "source_snapshot_at": properties.get("source_snapshot_at"),
        "source_ids": ["openstreetmap"],
        "research_priority": priority,
        "power_profile": "not yet researched",
    }
    return record, None


def prepare(payload: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if payload.get("type") != "FeatureCollection" or not isinstance(payload.get("features"), list):
        raise ValueError("input must be a GeoJSON FeatureCollection")
    records: list[dict[str, Any]] = []
    deferred = Counter()
    for feature in payload["features"]:
        record, reason = feature_record(feature)
        if record is None:
            deferred[reason or "unknown"] += 1
        else:
            records.append(record)
    records.sort(
        key=lambda row: (
            row["research_priority"],
            str(row.get("country_code") or "ZZ"),
            str(row.get("name") or "").casefold(),
            row["id"],
        )
    )
    report = {
        "source_inventory": payload.get("metadata", {}).get("inventory"),
        "source_snapshot": payload.get("metadata", {}).get("source_timestamp"),
        "source_record_count": len(payload["features"]),
        "eligible_count": len(records),
        "deferred_count": sum(deferred.values()),
        "deferred_reasons": dict(sorted(deferred.items())),
        "country_counts": dict(sorted(Counter(str(row.get("country_code") or "unknown") for row in records).items())),
        "priority_counts": {str(key): value for key, value in sorted(Counter(row["research_priority"] for row in records).items())},
    }
    return records, report


def main() -> int:
    args = parse_args()
    records, report = prepare(json.loads(args.input.read_text(encoding="utf-8")))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(records, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"input": str(args.input), "output": str(args.output), **report}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
