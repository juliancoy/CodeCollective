"""Scrape Greater Baltimore Climate Initiative events from the CCT Foundation."""

from __future__ import annotations

from typing import Any

from bs4 import BeautifulSoup

from http_client import build_session, polite_get
from scrape_web_events import _extract_events_from_page


GBCI_EVENT_NAME_MARKERS = (
    "greater baltimore climate summit",
    "building greater baltimore momentum",
)


def _is_gbci_event(event: dict[str, Any]) -> bool:
    name = str(event.get("name") or "").strip().lower()
    location_name = str((event.get("location") or {}).get("name") or "").strip().lower()
    return (
        location_name == "webinar"
        or any(marker in name for marker in GBCI_EVENT_NAME_MARKERS)
    )


def scrape(source_url: str) -> list[dict[str, Any]]:
    session = build_session()
    response = polite_get(session, source_url, timeout=10, allow_redirects=True)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    events: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for event in _extract_events_from_page(soup, source_url):
        if not _is_gbci_event(event):
            continue
        key = (str(event.get("name") or ""), str(event.get("startDate") or ""))
        if key in seen:
            continue
        seen.add(key)
        events.append(event)
    return events
