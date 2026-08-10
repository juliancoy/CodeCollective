#!/usr/bin/env python3
"""Generate Maryland transmission-boundary interchange points from official data.

The physical crossing locations come from the 2024 HIFLD transmission network
intersected with Maryland iMAP's official state boundary. EIA publishes only
statewide net interstate trade, not metered direction or MW for each circuit.
Consequently every point is labeled as a bidirectional interchange corridor and
the statewide flow is kept in separate aggregate fields.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import requests
from shapely.geometry import Point, shape


MARYLAND_BOUNDARY_QUERY = (
    "https://mdgeodata.md.gov/imap/rest/services/Boundaries/"
    "MD_PoliticalBoundaries/FeatureServer/0/query"
)
HIFLD_TRANSMISSION_QUERY = (
    "https://services2.arcgis.com/FiaPA4ga0iQKduv3/arcgis/rest/services/"
    "US_Electric_Power_Transmission_Lines/FeatureServer/0/query"
)
CENSUS_STATE_QUERY = (
    "https://tigerweb.geo.census.gov/arcgis/rest/services/"
    "TIGERweb/State_County/MapServer/0/query"
)
CENSUS_STATE_URL = CENSUS_STATE_QUERY.removesuffix("/query")
EIA_STATE_TABLES_URL = "https://www.eia.gov/electricity/state/maryland/state_tables.php"
PJM_STATE_REPORT_URL = (
    "https://www.pjm.com/-/media/DotCom/library/reports-notices/"
    "state-specific-reports/2025/maryland-dc.pdf"
)
HIFLD_ITEM_URL = "https://www.arcgis.com/home/item.html?id=d4090758322c4d32a4cd002ffaa0aa12"
MARYLAND_BOUNDARY_URL = MARYLAND_BOUNDARY_QUERY.removesuffix("/query")

# EIA State Electricity Profile table 10. A negative value is a net import.
EIA_FLOW_YEAR = 2024
EIA_NET_INTERSTATE_TRADE_MWH = -27_111_098
CLUSTER_DISTANCE_KM = 0.12

VOLTAGE_CLASS_PROXY_KV = {
    "Under 100": 69,
    "100-161": 138,
    "220-287": 230,
    "345": 345,
    "500": 500,
    "735 And Above": 735,
    "DC": 500,
    "Dc": 500,
}


def fetch_geojson(url: str, parameters: dict[str, str]) -> dict:
    response = requests.get(url, params=parameters, timeout=90)
    response.raise_for_status()
    data = response.json()
    if data.get("error"):
        raise RuntimeError(data["error"].get("message", "ArcGIS query failed"))
    return data


def point_parts(geometry):
    if geometry.is_empty:
        return []
    if geometry.geom_type == "Point":
        return [geometry]
    if geometry.geom_type in {"MultiPoint", "GeometryCollection"}:
        return [part for part in geometry.geoms if part.geom_type == "Point"]
    return []


def distance_km(left: Point, right: Point) -> float:
    latitude = math.radians((left.y + right.y) / 2)
    dx = (left.x - right.x) * 111.32 * math.cos(latitude)
    dy = (left.y - right.y) * 110.57
    return math.hypot(dx, dy)


def inward_axis_rotation(boundary_point: Point, maryland) -> float:
    best = None
    for bearing in range(0, 360, 5):
        radians = math.radians(bearing)
        candidate = Point(
            boundary_point.x + math.sin(radians) * 0.025 / max(math.cos(math.radians(boundary_point.y)), 0.2),
            boundary_point.y + math.cos(radians) * 0.025,
        )
        if not maryland.contains(candidate):
            continue
        score = candidate.distance(maryland.boundary)
        if best is None or score > best[0]:
            best = (score, bearing)
    inward_bearing = best[1] if best else 0
    return round(inward_bearing - 90, 1)


def clean_values(records: list[dict], field: str, unknown=None) -> list[str]:
    values = []
    for record in records:
        value = record.get(field)
        if value in (None, "", -999999, "-999999") or value == unknown:
            continue
        text = str(value).strip()
        if text not in values:
            values.append(text)
    return sorted(values)


def voltage_proxy_kv(line: dict) -> float:
    voltage = line.get("VOLTAGE")
    try:
        value = float(voltage)
        if value > 0:
            return value
    except (TypeError, ValueError):
        pass
    voltage_class = str(line.get("VOLT_CLASS") or "").strip()
    return VOLTAGE_CLASS_PROXY_KV.get(voltage_class, 138)


def crossing_flow_weight(lines: list[dict]) -> float:
    return sum(voltage_proxy_kv(line) for line in lines) or len(lines) or 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parent / "data" / "power-interchanges.json",
    )
    args = parser.parse_args()

    boundary_data = fetch_geojson(MARYLAND_BOUNDARY_QUERY, {
        "where": "1=1", "outFields": "State", "returnGeometry": "true",
        "outSR": "4326", "geometryPrecision": "7", "f": "geojson",
    })
    maryland = shape(boundary_data["features"][0]["geometry"])
    bounds = ",".join(str(value) for value in maryland.bounds)
    transmission_data = fetch_geojson(HIFLD_TRANSMISSION_QUERY, {
        "where": "1=1", "geometry": bounds, "geometryType": "esriGeometryEnvelope",
        "inSR": "4326", "spatialRel": "esriSpatialRelIntersects",
        "outFields": "ID,TYPE,STATUS,OWNER,VOLTAGE,VOLT_CLASS,INFERRED,SUB_1,SUB_2,SOURCE,SOURCEDATE,VAL_METHOD,VAL_DATE",
        "returnGeometry": "true", "outSR": "4326", "geometryPrecision": "7",
        "resultRecordCount": "2000", "f": "geojson",
    })
    state_data = fetch_geojson(CENSUS_STATE_QUERY, {
        "where": "STUSAB IN ('PA','WV','VA','DC','DE')", "outFields": "STUSAB,NAME",
        "returnGeometry": "true", "outSR": "4326", "geometryPrecision": "6", "f": "geojson",
    })
    neighbors = [(feature["properties"]["NAME"], shape(feature["geometry"])) for feature in state_data["features"]]

    crossings = []
    for feature in transmission_data["features"]:
        line = shape(feature["geometry"])
        if line.intersection(maryland).length < 0.00001 or line.difference(maryland).length < 0.00001:
            continue
        for point in point_parts(line.intersection(maryland.boundary)):
            crossings.append({"point": point, "line": feature["properties"]})

    clusters: list[dict] = []
    for crossing in sorted(crossings, key=lambda item: (item["point"].x, item["point"].y, str(item["line"].get("ID")))):
        cluster = next((item for item in clusters if distance_km(item["point"], crossing["point"]) <= CLUSTER_DISTANCE_KM), None)
        if cluster:
            count = len(cluster["lines"])
            cluster["point"] = Point(
                (cluster["point"].x * count + crossing["point"].x) / (count + 1),
                (cluster["point"].y * count + crossing["point"].y) / (count + 1),
            )
            cluster["lines"].append(crossing["line"])
        else:
            clusters.append({"point": crossing["point"], "lines": [crossing["line"]]})

    net_import_mwh = abs(EIA_NET_INTERSTATE_TRADE_MWH)
    hours = 8784 if EIA_FLOW_YEAR % 4 == 0 else 8760
    feature_rows = []
    for index, cluster in enumerate(clusters, 1):
        point = cluster["point"]
        lines = cluster["lines"]
        neighbor = min(neighbors, key=lambda item: point.distance(item[1]))[0]
        voltages = clean_values(lines, "VOLTAGE")
        voltage_classes = clean_values(lines, "VOLT_CLASS")
        line_ids = clean_values(lines, "ID")
        owners = clean_values(lines, "OWNER", "NOT AVAILABLE")
        substations = clean_values(lines, "SUB_1") + clean_values(lines, "SUB_2")
        substations = sorted(set(value for value in substations if not value.startswith("UNKNOWN") and not value.startswith("TAP")))
        feature_rows.append({
            "weight": crossing_flow_weight(lines),
            "feature": {
            "type": "Feature",
            "id": f"md-interchange-{index:03d}",
            "geometry": {"type": "Point", "coordinates": [round(point.x, 6), round(point.y, 6)]},
            "properties": {
                "crossing_id": f"MD-X-{index:03d}",
                "name": f"{neighbor} / Maryland transmission crossing",
                "neighboring_jurisdiction": neighbor,
                "line_count": len(lines),
                "line_ids": "; ".join(line_ids) or "Not identified",
                "owners": "; ".join(owners) or "Not published",
                "voltage_kv": ", ".join(voltages) or "Not published",
                "voltage_classes": ", ".join(voltage_classes) or "Not published",
                "named_substations": "; ".join(substations) or "Not published",
                "flow_capability": "Bidirectional interstate interchange corridor",
                "line_flow_measurement": "Actual direction and MW are not published for this individual crossing",
                "statewide_flow_direction": "Net import",
                "statewide_net_import_mwh": net_import_mwh,
                "statewide_average_net_import_mw": round(net_import_mwh / hours, 1),
                "statewide_flow_year": EIA_FLOW_YEAR,
                "axis_rotation_degrees": inward_axis_rotation(point, maryland),
            },
            },
        })

    total_weight = sum(row["weight"] for row in feature_rows) or 1
    average_net_import_mw = net_import_mwh / hours
    features = []
    for row in feature_rows:
        feature = row["feature"]
        share = row["weight"] / total_weight
        estimated_mw = average_net_import_mw * share
        properties = feature["properties"]
        properties["estimated_average_interchange_mw"] = round(estimated_mw, 1)
        properties["estimated_interchange_share_percent"] = round(share * 100, 2)
        properties["estimated_interchange_weight"] = round(row["weight"], 1)
        properties["estimated_interchange_basis"] = (
            "Estimated allocation of Maryland's statewide 2024 average net import across mapped border crossings "
            "using HIFLD voltage proxy multiplied by co-located circuit count. This is a planning guess, not "
            "metered flow for this crossing."
        )
        features.append(feature)

    output = {
        "type": "FeatureCollection",
        "metadata": {
            "title": "Maryland electricity import/export transmission crossings",
            "generated_date": "2026-08-09",
            "crossing_definition": "HIFLD transmission lines that have geometry both inside and outside the official Maryland boundary",
            "corridor_count": len(features),
            "line_crossing_count": len(crossings),
            "cluster_distance_meters": int(CLUSTER_DISTANCE_KM * 1000),
            "flow_scope": "EIA statewide annual net interstate trade; not a measurement for any individual mapped line",
            "estimated_crossing_flow_method": (
                "Statewide average net import MW allocated across crossings in proportion to voltage-weighted "
                "co-located circuit count. Estimates are for visual planning only."
            ),
            "sources": [
                {"label": "HIFLD U.S. Electric Power Transmission Lines (2024)", "url": HIFLD_ITEM_URL},
                {"label": "Maryland iMAP State Boundary", "url": MARYLAND_BOUNDARY_URL},
                {"label": "U.S. Census Bureau TIGERweb State Boundaries", "url": CENSUS_STATE_URL},
                {"label": "EIA Maryland State Electricity Profile, table 10", "url": EIA_STATE_TABLES_URL},
                {"label": "PJM 2025 Maryland and D.C. State Infrastructure Report", "url": PJM_STATE_REPORT_URL},
            ],
        },
        "features": features,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2) + "\n")
    print(f"Wrote {len(features)} corridors covering {len(crossings)} line crossings to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
