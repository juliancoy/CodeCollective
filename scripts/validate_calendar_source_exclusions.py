#!/usr/bin/env python3
"""Fail when generated events contain a source's excluded sector tags."""

import importlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CITIES = (
    "baltimore",
    "dc",
    "hawaii",
    "multicity",
    "philadelphia",
    "pittsburgh",
    "virtual",
    "westvirginia",
)


def normalize(value):
    return str(value or "").strip().casefold()


def load_category_matches():
    path = ROOT / "data" / "category_maps" / "community_sectors.json"
    category_map = json.loads(path.read_text(encoding="utf-8"))
    matches = {}
    for category in category_map.get("categories", []):
        label = normalize(category.get("label"))
        if not label:
            continue
        matches[label] = {
            label,
            *(normalize(tag) for tag in category.get("matches", [])),
        }
    return matches


def event_belongs_to_source(event, source):
    source_url = normalize(source.get("url"))
    source_name = normalize(source.get("group_name") or source.get("name"))
    event_urls = {
        normalize(event.get("source")),
        normalize(event.get("source_url")),
    }
    event_names = {
        normalize(event.get("source_group")),
        normalize(event.get("org_name")),
        normalize(event.get("orgName")),
    }
    return bool(
        (source_url and source_url in event_urls)
        or (source_name and source_name in event_names)
    )


def main():
    category_matches = load_category_matches()
    violations = []

    for city in CITIES:
        module = importlib.import_module(f"{city}.event_sources")
        excluded_sources = [
            source for source in module.sources if source.get("excluded_org_tags")
        ]
        if not excluded_sources:
            continue

        events_path = ROOT / city / "upcoming_events.json"
        events = json.loads(events_path.read_text(encoding="utf-8"))

        for source in excluded_sources:
            disallowed = set()
            for excluded_tag in source.get("excluded_org_tags", []):
                normalized = normalize(excluded_tag)
                disallowed.update(category_matches.get(normalized, {normalized}))

            source_name = source.get("group_name") or source.get("name") or source.get("url")
            for event in events:
                if not event_belongs_to_source(event, source):
                    continue
                forbidden_tags = sorted(
                    tag
                    for tag in event.get("tags", [])
                    if normalize(tag) in disallowed
                )
                if forbidden_tags:
                    violations.append(
                        (city, source_name, event.get("name"), forbidden_tags)
                    )

    if not violations:
        print("Generated calendar events respect all source sector exclusions.")
        return 0

    print("Generated calendar source-exclusion violations:")
    for city, source_name, event_name, tags in violations[:20]:
        print(f"- {city}: {source_name} / {event_name}: {', '.join(tags)}")
    if len(violations) > 20:
        print(f"- ... and {len(violations) - 20} more violation(s)")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
