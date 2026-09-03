#!/usr/bin/env python3
"""Build the publishable nationwide OpenStreetMap data-center inventory."""

from __future__ import annotations

import argparse
import json
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path


OUTPUT = Path(__file__).with_name("data") / "data-centers-openstreetmap-us.json"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
CENSUS_STATES_URL = (
    "https://tigerweb.geo.census.gov/arcgis/rest/services/"
    "TIGERweb/State_County/MapServer/0/query"
)
OSM_QUERY = """[out:json][timeout:300];
area["ISO3166-1"="US"][admin_level=2]->.us;
(
  nwr(area.us)["telecom"~"^data_cent(er|re)$"];
  nwr(area.us)["building"~"^data_cent(er|re)$"];
  nwr(area.us)["industrial"~"^data_cent(er|re)$"];
);
out center tags;"""
DATA_CENTER_TAGS = ("telecom", "building", "industrial")


def request_json(url, *, data=None, timeout=360):
    request = urllib.request.Request(
        url,
        data=data,
        headers={"User-Agent": "CodeCollective public map generator/1.0 (https://codecollective.us)"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def download_overpass():
    body = urllib.parse.urlencode({"data": OSM_QUERY}).encode()
    return request_json(OVERPASS_URL, data=body)


def download_census_states():
    parameters = urllib.parse.urlencode({
        "where": "1=1",
        "outFields": "*",
        "returnGeometry": "true",
        "outSR": "4326",
        "geometryPrecision": "5",
        "maxAllowableOffset": "0.001",
        "f": "geojson",
    })
    payload = request_json(f"{CENSUS_STATES_URL}?{parameters}", timeout=120)
    if payload.get("type") != "FeatureCollection" or not payload.get("features"):
        raise RuntimeError(f"Census state query failed: {payload.get('error') or 'empty response'}")
    return payload


def point_in_ring(longitude, latitude, ring):
    inside = False
    previous = ring[-1]
    for current in ring:
        x1, y1 = previous[:2]
        x2, y2 = current[:2]
        if (y1 > latitude) != (y2 > latitude):
            crossing = (x2 - x1) * (latitude - y1) / (y2 - y1) + x1
            if longitude < crossing:
                inside = not inside
        previous = current
    return inside


def point_in_polygon(longitude, latitude, rings):
    return bool(rings and point_in_ring(longitude, latitude, rings[0])
                and not any(point_in_ring(longitude, latitude, hole) for hole in rings[1:]))


def geometry_contains(geometry, longitude, latitude):
    if geometry.get("type") == "Polygon":
        return point_in_polygon(longitude, latitude, geometry.get("coordinates", []))
    if geometry.get("type") == "MultiPolygon":
        return any(point_in_polygon(longitude, latitude, polygon)
                   for polygon in geometry.get("coordinates", []))
    return False


def state_index(census_states):
    return [
        {
            "code": feature["properties"]["STUSAB"],
            "name": feature["properties"]["NAME"],
            "fips": feature["properties"]["GEOID"],
            "geometry": feature["geometry"],
        }
        for feature in census_states["features"]
    ]


def element_coordinates(element):
    if element.get("type") == "node":
        longitude, latitude = element.get("lon"), element.get("lat")
        method = "OpenStreetMap node"
    else:
        center = element.get("center") or {}
        longitude, latitude = center.get("lon"), center.get("lat")
        method = "OpenStreetMap geometry center"
    if not isinstance(longitude, (int, float)) or not isinstance(latitude, (int, float)):
        return None
    return round(longitude, 7), round(latitude, 7), method


def state_for_point(states, longitude, latitude, tagged_state=None):
    for state in states:
        if geometry_contains(state["geometry"], longitude, latitude):
            return state
    normalized = str(tagged_state or "").strip().upper()
    return next((state for state in states if state["code"] == normalized), None)


def clean(value):
    value = str(value or "").strip()
    return value or None


def joined_address(tags):
    street = " ".join(filter(None, [clean(tags.get("addr:housenumber")), clean(tags.get("addr:street"))]))
    parts = [street, clean(tags.get("addr:city")), clean(tags.get("addr:state")), clean(tags.get("addr:postcode"))]
    return ", ".join(part for part in parts if part) or None


def qualifying_tags(tags):
    return [
        f"{key}={tags[key]}"
        for key in DATA_CENTER_TAGS
        if str(tags.get(key, "")).lower() in {"data_center", "data_centre"}
    ]


def build(overpass, census_states):
    states = state_index(census_states)
    source_timestamp = overpass.get("osm3s", {}).get("timestamp_osm_base")
    features = []
    state_counts = Counter()
    tag_counts = Counter()
    geometry_counts = Counter()
    skipped_without_geometry = 0
    seen = set()

    for element in sorted(overpass.get("elements", []), key=lambda row: (row.get("type", ""), row.get("id", 0))):
        identity = (element.get("type"), element.get("id"))
        if identity in seen:
            continue
        seen.add(identity)
        coordinates = element_coordinates(element)
        if not coordinates:
            skipped_without_geometry += 1
            continue
        longitude, latitude, coordinate_method = coordinates
        tags = element.get("tags") or {}
        matched_tags = qualifying_tags(tags)
        if not matched_tags:
            continue
        state = state_for_point(states, longitude, latitude, tags.get("addr:state"))
        state_code = state["code"] if state else clean(tags.get("addr:state"))
        state_name = state["name"] if state else state_code
        state_fips = state["fips"] if state else None
        city = clean(tags.get("addr:city")) or clean(tags.get("is_in:city"))
        county = clean(tags.get("addr:county")) or clean(tags.get("is_in:county"))
        postal_code = clean(tags.get("addr:postcode"))
        operator = clean(tags.get("operator")) or clean(tags.get("brand"))
        name = clean(tags.get("name")) or clean(tags.get("official_name"))
        if not name:
            name = f"{operator} data center" if operator else "Mapped data center"
        location_tags = list(dict.fromkeys(filter(None, [
            "United States",
            state_name,
            state_code,
            county,
            city,
            postal_code,
            f"Census state {state_fips}" if state_fips else None,
        ])))
        for tag in matched_tags:
            tag_counts[tag] += 1
        if state_code:
            state_counts[state_code] += 1
        geometry_counts[element["type"]] += 1
        osm_type = element["type"]
        osm_id = int(element["id"])
        properties = {
            "record_type": "data_center",
            "inventory_scope": "United States",
            "source_name": "OpenStreetMap",
            "source_id": "openstreetmap",
            "source_snapshot_at": source_timestamp,
            "osm_type": osm_type,
            "osm_id": osm_id,
            "osm_url": f"https://www.openstreetmap.org/{osm_type}/{osm_id}",
            "name": name,
            "operator": operator,
            "website": clean(tags.get("website")) or clean(tags.get("contact:website")),
            "street_address": joined_address(tags),
            "house_number": clean(tags.get("addr:housenumber")),
            "street": clean(tags.get("addr:street")),
            "city": city,
            "county": county,
            "state": state_code,
            "state_name": state_name,
            "postal_code": postal_code,
            "country": "United States",
            "country_code": "US",
            "census_state_fips": state_fips,
            "latitude": latitude,
            "longitude": longitude,
            "coordinate_method": coordinate_method,
            "location_tags": location_tags,
            "facility_tags": matched_tags,
            "wikidata": clean(tags.get("wikidata")),
            "operator_wikidata": clean(tags.get("operator:wikidata")),
            "start_date": clean(tags.get("start_date")),
        }
        features.append({
            "type": "Feature",
            "id": f"osm-{osm_type}-{osm_id}",
            "geometry": {"type": "Point", "coordinates": [longitude, latitude]},
            "properties": {key: value for key, value in properties.items() if value is not None},
        })

    return {
        "type": "FeatureCollection",
        "metadata": {
            "inventory": "OpenStreetMap U.S. mapped data centers",
            "record_count": len(features),
            "source_timestamp": source_timestamp,
            "source_url": "https://www.openstreetmap.org/",
            "source_api": OVERPASS_URL,
            "source_query": OSM_QUERY,
            "source_license": "Open Database License (ODbL) 1.0",
            "source_license_url": "https://www.openstreetmap.org/copyright",
            "attribution": "OpenStreetMap contributors",
            "coverage_note": "All OpenStreetMap elements returned inside the U.S. boundary that match the documented data-center tags. Community mapping is not a census and may omit private, proposed, or unmapped facilities.",
            "census_geography_source": CENSUS_STATES_URL,
            "state_counts": dict(sorted(state_counts.items())),
            "tag_counts": dict(sorted(tag_counts.items())),
            "geometry_counts": dict(sorted(geometry_counts.items())),
            "named_count": sum(feature["properties"]["name"] != "Mapped data center" for feature in features),
            "located_state_count": sum(bool(feature["properties"].get("state")) for feature in features),
            "skipped_without_geometry": skipped_without_geometry,
        },
        "features": features,
    }


def write_geojson(data, output):
    output.parent.mkdir(parents=True, exist_ok=True)
    metadata = json.dumps(data["metadata"], ensure_ascii=False, separators=(",", ":"))
    features = ",\n".join(json.dumps(feature, ensure_ascii=False, separators=(",", ":"))
                            for feature in data["features"])
    output.write_text(f'{{"type":"FeatureCollection","metadata":{metadata},"features":[\n{features}\n]}}\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--overpass-json", type=Path, help="Use a saved Overpass response instead of downloading")
    parser.add_argument("--census-states-json", type=Path, help="Use saved Census state GeoJSON instead of downloading")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    overpass = json.loads(args.overpass_json.read_text()) if args.overpass_json else download_overpass()
    census_states = json.loads(args.census_states_json.read_text()) if args.census_states_json else download_census_states()
    data = build(overpass, census_states)
    if not data["features"]:
        raise RuntimeError("Nationwide OpenStreetMap query returned no mapped data centers")
    write_geojson(data, args.output)
    print(f"Wrote {len(data['features'])} nationwide OpenStreetMap data centers to {args.output}")


if __name__ == "__main__":
    main()
