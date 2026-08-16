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
DEFAULT_INFRASTRUCTURE = ROOT / "datacenters" / "data" / "infrastructure.json"
DEFAULT_OUTPUT = ROOT / "datacenters" / "data" / "power-estimates.json"

CENSUS_REPORTER_ACS_URL = "https://api.censusreporter.org/1.0/data/show/latest"
TIGERWEB_COUNTY_QUERY = (
    "https://tigerweb.geo.census.gov/arcgis/rest/services/"
    "TIGERweb/State_County/MapServer/1/query"
)
TIGERWEB_COUNTY_URL = TIGERWEB_COUNTY_QUERY.removesuffix("/query")
ACS_B25003_URL = "https://api.census.gov/data/2024/acs/acs5/groups/B25003.html"
ACS_B23025_URL = "https://api.census.gov/data/2024/acs/acs5/groups/B23025.html"
EIA_RETAIL_API_URL = "https://api.eia.gov/v2/electricity/retail-sales/data/"
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


def fetch_eia_state_retail_sales(year: int) -> dict[str, dict]:
    data = fetch_json(
        EIA_RETAIL_API_URL,
        params={
            "api_key": "DEMO_KEY",
            "frequency": "annual",
            "data[0]": "sales",
            "data[1]": "customers",
            "data[2]": "price",
            "facets[stateid][]": "MD",
            "start": str(year),
            "end": str(year),
            "length": "5000",
        },
    )
    by_sector: dict[str, dict] = {}
    for row in data.get("response", {}).get("data", []):
        sector = row.get("sectorid")
        if not sector:
            continue
        by_sector[sector] = row
    required = ["ALL", "RES", "COM", "IND", "TRA"]
    missing = [sector for sector in required if sector not in by_sector]
    if missing:
        raise RuntimeError(f"EIA retail-sales response missing sectors: {', '.join(missing)}")
    return by_sector


def fetch_county_demographics() -> tuple[dict[str, dict], dict]:
    data = fetch_json(
        CENSUS_REPORTER_ACS_URL,
        params={"table_ids": "B25003,B23025", "geo_ids": "050|04000US24"},
    )
    demographics: dict[str, dict] = {}
    for reporter_geoid, tables in data.get("data", {}).items():
        geoid = reporter_geoid.removeprefix("05000US")
        households = tables.get("B25003", {}).get("estimate", {}).get("B25003001")
        employed = tables.get("B23025", {}).get("estimate", {}).get("B23025004")
        labor_force = tables.get("B23025", {}).get("estimate", {}).get("B23025002")
        if not geoid or households is None or employed is None:
            continue
        geography = data.get("geography", {}).get(reporter_geoid, {})
        demographics[geoid] = {
            "occupied_housing_units": int(round(float(households))),
            "employed_population": int(round(float(employed))),
            "civilian_labor_force": int(round(float(labor_force))) if labor_force is not None else None,
            "acs_name": geography.get("name"),
            "acs_geoid": reporter_geoid,
        }
    if len(demographics) != 24:
        raise RuntimeError(f"expected 24 Maryland county equivalents from ACS, got {len(demographics)}")
    release = data.get("release", {})
    return demographics, release


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


def load_infrastructure_context(path: Path) -> dict[str, dict]:
    context: dict[str, dict] = {}
    if not path.exists():
        return context
    records = json.loads(path.read_text())
    for record in records:
        county = record.get("county")
        if not county:
            continue
        bucket = context.setdefault(county, {
            "power_plant_count": 0,
            "power_plant_nameplate_capacity_mw": 0.0,
            "power_plant_net_generation_mwh": 0.0,
            "data_center_count": 0,
            "planned_data_center_count": 0,
            "planned_data_center_projected_mw": 0.0,
        })
        if record.get("record_type") == "power_plant":
            bucket["power_plant_count"] += 1
            bucket["power_plant_nameplate_capacity_mw"] += float(record.get("nameplate_capacity_mw") or 0)
            bucket["power_plant_net_generation_mwh"] += float(record.get("net_generation_mwh") or 0)
        elif record.get("record_type") == "data_center":
            bucket["data_center_count"] += 1
            projected = record.get("projected_power_demand_mw")
            if isinstance(projected, (int, float)):
                bucket["planned_data_center_count"] += 1
                bucket["planned_data_center_projected_mw"] += float(projected)
    return context


def eia_sales_mwh(row: dict) -> float:
    value = row.get("sales")
    return float(value) * 1000 if value is not None else 0.0


