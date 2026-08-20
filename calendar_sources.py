import importlib
import json
import os


def collect_source_events(city, flatten_sources, fetch_all_sources):
    module = importlib.import_module(f"{city}.event_sources")
    sources = list(module.sources)

    try:
        extra_module = importlib.import_module(f"{city}.extra_event_sources")
    except ModuleNotFoundError as exc:
        if exc.name != f"{city}.extra_event_sources":
            raise
    else:
        sources.extend(extra_module.sources)

    sources = flatten_sources(sources)
    return fetch_all_sources(sources, city)


def write_unmatched_sources(city, unmatched_sources):
    unmatched_sources_path = os.path.join(city, "unmatched_source_patterns.json")
    with open(unmatched_sources_path, "w+", encoding="utf-8") as f:
        json.dump(unmatched_sources, f, indent=4)

    if unmatched_sources:
        print(f"Unmatched source patterns saved to {unmatched_sources_path}")

    return unmatched_sources_path
