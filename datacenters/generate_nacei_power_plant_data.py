#!/usr/bin/env python3
"""Build the compact official NACEI Canada/Mexico plant comparison layer."""

from __future__ import annotations

import argparse
import json
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

from generate_global_power_plant_data import FUEL_CODES, PLANNING_OUTPUT_FACTORS


OUTPUT = Path(__file__).with_name("data") / "power-plants-nacei.json"
SERVICE = "https://geoappext.nrcan.gc.ca/arcgis/rest/services/NACEI/energy_infrastructure_of_north_america_en/MapServer/15"
DATASET_URL = "https://open.canada.ca/data/en/dataset/40fbe40c-01cd-49d3-8add-0d20ed64c90d"


def download():
    query = urllib.parse.urlencode({
        "where": "Country IN ('Canada','Mexico')",
        "outFields": "*",
        "returnGeometry": "true",
        "outSR": "4326",
        "f": "geojson",
    })
    request = urllib.request.Request(f"{SERVICE}/query?{query}", headers={"User-Agent": "CodeCollective public map generator/1.0"})
    with urllib.request.urlopen(request, timeout=90) as response:
        return json.load(response)


def build(source):
    records = []
    for feature in source.get("features", []):
        row = feature["properties"]
        country = row["Country"]
        if country not in {"Canada", "Mexico"}:
            continue
        country_code = {"Canada": "CAN", "Mexico": "MEX"}[country]
        fuel = row.get("PrimSource") or "Other"
        fuel_key = {
            "Hydroelectric": "Hydro",
            "Natural Gas": "Gas",
            "Petroleum": "Oil",
        }.get(fuel, fuel)
        capacity = float(row["Total_MW"])
        longitude, latitude = feature["geometry"]["coordinates"]
        record_id = f"nacei-{row['OBJECTID']}"
        properties = {
            "record_type": "power_plant",
            "country": country,
            "country_code": country_code,
            "name": row.get("Facility") or f"NACEI plant {row['OBJECTID']}",
            "operator": row.get("Operator") or row.get("Owner") or None,
            "owner": row.get("Owner") or None,
            "city": row.get("City") or None,
            "state": row.get("StateProv") or None,
            "nameplate_capacity_mw": capacity,
            "planning_sustained_output_mw": round(capacity * PLANNING_OUTPUT_FACTORS.get(fuel_key, 0.40), 3),
            "primary_technology": fuel,
            "energy_source_codes": [FUEL_CODES.get(fuel_key, "OTH")],
            "source_name": row.get("Source") or "NACEI",
            "source_url": DATASET_URL,
            "source_year": int(str(row.get("Period") or "201708")[:4]),
            "source_period": str(row.get("Period") or "201708"),
            "location_tags": [country, f"ISO3 {country_code}", row.get("StateProv")],
            "coordinate_confidence": "source-reported",
            "nacei_object_id": row["OBJECTID"],
        }
        properties = {key: value for key, value in properties.items() if value not in (None, "")}
        properties["location_tags"] = [value for value in properties["location_tags"] if value]
        records.append({
            "type": "Feature",
            "id": record_id,
            "geometry": {"type": "Point", "coordinates": [round(longitude, 6), round(latitude, 6)]},
            "properties": properties,
        })
    records.sort(key=lambda feature: (feature["properties"]["country_code"], feature["properties"]["name"], feature["id"]))
    country_counts = Counter(feature["properties"]["country_code"] for feature in records)
    return {
        "type": "FeatureCollection",
        "metadata": {
            "inventory": "NACEI power plants of 100 MW or more in Canada and Mexico",
            "reference_period": "2017-08",
            "record_count": len(records),
            "country_counts": dict(sorted(country_counts.items())),
            "threshold_mw": 100,
            "freshness_note": "Official comparison inventory limited to plants of at least 100 MW and dated August 2017.",
            "planning_output_method": "Code Collective fuel-family factors applied to source-reported nameplate capacity solely for visual scaling; not publisher-reported generation.",
            "source_urls": [DATASET_URL, SERVICE],
            "license": "Open Government Licence - Canada",
        },
        "features": records,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, help="Optional local ArcGIS GeoJSON")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    data = build(json.loads(args.input.read_text()) if args.input else download())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n")
    print(f"Wrote {len(data['features'])} NACEI plants to {args.output}")


if __name__ == "__main__":
    main()
