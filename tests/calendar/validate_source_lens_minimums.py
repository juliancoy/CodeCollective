#!/usr/bin/env python3
"""Ensure each Baltimore source has at least 1 sector tag and 1 Maslow tag."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from baltimore.event_sources import sources

MASLOW_TAGS = {
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

SECTOR_TAGS = {
    "Technology",
    "Education",
    "Entrepreneurship",
    "Economics",
    "Finance",
    "Health",
    "Politics",
    "Culture",
    "Faith",
    "Environment",
    "Makerspace",
    "Other",
}


def main() -> int:
    failures = []
    for source in sources:
        tags = set(source.get("tags", []))
        has_sector = bool(tags & SECTOR_TAGS)
        has_maslow = bool(tags & MASLOW_TAGS)
        if not has_sector or not has_maslow:
            failures.append((source.get("name") or source.get("url"), has_sector, has_maslow))

    if not failures:
        print("All Baltimore sources satisfy minimums: 1 sector + 1 Maslow.")
        return 0

    print("Sources missing required lens tags:")
    for name, has_sector, has_maslow in failures:
        print(f"- {name}: sector={has_sector} maslow={has_maslow}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
