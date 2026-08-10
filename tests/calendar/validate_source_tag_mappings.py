#!/usr/bin/env python3
"""Validate that source tags map to community sectors."""

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from baltimore.event_sources import sources as baltimore_sources
from dc.event_sources import sources as dc_sources
from hawaii.event_sources import sources as hawaii_sources
from multicity.event_sources import sources as multicity_sources
from philadelphia.event_sources import sources as philadelphia_sources
from pittsburgh.event_sources import sources as pittsburgh_sources
from virtual.event_sources import sources as virtual_sources
from westvirginia.event_sources import sources as westvirginia_sources

ALLOWED_NON_SECTOR_TAGS = {
    "MarylandGov",
    "Food",
    "Water",
    "Shelter",
    "Clothing",
    "Health",
    "Safety",
    "Belonging",
    "Esteem",
    "Growth",
    "Purpose",
}


def _load_sector_tags(path: Path) -> set[str]:
    data = json.loads(path.read_text())
    tags = set()
    for category in data.get("categories", []):
        tags.update(category.get("matches", []))
    return tags


def _unmapped_for_city(city: str, city_sources: list[dict], mapped_tags: set[str]) -> Counter:
    missing = Counter()
    for source in city_sources:
        for tag in source.get("tags", []):
            if tag in ALLOWED_NON_SECTOR_TAGS:
                continue
            if tag not in mapped_tags:
                missing[tag] += 1
    if missing:
        print(f"{city}:")
        for tag, count in missing.most_common():
            print(f"  {tag}: {count}")
    return missing


def main() -> int:
    mapped_tags = _load_sector_tags(ROOT / "data/category_maps/community_sectors.json")
    all_missing = Counter()
    city_sets = {
        "baltimore": baltimore_sources,
        "dc": dc_sources,
        "hawaii": hawaii_sources,
        "multicity": multicity_sources,
        "philadelphia": philadelphia_sources,
        "pittsburgh": pittsburgh_sources,
        "virtual": virtual_sources,
        "westvirginia": westvirginia_sources,
    }
    for city, city_sources in city_sets.items():
        all_missing.update(_unmapped_for_city(city, city_sources, mapped_tags))
    if not all_missing:
        print("All source tags map to a community sector.")
        return 0
    print("\nSummary:")
    for tag, count in all_missing.most_common():
        print(f"- {tag}: {count}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
