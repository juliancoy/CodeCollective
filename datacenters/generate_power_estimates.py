#!/usr/bin/env python3
"""Generate derived Maryland county electricity-demand estimate layers.

This layer is intentionally an estimate. EIA publishes reliable statewide
residential electricity sales and customer counts. ACS publishes county occupied
housing units. The generator allocates the statewide residential total across
Maryland county equivalents by ACS occupied-housing share so the map can show a
usable demand context without implying county-level metered load.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import date
from pathlib import Path

import requests


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RATES = ROOT / "datacenters" / "data" / "residential-electricity-rates.json"
DEFAULT_OUTPUT = ROOT / "datacenters" / "data" / "power-estimates.json"

CENSUS_REPORTER_ACS_URL = "https://api.censusreporter.org/1.0/data/show/latest"
TIGERWEB_COUNTY_QUERY = (
    "https://tigerweb.geo.census.gov/arcgis/rest/services/"
    "TIGERweb/State_County/MapServer/1/query"
)
TIGERWEB_COUNTY_URL = TIGERWEB_COUNTY_QUERY.removesuffix("/query")
ACS_B25003_URL = "https://api.census.gov/data/2024/acs/acs5/groups/B25003.html"
EIA_RETAIL_URL = "https://www.eia.gov/electricity/data/browser/#/topic/7"
HOURS_IN_2024 = 8784


def fetch_json(url: str, *, params: dict[str, str] | None = None) -> dict:
    headers = {"User-Agent": "CodeCollective Maryland data-center map generator"}
    response = requests.get(url, params=params, headers=headers, timeout=90)
    response.raise_for_status()
    data = response.json()
    if isinstance(data, dict) and data.get("error"):
      raise RuntimeError(data["error"].get("message", "public data request failed"))
    return data


def load_rates(path: Path) -> dict:
    records = json.loads(path.read_text())
    if not records:
        raise RuntimeError(f"{path} has no residential rate record")
    record = records[0]
    required = [
        "year",
        "average_price_cents_per_kwh",
        "residential_sales_million_kwh",
        "residential_customer_count",
    ]
    missing = [field for field in required if record.get(field) is None]
    if missing:
        raise RuntimeError(f"{path} is missing required fields: {', '.join(missing)}")
    return record


def fetch_county_households() -> tuple[dict[str, dict], dict]:
    data = fetch_json(
        CENSUS_REPORTER_ACS_URL,
        params={"table_ids": "B25003", "geo_ids": "050|04000US24"},
    )
    households: dict[str, dict] = {}
    for reporter_geoid, tables in data.get("data", {}).items():
        geoid = reporter_geoid.removeprefix("05000US")
        value = tables.get("B25003", {}).get("estimate", {}).get("B25003001")
        if not geoid or value is None:
            continue
        geography = data.get("geography", {}).get(reporter_geoid, {})
        households[geoid] = {
            "occupied_housing_units": int(round(float(value))),
            "acs_name": geography.get("name"),
            "acs_geoid": reporter_geoid,
        }
    if len(households) != 24:
        raise RuntimeError(f"expected 24 Maryland county equivalents from ACS, got {len(households)}")
    release = data.get("release", {})
    return households, release


def fetch_county_geometry() -> dict:
    return fetch_json(
        TIGERWEB_COUNTY_QUERY,
        params={
            "where": "STATE='24'",
            "outFields": "STATE,COUNTY,BASENAME,NAME,GEOID,CENTLAT,CENTLON,AREALAND,AREAWATER",
            "returnGeometry": "true",
            "outSR": "4326",
            "geometryPrecision": "4",
            "resultRecordCount": "100",
            "f": "geojson",
        },
    )


def estimate_county_power(rates: dict, households: dict[str, dict], geometry: dict) -> dict:
    statewide_sales_mwh = float(rates["residential_sales_million_kwh"]) * 1000
    statewide_customers = int(rates["residential_customer_count"])
    statewide_price = float(rates["average_price_cents_per_kwh"])
    total_occupied_units = sum(item["occupied_housing_units"] for item in households.values())
    if total_occupied_units <= 0:
        raise RuntimeError("ACS occupied-housing total is not positive")

    features = []
    for feature in geometry.get("features", []):
        properties = dict(feature.get("properties", {}))
        geoid = str(properties.get("GEOID", ""))
        acs = households.get(geoid)
        if not acs:
            continue
        share = acs["occupied_housing_units"] / total_occupied_units
        annual_mwh = statewide_sales_mwh * share
        average_mw = annual_mwh / HOURS_IN_2024
        county_name = properties.get("NAME") or acs.get("acs_name") or geoid
        estimated_customers = statewide_customers * share
        feature["properties"] = {
            "id": f"md-county-power-estimate-{geoid}",
            "record_type": "county_power_estimate",
            "county": county_name,
            "county_basename": properties.get("BASENAME"),
            "state": "Maryland",
            "state_abbrev": "MD",
            "geoid": geoid,
            "county_fips": properties.get("COUNTY"),
            "source_year": int(rates["year"]),
            "acs_release": "ACS 2024 5-year",
            "occupied_housing_units": acs["occupied_housing_units"],
            "estimated_residential_customers": round(estimated_customers),
            "estimated_residential_annual_mwh": round(annual_mwh, 1),
            "estimated_residential_average_mw": round(average_mw, 2),
            "estimated_residential_monthly_mwh": round(annual_mwh / 12, 1),
            "estimated_residential_daily_mwh": round(annual_mwh / 366, 1),
            "estimated_share_percent": round(share * 100, 3),
            "statewide_residential_sales_mwh": round(statewide_sales_mwh, 1),
            "statewide_residential_average_mw": round(statewide_sales_mwh / HOURS_IN_2024, 2),
            "statewide_residential_customers": statewide_customers,
            "statewide_residential_price_cents_kwh": statewide_price,
            "estimate_basis": (
                "Estimated county residential demand: EIA statewide 2024 residential sales "
                "allocated by ACS 2024 occupied housing units; not utility-metered county load."
            ),
            "centroid_latitude": float(properties["CENTLAT"]) if properties.get("CENTLAT") else None,
            "centroid_longitude": float(properties["CENTLON"]) if properties.get("CENTLON") else None,
            "land_area_square_meters": int(properties["AREALAND"]) if properties.get("AREALAND") else None,
            "water_area_square_meters": int(properties["AREAWATER"]) if properties.get("AREAWATER") else None,
        }
        features.append(feature)
    if len(features) != 24:
        raise RuntimeError(f"expected 24 estimated county features, got {len(features)}")
    features.sort(key=lambda item: item["properties"]["county"])
    return {
        "type": "FeatureCollection",
        "metadata": {
            "title": "Maryland county residential electricity demand estimates",
            "generated_date": date.today().isoformat(),
            "state": "Maryland",
            "source_year": int(rates["year"]),
            "county_equivalent_count": len(features),
            "method": (
                "Allocate EIA statewide annual residential electricity sales to Maryland county "
                "equivalents using ACS occupied housing units as the residential-customer proxy."
            ),
            "estimate_scope": (
                "Planning context only. The figures are not utility-metered county load, feeder "
                "load, coincident peak demand, or a tariff quote."
            ),
            "statewide_residential_sales_mwh": round(statewide_sales_mwh, 1),
            "statewide_residential_average_mw": round(statewide_sales_mwh / HOURS_IN_2024, 2),
            "statewide_residential_customer_count": statewide_customers,
            "statewide_average_price_cents_per_kwh": statewide_price,
            "acs_occupied_housing_units_total": total_occupied_units,
            "hours_in_year": HOURS_IN_2024,
            "sources": [
                {"label": "EIA Maryland residential retail electricity record", "url": EIA_RETAIL_URL},
                {"label": "Census Reporter ACS table B25003", "url": CENSUS_REPORTER_ACS_URL},
                {"label": "U.S. Census Bureau TIGERweb county boundaries", "url": TIGERWEB_COUNTY_URL},
                {"label": "ACS B25003 occupied housing units", "url": ACS_B25003_URL},
            ],
        },
        "features": features,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rates", type=Path, default=DEFAULT_RATES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    if os.environ.get("CENSUS_API_KEY"):
        # Reserved for future direct Census API usage; Census Reporter remains
        # the no-key path so the script is easy to run in CI and review.
        pass
    rates = load_rates(args.rates)
    households, _release = fetch_county_households()
    geometry = fetch_county_geometry()
    collection = estimate_county_power(rates, households, geometry)
    args.output.write_text(json.dumps(collection, indent=2, sort_keys=True) + "\n")
    print(f"wrote {args.output} with {len(collection['features'])} county estimate features")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
