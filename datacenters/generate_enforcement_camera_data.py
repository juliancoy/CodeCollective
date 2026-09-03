#!/usr/bin/env python3
"""Build the source-auditable Baltimore automated-enforcement map layer."""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "data" / "enforcement-cameras.json"

RED_LIGHT_SOURCE = "https://www.baltimorecity.gov/transportation"
RED_LIGHT_DOCUMENT = "https://transportation.baltimorecity.gov/sites/default/files/Red%20Light%20Camera%20Locations%201-28-25%20%281%29.pdf"

# Coordinates are intersection points returned by the ArcGIS World Geocoder.
# Directional entries remain separate official records.
RED_LIGHT_CAMERAS = [
    ("Reisterstown Rd", "Patterson Ave", "SB", -76.702454, 39.356202),
    ("W North Ave", "N Howard St", "WB", -76.619316, 39.310983),
    ("Belair Rd", "Erdman Ave", "SB", -76.573647, 39.321584),
    ("Erdman Ave", "Belair Rd", "EB", -76.573647, 39.321584),
    ("S Monroe St", "Washington Blvd", "NB", -76.642148, 39.275331),
    ("S Monroe St", "Washington Blvd", "SB", -76.642148, 39.275331),
    ("N Calvert St", "E Baltimore St", "NB", -76.612284, 39.289626),
    ("Harford Rd", "The Alameda", "NB", -76.590760, 39.321202),
    ("Harford Rd", "The Alameda", "SB", -76.590760, 39.321202),
    ("Pulaski Hwy", "N North Point Rd", "EB", -76.538531, 39.304963),
    ("Light St", "E Pratt St", "SB", -76.613554, 39.286554),
    ("E Pratt St", "Light St", "EB", -76.613554, 39.286554),
    ("W Northern Pkwy", "Falls Rd", "WB", -76.646195, 39.361305),
    ("W Northern Pkwy", "Greenspring Ave", "EB", -76.664478, 39.355640),
]

def feature(identifier, longitude, latitude, **properties):
    return {
        "type": "Feature",
        "id": identifier,
        "geometry": {"type": "Point", "coordinates": [longitude, latitude]},
        "properties": {"id": identifier, **properties},
    }


def build():
    features = []
    for index, (road, cross_street, direction, longitude, latitude) in enumerate(RED_LIGHT_CAMERAS, 1):
        location = f"{road} at {cross_street}"
        features.append(feature(
            f"baltimore-red-light-{index:02d}", longitude, latitude,
            camera_type="red-light camera", jurisdiction="Baltimore City",
            location=location, direction=direction, location_status="official intersection point",
            source_date="2025-01-28", source_url=RED_LIGHT_SOURCE,
            coordinate_method="ArcGIS World Geocoder intersection match",
        ))
    return {
        "type": "FeatureCollection",
        "metadata": {
            "generated_date": "2026-08-24",
            "feature_count": len(features),
            "scope": "Baltimore City red-light intersections published in the official January 28, 2025 location document",
            "note": "The source site migrated in 2026; the live Transportation landing page is linked on each record and the original document URL is retained here for audit history.",
            "sources": [RED_LIGHT_SOURCE, RED_LIGHT_DOCUMENT],
        },
        "features": features,
    }


if __name__ == "__main__":
    OUTPUT.write_text(json.dumps(build(), indent=2, ensure_ascii=False) + "\n")
    print(f"Wrote {OUTPUT} with {len(build()['features'])} features")
