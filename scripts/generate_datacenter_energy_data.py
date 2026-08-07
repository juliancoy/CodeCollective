#!/usr/bin/env python3
"""Build the data-center map's EIA-derived JSON files.

The EIA workbooks are intentionally not committed because each archive is over
20 MB. Download the final annual EIA-860 and EIA-923 archives, extract them,
and pass their plant, generator, and generation/fuel workbooks to this script.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import pandas as pd


def clean_number(value, digits=3):
    if pd.isna(value):
        return None
    return round(float(value), digits)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plant-workbook", required=True, type=Path)
    parser.add_argument("--generator-workbook", required=True, type=Path)
    parser.add_argument("--generation-workbook", required=True, type=Path)
    parser.add_argument("--year", required=True, type=int)
    parser.add_argument("--state", default="MD")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    plants = pd.read_excel(args.plant_workbook, sheet_name="Plant", header=1)
    generators = pd.read_excel(args.generator_workbook, sheet_name="Operable", header=1)
    generation = pd.read_excel(
        args.generation_workbook,
        sheet_name="Page 1 Generation and Fuel Data",
        header=5,
    )

    plants = plants[plants["State"] == args.state].copy()
    generators = generators[generators["State"] == args.state].copy()
    generation = generation[generation["Plant State"] == args.state].copy()

    generator_summary = {}
    for plant_code, rows in generators.groupby("Plant Code"):
        capacity = pd.to_numeric(rows["Nameplate Capacity (MW)"], errors="coerce")
        technology_capacity = (
            rows.assign(_capacity=capacity)
            .groupby("Technology", dropna=True)["_capacity"]
            .sum()
            .sort_values(ascending=False)
        )
        primary_technology = technology_capacity.index[0] if len(technology_capacity) else None
        fuels = [str(value) for value in rows["Energy Source 1"].dropna() if str(value).strip()]
        generator_summary[int(plant_code)] = {
            "nameplate_capacity_mw": clean_number(capacity.sum()),
            "generator_count": int(len(rows)),
            "primary_technology": primary_technology,
            "energy_source_codes": sorted(set(fuels)),
        }

    generation_summary = {}
    for plant_code, rows in generation.groupby("Plant Id"):
        net = pd.to_numeric(rows["Net Generation\n(Megawatthours)"], errors="coerce")
        fuel_rows = rows.assign(_net=net.fillna(0)).sort_values("_net", ascending=False)
        fuel_codes = [
            str(value)
            for value in fuel_rows["Reported\nFuel Type Code"].dropna()
            if str(value).strip()
        ]
        generation_summary[int(plant_code)] = {
            "net_generation_mwh": clean_number(net.sum(min_count=1)),
            "reported_fuel_codes": list(dict.fromkeys(fuel_codes)),
        }

    records = []
    for _, plant in plants.sort_values(["County", "Plant Name"]).iterrows():
        plant_code = int(plant["Plant Code"])
        generator = generator_summary.get(plant_code, {})
        produced = generation_summary.get(plant_code, {})
        if not generator:
            continue
        records.append(
            {
                "id": f"eia-{plant_code}",
                "record_type": "power_plant",
                "eia_plant_code": plant_code,
                "name": str(plant["Plant Name"]).strip(),
                "operator": str(plant["Utility Name"]).strip(),
                "street_address": None if pd.isna(plant["Street Address"]) else str(plant["Street Address"]).strip(),
                "city": None if pd.isna(plant["City"]) else str(plant["City"]).strip(),
                "county": None if pd.isna(plant["County"]) else str(plant["County"]).strip(),
                "state": args.state,
                "postal_code": None if pd.isna(plant["Zip"]) else str(plant["Zip"]).strip(),
                "latitude": clean_number(plant["Latitude"], 6),
                "longitude": clean_number(plant["Longitude"], 6),
                "primary_technology": generator.get("primary_technology"),
                "energy_source_codes": generator.get("energy_source_codes", []),
                "nameplate_capacity_mw": generator.get("nameplate_capacity_mw"),
                "generator_count": generator.get("generator_count"),
                "net_generation_mwh": produced.get("net_generation_mwh"),
                "generation_year": args.year,
                "generation_fuel_codes": produced.get("reported_fuel_codes", []),
                "capacity_source_id": f"eia-860-{args.year}-final",
                "generation_source_id": f"eia-923-{args.year}-final",
            }
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(records, indent=2, ensure_ascii=False) + "\n")
    technologies = Counter(record["primary_technology"] for record in records)
    print(f"Wrote {len(records)} plants to {args.output}")
    print("Technologies:", dict(technologies.most_common()))


if __name__ == "__main__":
    main()
