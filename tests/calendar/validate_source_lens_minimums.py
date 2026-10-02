#!/usr/bin/env python3
"""Ensure each Baltimore source has tags represented in both lens maps."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from baltimore.event_sources import sources


def _load_lens_tags(path: Path) -> set[str]:
    data = json.loads(path.read_text())
    tags = set()
    for category in data.get("categories", []):
        label = str(category.get("label", "")).strip()
        if label and label != "Other":
            tags.add(label)
        tags.update(category.get("matches", []))
    return tags


def main() -> int:
    sector_tags = _load_lens_tags(ROOT / "data/category_maps/community_sectors.json")
    maslow_tags = _load_lens_tags(ROOT / "data/category_maps/maslow_needs.json")
    failures = []
    for source in sources:
        tags = set(source.get("tags", []))
        has_sector = bool(tags & sector_tags)
        has_maslow = bool(tags & maslow_tags)
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
