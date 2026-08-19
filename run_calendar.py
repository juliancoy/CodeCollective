#!/usr/bin/env python3
"""Run calendar generation with bounded, polite source fetching.

`genCalendar.py` owns parsing and output behavior. This runner adds operational
controls around it: one global source-fetch pool, per-source-kind limits, and a
compatibility shim that routes legacy ``requests.get`` calls through the shared
polite HTTP client during calendar generation.
"""

from __future__ import annotations

import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

import genCalendar
import http_client


DEFAULT_MAX_WORKERS = 6
_ORIGINAL_REQUESTS_GET = requests.get
_LEGACY_SESSION = http_client.build_session()


def install_legacy_polite_requests() -> None:
    """Route legacy module-level requests.get calls through polite_get.

    New scraper code should call http_client.polite_get directly. This shim
    keeps older scraper modules subject to the same host pacing, retries,
    robots checks, and conditional cache until they are migrated individually.
    """

    def polite_requests_get(url, **kwargs):
        timeout = kwargs.pop("timeout", http_client.DEFAULT_TIMEOUT)
        return http_client.polite_get(
            _LEGACY_SESSION,
            url,
            timeout=timeout,
            **kwargs,
        )

    requests.get = polite_requests_get


def restore_requests_get() -> None:
    requests.get = _ORIGINAL_REQUESTS_GET


def bounded_fetch_all_sources(sources, city, max_workers=DEFAULT_MAX_WORKERS):
    if not sources:
        return [], [], []

    worker_count = max(1, min(int(max_workers or DEFAULT_MAX_WORKERS), len(sources)))
    kind_semaphores: dict[str, threading.Semaphore] = {}
    semaphore_lock = threading.Lock()

    def source_kind(source):
        return (
            source.get("source_kind")
            or genCalendar.infer_source_kind(source.get("url", ""))
            or "unknown"
        )

    def kind_semaphore(kind):
        limit = max(
            1,
            int(
                genCalendar.SOURCE_KIND_CONCURRENCY.get(
                    kind,
                    genCalendar.SOURCE_KIND_CONCURRENCY["unknown"],
                )
            ),
        )
        with semaphore_lock:
            return kind_semaphores.setdefault(kind, threading.Semaphore(limit))

    def run_one(index, source):
        kind = source_kind(source)
        with kind_semaphore(kind):
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
    install_legacy_polite_requests()

    try:
        cities = [genCalendar.MULTICITY_BUCKET, *genCalendar.CALENDAR_CITIES]
        if argv:
            cities = argv

        for city in cities:
            genCalendar.main(city)
        genCalendar.write_root_aggregate(cities)
    finally:
        restore_requests_get()


if __name__ == "__main__":
    main()
