#!/usr/bin/env python3
"""Run calendar generation with bounded, polite source fetching."""

from __future__ import annotations

import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

import genCalendar
import http_client

DEFAULT_MAX_WORKERS = 6
DEFAULT_TELEMETRY_PATH = ".cache/codecollective-scrape-telemetry.json"
_ORIGINAL_REQUESTS_GET = requests.get
_LEGACY_SESSION = http_client.build_session()


def install_legacy_polite_requests() -> None:
    def polite_requests_get(url, **kwargs):
        timeout = kwargs.pop("timeout", http_client.DEFAULT_TIMEOUT)
        return http_client.polite_get(_LEGACY_SESSION, url, timeout=timeout, **kwargs)
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
        return source.get("source_kind") or genCalendar.infer_source_kind(source.get("url", "")) or "unknown"

    def kind_semaphore(kind):
        limit = max(1, int(genCalendar.SOURCE_KIND_CONCURRENCY.get(kind, genCalendar.SOURCE_KIND_CONCURRENCY["unknown"])))
        with semaphore_lock:
            return kind_semaphores.setdefault(kind, threading.Semaphore(limit))

    def run_one(index, source):
        kind = source_kind(source)
        with kind_semaphore(kind):
            events, unmatched, errors = genCalendar.fetch_events_from_source(source, city)
        return index, events, unmatched, errors

    ordered_results = []
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = [executor.submit(run_one, index, source) for index, source in enumerate(sources)]
        for future in as_completed(futures):
            ordered_results.append(future.result())

    new_events, unmatched_sources, scrape_errors = [], [], []
    for _, events, unmatched, errors in sorted(ordered_results, key=lambda item: item[0]):
        new_events.extend(events); unmatched_sources.extend(unmatched); scrape_errors.extend(errors)
    return new_events, unmatched_sources, scrape_errors


def _append_github_summary(snapshot: dict[str, object]) -> None:
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return
    totals = snapshot.get("totals", {})
    hosts = snapshot.get("hosts", {})
    ranked = sorted(
        hosts.items(),
        key=lambda item: (-int(item[1].get("failures", 0)), -float(item[1].get("latency_ms_avg", 0))),
    )[:15]
    lines = [
        "## Calendar scrape telemetry",
        "",
        f"Duration: **{snapshot.get('duration_seconds', 0)}s** · Requests: **{totals.get('requests', 0)}** · "
        f"Retries: **{totals.get('retries', 0)}** · 429s: **{totals.get('http_429', 0)}** · "
        f"5xx: **{totals.get('http_5xx', 0)}** · Failures: **{totals.get('failures', 0)}** · "
        f"304 revalidations: **{totals.get('cache_revalidations', 0)}**",
        "",
        "| Host | Requests | Avg ms | Max ms | Retries | 429 | 5xx | Failures | 304 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for host, metrics in ranked:
        lines.append(
            f"| {host} | {metrics.get('requests', 0)} | {metrics.get('latency_ms_avg', 0)} | "
            f"{metrics.get('latency_ms_max', 0)} | {metrics.get('retries', 0)} | {metrics.get('http_429', 0)} | "
            f"{metrics.get('http_5xx', 0)} | {metrics.get('failures', 0)} | {metrics.get('cache_revalidations', 0)} |"
        )
    with open(summary_path, "a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    genCalendar.fetch_all_sources = bounded_fetch_all_sources
    http_client.reset_telemetry()
    install_legacy_polite_requests()
    telemetry_path = os.environ.get("CODECOLLECTIVE_SCRAPE_TELEMETRY_PATH", DEFAULT_TELEMETRY_PATH)

    try:
        cities = [genCalendar.MULTICITY_BUCKET, *genCalendar.CALENDAR_CITIES]
        if argv:
            cities = argv
        for city in cities:
            genCalendar.main(city)
        genCalendar.write_root_aggregate(cities)
    finally:
        restore_requests_get()
        try:
            snapshot = http_client.write_telemetry(telemetry_path)
            _append_github_summary(snapshot)
            print(f"Scrape telemetry saved to {telemetry_path}")
        except Exception as exc:
            print(f"Warning: unable to write scrape telemetry: {exc}")


if __name__ == "__main__":
    main()
