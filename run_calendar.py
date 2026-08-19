#!/usr/bin/env python3
"""Run calendar generation with one globally bounded source-scrape pool.

`genCalendar.py` owns parsing and output behavior. This runner only replaces its
source scheduler so total concurrent source fetches are bounded while retaining
per-source-kind limits.
"""

from __future__ import annotations

import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import genCalendar


DEFAULT_MAX_WORKERS = 6


def bounded_fetch_all_sources(sources, city, max_workers=DEFAULT_MAX_WORKERS):
    if not sources:
        return [], [], []

    worker_count = max(1, min(int(max_workers or DEFAULT_MAX_WORKERS), len(sources)))
    kind_semaphores: dict[str, threading.Semaphore] = {}

    def source_kind(source):
        return (
            source.get("source_kind")
            or genCalendar.infer_source_kind(source.get("url", ""))
            or "unknown"
        )

    def run_one(index, source):
        kind = source_kind(source)
        limit = max(
            1,
            int(
                genCalendar.SOURCE_KIND_CONCURRENCY.get(
                    kind,
                    genCalendar.SOURCE_KIND_CONCURRENCY["unknown"],
                )
            ),
        )
        semaphore = kind_semaphores.setdefault(kind, threading.Semaphore(limit))
        with semaphore:
            events, unmatched, errors = genCalendar.fetch_events_from_source(source, city)
        return index, events, unmatched, errors

    ordered_results = []
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = [
            executor.submit(run_one, index, source)
            for index, source in enumerate(sources)
        ]
        for future in as_completed(futures):
            ordered_results.append(future.result())

    new_events = []
    unmatched_sources = []
    scrape_errors = []
    for _, events, unmatched, errors in sorted(ordered_results, key=lambda item: item[0]):
        new_events.extend(events)
        unmatched_sources.extend(unmatched)
        scrape_errors.extend(errors)

    return new_events, unmatched_sources, scrape_errors


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    genCalendar.fetch_all_sources = bounded_fetch_all_sources

    cities = [genCalendar.MULTICITY_BUCKET, *genCalendar.CALENDAR_CITIES]
    if argv:
        cities = argv

    for city in cities:
        genCalendar.main(city)
    genCalendar.write_root_aggregate(cities)


if __name__ == "__main__":
    main()
