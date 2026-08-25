#!/usr/bin/env python3
"""Build the compact nationwide EIA power-plant inventory used on demand by the map."""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import tempfile
import urllib.request
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

from generate_datacenter_energy_data import (
    STATE_FIPS,
    STATE_NAMES,
    add_coordinate_confidence,
    clean_number,
    enrich_power_plant_planning_output,
    plant_status_metadata,
)


OUTPUT = Path(__file__).with_name("data") / "power-plants-us.json"
PLACE_URL = "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2025_Gazetteer/2025_Gaz_place_national.zip"
COUNTY_URL = "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2025_Gazetteer/2025_Gaz_counties_national.zip"
EIA_860_URL = "https://www.eia.gov/electricity/data/eia860/xls/eia8602024.zip"
EIA_923_URL = "https://www.eia.gov/electricity/data/eia923/archive/xls/f923_2024.zip"
ISO_BY_BALANCING_AUTHORITY = {
    "CISO": "CAISO",
    "ERCO": "ERCOT",
    "ISNE": "ISO-NE",
    "MISO": "MISO",
    "NYIS": "NYISO",
    "PJM": "PJM",
    "SWPP": "SPP",
}


def normalize_name(value):
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def download(url):
    request = urllib.request.Request(url, headers={"User-Agent": "CodeCollective public map generator/1.0"})
    with urllib.request.urlopen(request, timeout=90) as response:
        return response.read()


def gazetteer_rows(url):
    archive = zipfile.ZipFile(io.BytesIO(download(url)))
    filename = archive.namelist()[0]
    text = io.TextIOWrapper(archive.open(filename), encoding="utf-8-sig")
    return list(csv.DictReader(text, delimiter="|"))


def extract_workbook(archive_bytes, filename, directory):
    archive = zipfile.ZipFile(io.BytesIO(archive_bytes))
    matches = [member for member in archive.namelist() if Path(member).name == filename]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one {filename} workbook, found {len(matches)}")
    destination = directory / filename
    destination.write_bytes(archive.read(matches[0]))
    return destination


def download_eia_workbooks(directory):
    eia_860 = download(EIA_860_URL)
    eia_923 = download(EIA_923_URL)
    return (
        extract_workbook(eia_860, "2___Plant_Y2024.xlsx", directory),
        extract_workbook(eia_860, "3_1_Generator_Y2024.xlsx", directory),
        extract_workbook(eia_923, "EIA923_Schedules_2_3_4_5_M_12_2024_Final.xlsx", directory),
    )


def census_indexes():
    county_index = {}
    for row in gazetteer_rows(COUNTY_URL):
        name = re.sub(r"\s+(county|parish|borough|census area|municipality)$", "", row["NAME"], flags=re.I)
        county_index[(row["USPS"], normalize_name(name))] = row["GEOID"]

    candidates = defaultdict(list)
    for row in gazetteer_rows(PLACE_URL):
        name = re.sub(r"\s+(city and borough|municipality|village|borough|city|town|cdp)$", "", row["NAME"], flags=re.I)
        candidates[(row["USPS"], normalize_name(name))].append(row["GEOID"])
    place_index = {key: values[0] for key, values in candidates.items() if len(values) == 1}
    return county_index, place_index


def text(value):
    return None if pd.isna(value) or not str(value).strip() else str(value).strip()


def number(value, digits=3):
    numeric = pd.to_numeric(value, errors="coerce")
    return None if pd.isna(numeric) else clean_number(numeric, digits)


def record_location_metadata(plant, county_index, place_index):
    state = str(plant["State"]).strip().upper()
    state_name = STATE_NAMES.get(state, state)
    state_fips = STATE_FIPS.get(state)
    county = text(plant["County"])
    city = text(plant["City"])
    county_fips = county_index.get((state, normalize_name(county)))
    place_fips = place_index.get((state, normalize_name(city)))
    balancing_authority = text(plant.get("Balancing Authority Code"))
    nerc_region = text(plant.get("NERC Region"))
    iso_region = ISO_BY_BALANCING_AUTHORITY.get(balancing_authority)
    tags = [state_name]
    if county:
        tags.append(county)
    if city:
        tags.append(city)
    if state_fips:
        tags.append(f"Census state {state_fips}")
    if county_fips:
        tags.append(f"Census county {county_fips}")
    if place_fips:
        tags.append(f"Census place {place_fips}")
    if nerc_region:
        tags.append(f"NERC {nerc_region}")
    if balancing_authority:
        tags.append(f"Balancing authority {balancing_authority}")
    if iso_region:
        tags.append(f"ISO {iso_region}")
    return {
        "state": state,
        "census_state_fips": state_fips,
        "census_county_fips": county_fips,
        "census_place_fips": place_fips,
        "nerc_region": nerc_region,
        "balancing_authority_code": balancing_authority,
        "balancing_authority_name": text(plant.get("Balancing Authority Name")),
        "iso_region": iso_region,
        "iso_zone": None,
        "location_tags": list(dict.fromkeys(tag for tag in tags if tag)),
    }