def estimate_county_power(rates: dict, demographics: dict[str, dict], geometry: dict, retail_sales: dict[str, dict], infrastructure_context: dict[str, dict]) -> dict:
    statewide_sales_mwh = float(rates["residential_sales_million_kwh"]) * 1000
    statewide_all_sector_sales_mwh = eia_sales_mwh(retail_sales["ALL"])
    statewide_nonresidential_sales_mwh = max(0.0, statewide_all_sector_sales_mwh - statewide_sales_mwh)
    statewide_customers = int(rates["residential_customer_count"])
    statewide_price = float(rates["average_price_cents_per_kwh"])
    statewide_all_sector_price = float(retail_sales["ALL"]["price"])
    total_occupied_units = sum(item["occupied_housing_units"] for item in demographics.values())
    total_employed_population = sum(item["employed_population"] for item in demographics.values())
    if total_occupied_units <= 0:
        raise RuntimeError("ACS occupied-housing total is not positive")
    if total_employed_population <= 0:
        raise RuntimeError("ACS employed-population total is not positive")

    features = []
    for feature in geometry.get("features", []):
        properties = dict(feature.get("properties", {}))
        geoid = str(properties.get("GEOID", ""))
        acs = demographics.get(geoid)
        if not acs:
            continue
        residential_share = acs["occupied_housing_units"] / total_occupied_units
        nonresidential_share = acs["employed_population"] / total_employed_population
        residential_annual_mwh = statewide_sales_mwh * residential_share
        nonresidential_annual_mwh = statewide_nonresidential_sales_mwh * nonresidential_share
        total_annual_mwh = residential_annual_mwh + nonresidential_annual_mwh
        residential_average_mw = residential_annual_mwh / HOURS_IN_2024
        nonresidential_average_mw = nonresidential_annual_mwh / HOURS_IN_2024
        total_average_mw = total_annual_mwh / HOURS_IN_2024
        county_name = properties.get("NAME") or acs.get("acs_name") or geoid
        context = infrastructure_context.get(county_name, {})
        generation_mwh = float(context.get("power_plant_net_generation_mwh") or 0)
        generation_average_mw = generation_mwh / HOURS_IN_2024
        projected_datacenter_mw = float(context.get("planned_data_center_projected_mw") or 0)
        estimated_customers = statewide_customers * residential_share
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
            "employed_population": acs["employed_population"],
            "civilian_labor_force": acs["civilian_labor_force"],
            "estimated_residential_customers": round(estimated_customers),
            "estimated_residential_annual_mwh": round(residential_annual_mwh, 1),
            "estimated_residential_average_mw": round(residential_average_mw, 2),
            "estimated_residential_monthly_mwh": round(residential_annual_mwh / 12, 1),
            "estimated_residential_daily_mwh": round(residential_annual_mwh / 366, 1),
            "estimated_nonresidential_annual_mwh": round(nonresidential_annual_mwh, 1),
            "estimated_nonresidential_average_mw": round(nonresidential_average_mw, 2),
            "estimated_total_annual_mwh": round(total_annual_mwh, 1),
            "estimated_total_average_mw": round(total_average_mw, 2),
            "estimated_total_monthly_mwh": round(total_annual_mwh / 12, 1),
            "estimated_total_daily_mwh": round(total_annual_mwh / 366, 1),
            "estimated_share_percent": round(residential_share * 100, 3),
            "estimated_nonresidential_share_percent": round(nonresidential_share * 100, 3),
            "estimated_total_share_percent": round((total_annual_mwh / statewide_all_sector_sales_mwh) * 100, 3),
            "statewide_residential_sales_mwh": round(statewide_sales_mwh, 1),
            "statewide_residential_average_mw": round(statewide_sales_mwh / HOURS_IN_2024, 2),
            "statewide_residential_customers": statewide_customers,
            "statewide_residential_price_cents_kwh": statewide_price,
            "statewide_all_sector_sales_mwh": round(statewide_all_sector_sales_mwh, 1),
            "statewide_all_sector_average_mw": round(statewide_all_sector_sales_mwh / HOURS_IN_2024, 2),
            "statewide_nonresidential_sales_mwh": round(statewide_nonresidential_sales_mwh, 1),
            "statewide_all_sector_price_cents_kwh": statewide_all_sector_price,
            "county_power_plant_count": int(context.get("power_plant_count") or 0),
            "county_power_plant_nameplate_capacity_mw": round(float(context.get("power_plant_nameplate_capacity_mw") or 0), 2),
            "county_power_plant_generation_mwh": round(generation_mwh, 1),
            "county_power_plant_average_generation_mw": round(generation_average_mw, 2),
            "county_data_center_count": int(context.get("data_center_count") or 0),
            "county_planned_data_center_count": int(context.get("planned_data_center_count") or 0),
            "county_planned_data_center_projected_mw": round(projected_datacenter_mw, 2),
            "estimated_total_with_projected_datacenters_average_mw": round(total_average_mw + projected_datacenter_mw, 2),
            "estimated_generation_minus_total_load_average_mw": round(generation_average_mw - total_average_mw, 2),
            "estimated_generation_minus_total_with_projected_datacenters_average_mw": round(generation_average_mw - total_average_mw - projected_datacenter_mw, 2),
            "estimate_basis": (
                "Estimated county residential demand: EIA statewide 2024 residential sales "
                "allocated by ACS 2024 occupied housing units; not utility-metered county load."
            ),
            "total_estimate_basis": (
                "Estimated county all-sector demand: EIA statewide 2024 total retail sales split into residential "
                "and non-residential components. Residential is allocated by ACS occupied housing units; the "
                "non-residential remainder is allocated by ACS employed resident population. This is a planning "
                "proxy, not utility-metered county load or coincident peak demand."
            ),
            "planning_context_basis": (
                "Power-plant generation and planned data-center demand are summed from the local flat inventory. "
                "Generation is annual EIA net generation divided by 8,784 hours. Planned data-center additions are "
                "projected demand records and are shown separately to avoid treating proposed load as 2024 metered use."
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
                "Allocate EIA statewide annual residential electricity sales to Maryland county equivalents using "
                "ACS occupied housing units as the residential-customer proxy. Allocate the non-residential remainder "
                "of EIA statewide all-sector retail sales using ACS employed resident population as a planning proxy."
            ),
            "estimate_scope": (
                "Planning context only. The figures are not utility-metered county load, feeder load, workplace load, "
                "coincident peak demand, or a tariff quote. Planned data-center additions are shown separately."
            ),
            "statewide_residential_sales_mwh": round(statewide_sales_mwh, 1),
            "statewide_residential_average_mw": round(statewide_sales_mwh / HOURS_IN_2024, 2),
            "statewide_residential_customer_count": statewide_customers,
            "statewide_all_sector_sales_mwh": round(statewide_all_sector_sales_mwh, 1),
            "statewide_all_sector_average_mw": round(statewide_all_sector_sales_mwh / HOURS_IN_2024, 2),
            "statewide_nonresidential_sales_mwh": round(statewide_nonresidential_sales_mwh, 1),
            "statewide_average_price_cents_per_kwh": statewide_price,
            "statewide_all_sector_average_price_cents_per_kwh": statewide_all_sector_price,
            "acs_occupied_housing_units_total": total_occupied_units,
            "acs_employed_population_total": total_employed_population,
            "hours_in_year": HOURS_IN_2024,
            "sources": [
                {"label": "EIA Maryland residential and all-sector retail electricity records", "url": EIA_RETAIL_API_URL},
                {"label": "Census Reporter ACS tables B25003 and B23025", "url": CENSUS_REPORTER_ACS_URL},
                {"label": "U.S. Census Bureau TIGERweb county boundaries", "url": TIGERWEB_COUNTY_URL},
                {"label": "ACS B25003 occupied housing units", "url": ACS_B25003_URL},
                {"label": "ACS B23025 employment status", "url": ACS_B23025_URL},
            ],
        },
        "features": features,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rates", type=Path, default=DEFAULT_RATES)
    parser.add_argument("--infrastructure", type=Path, default=DEFAULT_INFRASTRUCTURE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    if os.environ.get("CENSUS_API_KEY"):
        # Reserved for future direct Census API usage; Census Reporter remains
        # the no-key path so the script is easy to run in CI and review.
        pass
    rates = load_rates(args.rates)
    retail_sales = fetch_eia_state_retail_sales(int(rates["year"]))
    demographics, _release = fetch_county_demographics()
    geometry = fetch_county_geometry()
    infrastructure_context = load_infrastructure_context(args.infrastructure)
    collection = estimate_county_power(rates, demographics, geometry, retail_sales, infrastructure_context)
    args.output.write_text(json.dumps(collection, indent=2, sort_keys=True) + "\n")
    print(f"wrote {args.output} with {len(collection['features'])} county estimate features")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
