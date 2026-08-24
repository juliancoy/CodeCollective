#!/usr/bin/env python3
"""Build approximate agency-jurisdiction points from EFF's Atlas of Surveillance."""

import csv
import io
import json
import re
import urllib.request
import zipfile
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "data" / "atlas-surveillance.json"
ATLAS_URL = "https://atlasofsurveillance.org/download.csv"
PLACE_URL = "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2025_Gazetteer/2025_Gaz_place_national.zip"
COUNTY_URL = "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2025_Gazetteer/2025_Gaz_counties_national.zip"


def download(url):
    request = urllib.request.Request(url, headers={"User-Agent": "CodeCollective public map generator/1.0"})
    with urllib.request.urlopen(request, timeout=90) as response:
        return response.read()


def normalized_name(value):
    value = re.sub(r"[^a-z0-9]+", " ", (value or "").lower()).strip()
    suffixes = (" city and borough", " municipality", " village", " borough", " county", " parish", " city", " town", " cdp")
    for suffix in suffixes:
        if value.endswith(suffix):
            value = value[:-len(suffix)].strip()
    return value


def gazetteer_rows(url):
    archive = zipfile.ZipFile(io.BytesIO(download(url)))
    filename = archive.namelist()[0]
    text = io.TextIOWrapper(archive.open(filename), encoding="utf-8-sig")
    return list(csv.DictReader(text, delimiter="|"))


def coordinate_indexes():
    places = gazetteer_rows(PLACE_URL)
    counties = gazetteer_rows(COUNTY_URL)
    place_candidates = defaultdict(list)
    for row in places:
        place_candidates[(row["USPS"], normalized_name(row["NAME"]))].append(
            (float(row["INTPTLONG"]), float(row["INTPTLAT"]))
        )
    place_index = {key: points[0] for key, points in place_candidates.items() if len(points) == 1}
    county_index = {
        (row["USPS"], normalized_name(row["NAME"])): (float(row["INTPTLONG"]), float(row["INTPTLAT"]))
        for row in counties
    }
    state_points = defaultdict(list)
    for row in counties:
        state_points[row["USPS"]].append((float(row["INTPTLONG"]), float(row["INTPTLAT"])))
    state_index = {
        state: (sum(point[0] for point in points) / len(points), sum(point[1] for point in points) / len(points))
        for state, points in state_points.items()
    }
    return place_index, county_index, state_index


def locate(row, place_index, county_index, state_index):
    state = row["State"].strip()
    city_key = (state, normalized_name(row["City"]))
    county_key = (state, normalized_name(row["County"]))
    if city_key in place_index:
        return (*place_index[city_key], "Census place centroid")
    if county_key in county_index:
        return (*county_index[county_key], "Census county centroid")
    if state in state_index:
        return (*state_index[state], "derived state overview point")
    return None


def build():
    place_index, county_index, state_index = coordinate_indexes()
    rows = list(csv.DictReader(io.StringIO(download(ATLAS_URL).decode("utf-8-sig"))))
    grouped = defaultdict(list)
    for row in rows:
        grouped[(row["Agency"].strip(), row["City"].strip(), row["County"].strip(), row["State"].strip())].append(row)

    features = []
    precision_counts = defaultdict(int)
    for index, ((agency, city, county, state), records) in enumerate(sorted(grouped.items()), 1):
        located = locate(records[0], place_index, county_index, state_index)
        if not located:
            continue
        longitude, latitude, precision = located
        precision_counts[precision] += 1
        technologies = sorted({row["Technology"].strip() for row in records if row["Technology"].strip()})
        vendors = sorted({row["Vendor"].strip() for row in records if row["Vendor"].strip()})
        source_urls = [row["Link 1"].strip() for row in records if row["Link 1"].strip()]
        features.append({
            "type": "Feature",
            "id": f"atlas-agency-{index:05d}",
            "geometry": {"type": "Point", "coordinates": [round(longitude, 6), round(latitude, 6)]},
            "properties": {
                "agency": agency,
                "city": city,
                "county": county,
                "state": state,
                "technologies": ", ".join(technologies),
                "technology_count": len(technologies),
                "records": len(records),
                "vendors": ", ".join(vendors),
                "location_precision": precision,
                "source_url": source_urls[0] if source_urls else "https://atlasofsurveillance.org/search",
            },
        })
    return {
        "type": "FeatureCollection",
        "metadata": {
            "generated_date": "2026-08-24",
            "source": ATLAS_URL,
            "license": "CC BY",
            "source_record_count": len(rows),
            "agency_feature_count": len(features),
            "location_precision_counts": dict(sorted(precision_counts.items())),
            "note": "Points represent agency jurisdictions, not individual devices. City and county records use Census 2025 internal points; remaining records use a state overview point.",
        },
        "features": features,
    }


if __name__ == "__main__":
    data = build()
    OUTPUT.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    print(f"Wrote {OUTPUT} with {len(data['features'])} agency features")