def build(plant_workbook, generator_workbook, generation_workbook, year):
    plants = pd.read_excel(plant_workbook, sheet_name="Plant", header=1)
    generators = pd.read_excel(generator_workbook, sheet_name="Operable", header=1)
    generation = pd.read_excel(
        generation_workbook,
        sheet_name="Page 1 Generation and Fuel Data",
        header=5,
    )
    county_index, place_index = census_indexes()

    generator_summary = {}
    for plant_code, rows in generators.groupby("Plant Code"):
        capacity = pd.to_numeric(rows["Nameplate Capacity (MW)"], errors="coerce")
        technology_capacity = (
            rows.assign(_capacity=capacity)
            .groupby("Technology", dropna=True)["_capacity"]
            .sum()
            .sort_values(ascending=False)
        )
        operating_years = pd.to_numeric(rows["Operating Year"], errors="coerce").dropna()
        status_codes = sorted({str(value).strip() for value in rows["Status"].dropna() if str(value).strip()})
        development_status, status_tags = plant_status_metadata(status_codes)
        generator_summary[int(plant_code)] = {
            "nameplate_capacity_mw": clean_number(capacity.sum()),
            "generator_count": int(len(rows)),
            "primary_technology": str(technology_capacity.index[0]) if len(technology_capacity) else None,
            "technology_tags": [str(value) for value in technology_capacity.index],
            "energy_source_codes": sorted({str(value).strip() for value in rows["Energy Source 1"].dropna() if str(value).strip()}),
            "year_built": int(operating_years.min()) if len(operating_years) else None,
            "generator_status_codes": status_codes,
            "development_status": development_status,
            "status_tags": status_tags,
        }

    generation_summary = {}
    for plant_code, rows in generation.groupby("Plant Id"):
        net = pd.to_numeric(rows["Net Generation\n(Megawatthours)"], errors="coerce")
        fuel_rows = rows.assign(_net=net.fillna(0)).sort_values("_net", ascending=False)
        generation_summary[int(plant_code)] = {
            "net_generation_mwh": clean_number(net.sum(min_count=1)),
            "generation_fuel_codes": list(dict.fromkeys(
                str(value).strip()
                for value in fuel_rows["Reported\nFuel Type Code"].dropna()
                if str(value).strip()
            )),
        }

    records = []
    for _, plant in plants.sort_values(["State", "County", "Plant Name"]).iterrows():
        plant_code = int(plant["Plant Code"])
        generator = generator_summary.get(plant_code)
        latitude = number(plant["Latitude"], 6)
        longitude = number(plant["Longitude"], 6)
        if not generator or latitude is None or longitude is None:
            continue
        produced = generation_summary.get(plant_code, {})
        location = record_location_metadata(plant, county_index, place_index)
        record = {
            "id": f"eia-{plant_code}",
            "record_type": "power_plant",
            "inventory_scope": "United States",
            "eia_plant_code": plant_code,
            "name": text(plant["Plant Name"]),
            "operator": text(plant["Utility Name"]),
            "street_address": text(plant["Street Address"]),
            "city": text(plant["City"]),
            "county": text(plant["County"]),
            "postal_code": text(plant["Zip"]),
            "latitude": latitude,
            "longitude": longitude,
            **location,
            **generator,
            **produced,
            "primary_energy_source_code": (
                (produced.get("generation_fuel_codes") or generator["energy_source_codes"] or [None])[0]
            ),
            "generation_year": year,
            "year_built_status": "documented" if generator["year_built"] else "unknown",
            "year_built_basis": "Earliest operating year among operable generators in final EIA-860.",
            "year_built_source_ids": [f"eia-860-{year}-final"],
            "status_source_ids": [f"eia-860-{year}-final"],
            "capacity_source_id": f"eia-860-{year}-final",
            "generation_source_id": f"eia-923-{year}-final",
            "source_ids": [f"eia-860-{year}-final", f"eia-923-{year}-final"],
            "permit_status": "not researched in nationwide EIA baseline",
            "air_permit_status": "not researched in nationwide EIA baseline",
            "legal_status": "not researched in nationwide EIA baseline",
        }
        records.append(enrich_power_plant_planning_output(record))

    add_coordinate_confidence(records)
    compact_omissions = (
        "inventory_scope",
        "year_built_source_ids",
        "status_source_ids",
        "capacity_source_id",
        "generation_source_id",
        "planning_output_basis",
        "planning_output_source_id",
        "permit_status",
        "air_permit_status",
        "legal_status",
        "iso_zone",
    )
    for record in records:
        for field in compact_omissions:
            record.pop(field, None)
    state_counts = Counter(record["state"] for record in records)
    features = [
        {
            "type": "Feature",
            "id": record["id"],
            "geometry": {"type": "Point", "coordinates": [record["longitude"], record["latitude"]]},
            "properties": {
                key: value for key, value in record.items()
                if key not in {"latitude", "longitude"}
            },
        }
        for record in records
    ]
    return {
        "type": "FeatureCollection",
        "metadata": {
            "inventory": "final annual EIA nationwide operable power plants",
            "year": year,
            "record_count": len(records),
            "state_counts": dict(sorted(state_counts.items())),
            "source_urls": [EIA_860_URL, EIA_923_URL, PLACE_URL, COUNTY_URL],
        },
        "features": features,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plant-workbook", type=Path)
    parser.add_argument("--generator-workbook", type=Path)
    parser.add_argument("--generation-workbook", type=Path)
    parser.add_argument("--year", type=int, default=2024)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    supplied = (args.plant_workbook, args.generator_workbook, args.generation_workbook)
    if any(supplied) and not all(supplied):
        parser.error("provide all three workbook paths or omit them to download official EIA archives")
    with tempfile.TemporaryDirectory(prefix="codecollective-eia-") as temp_directory:
        workbooks = supplied if all(supplied) else download_eia_workbooks(Path(temp_directory))
        data = build(*workbooks, args.year)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    metadata = json.dumps(data["metadata"], ensure_ascii=False, separators=(",", ":"))
    features = ",\n".join(
        json.dumps(feature, ensure_ascii=False, separators=(",", ":"))
        for feature in data["features"]
    )
    args.output.write_text(f'{{"type":"FeatureCollection","metadata":{metadata},"features":[\n{features}\n]}}\n')
    print(f"Wrote {len(data['features'])} nationwide plants to {args.output}")


if __name__ == "__main__":
    main()
