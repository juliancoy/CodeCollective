#!/usr/bin/env python3
"""Build the compact non-U.S. WRI power-plant baseline loaded by global map scopes."""

from __future__ import annotations

import argparse
import csv
import io
import json
import urllib.request
from collections import Counter
from pathlib import Path


OUTPUT = Path(__file__).with_name("data") / "power-plants-global.json"
WRI_RELEASE = "1.3.0"
WRI_COMMIT = "7a91cfbb2a4e272597acbc00506d61fc1ec73b3d"
WRI_DATASET_URL = "https://datasets.wri.org/datasets/global-power-plant-database"
WRI_CSV_URL = (
    "https://raw.githubusercontent.com/wri/global-power-plant-database/"
    f"{WRI_COMMIT}/output_database/global_power_plant_database.csv"
)

FUEL_CODES = {
    "Biomass": "WDS",
    "Coal": "BIT",
    "Cogeneration": "OTH",
    "Gas": "NG",
    "Geothermal": "GEO",
    "Hydro": "WAT",
    "Nuclear": "NUC",
    "Oil": "DFO",
    "Other": "OTH",
    "Petcoke": "PC",
    "Solar": "SUN",
    "Storage": "MWH",
    "Waste": "MSW",
    "Wave and Tidal": "WAT",
    "Wind": "WND",
}

# Used only to make the existing resource-adjusted size control meaningful. The
# source inventory reports capacity, not projected output; the basis is explicit.
PLANNING_OUTPUT_FACTORS = {
    "Biomass": 0.55,
    "Coal": 0.55,
    "Cogeneration": 0.55,
    "Gas": 0.45,
    "Geothermal": 0.80,
    "Hydro": 0.42,
    "Nuclear": 0.90,
    "Oil": 0.20,
    "Other": 0.40,
    "Petcoke": 0.55,
    "Solar": 0.20,
    "Storage": 0.25,
    "Waste": 0.55,
    "Wave and Tidal": 0.30,
    "Wind": 0.35,
}


def download(url):
    request = urllib.request.Request(url, headers={"User-Agent": "CodeCollective public map generator/1.0"})
    with urllib.request.urlopen(request, timeout=90) as response:
        return response.read()


def optional_text(value):
    cleaned = str(value or "").strip()
    return cleaned or None


def optional_number(value, digits=3):
    try:
        return round(float(value), digits)
    except (TypeError, ValueError):
        return None


def optional_year(value):
    number = optional_number(value, 0)
    return int(number) if number is not None else None


def build(csv_bytes):
    rows = csv.DictReader(io.StringIO(csv_bytes.decode("utf-8-sig")))
    records = []
    for row in rows:
        # U.S. records come from newer final EIA-860/EIA-923 files and must not
        # be duplicated by this older global research baseline.
        if row["country"] == "USA":
            continue
        latitude = optional_number(row["latitude"], 6)
        longitude = optional_number(row["longitude"], 6)
        capacity = optional_number(row["capacity_mw"])
        if latitude is None or longitude is None or capacity is None:
            continue
        country_code = row["country"].strip()
        country = row["country_long"].strip()
        fuel = optional_text(row["primary_fuel"]) or "Other"
        other_fuels = [
            value for value in (optional_text(row.get(f"other_fuel{index}")) for index in range(1, 4))
            if value
        ]
        source_name = optional_text(row["source"]) or "WRI source not named"
        source_url = optional_text(row["url"])
        source_year = optional_year(row["year_of_capacity_data"])
        commissioning_year = optional_year(row["commissioning_year"])
        planning_factor = PLANNING_OUTPUT_FACTORS.get(fuel, 0.40)
        properties = {
            "record_type": "power_plant",
            "country": country,
            "country_code": country_code,
            "name": optional_text(row["name"]),
            "operator": optional_text(row["owner"]),
            "latitude": latitude,
            "longitude": longitude,
            "nameplate_capacity_mw": capacity,
            "planning_sustained_output_mw": round(capacity * planning_factor, 3),
            "primary_technology": fuel,
            "technology_tags": other_fuels or None,
            "energy_source_codes": [FUEL_CODES.get(fuel, "OTH")],
            "year_built": commissioning_year,
            "source_name": source_name,
            "source_url": source_url,
            "source_year": source_year,
            "geolocation_source": optional_text(row["geolocation_source"]),
            "location_tags": [country, f"ISO3 {country_code}"],
            "coordinate_confidence": "source-reported",
        }
        properties = {key: value for key, value in properties.items() if value is not None}
        record_id = f"wri-{row['gppd_idnr'].strip().lower()}"
        properties.pop("latitude")
        properties.pop("longitude")
        records.append({
            "type": "Feature",
            "id": record_id,
            "geometry": {"type": "Point", "coordinates": [longitude, latitude]},
            "properties": properties,
        })

    records.sort(key=lambda feature: (
        feature["properties"]["country_code"],
        feature["properties"].get("name") or "",
        feature["id"],
    ))
    country_counts = Counter(feature["properties"]["country_code"] for feature in records)
    return {
        "type": "FeatureCollection",
        "metadata": {
            "inventory": "WRI Global Power Plant Database non-U.S. baseline",
            "release": WRI_RELEASE,
            "record_count": len(records),
            "country_count": len(country_counts),
            "country_counts": dict(sorted(country_counts.items())),
            "freshness_note": "Plant capacity source years vary by country and are retained per record; this baseline is older than the final 2024 U.S. EIA inventory.",
            "planning_output_method": "Code Collective fuel-family factors applied to source-reported nameplate capacity solely for visual scaling; not publisher-reported generation.",
            "source_urls": [WRI_DATASET_URL, WRI_CSV_URL],
            "license": "CC BY 4.0",
        },
        "features": records,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, help="Optional local WRI CSV; downloads the pinned release when omitted")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    data = build(args.csv.read_bytes() if args.csv else download(WRI_CSV_URL))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    metadata = json.dumps(data["metadata"], ensure_ascii=False, separators=(",", ":"))
    features = ",\n".join(
        json.dumps(feature, ensure_ascii=False, separators=(",", ":"))
        for feature in data["features"]
    )
    args.output.write_text(f'{{"type":"FeatureCollection","metadata":{metadata},"features":[\n{features}\n]}}\n')
    print(
        f"Wrote {len(data['features'])} plants across {data['metadata']['country_count']} "
        f"countries to {args.output}"
    )


if __name__ == "__main__":
    main()
