"""Discover StartDMV events via its sitemap, rather than its stale listing HTML."""

import json
import logging
from datetime import datetime
from urllib.parse import urlparse
from xml.etree import ElementTree
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
from dateutil.parser import parse

from http_client import build_session, polite_get
from scrape_web_events import _normalize_event_schema


TIMEZONE = ZoneInfo("America/New_York")
SITEMAP = "https://startdmv.org/sitemap.xml"


def _nodes(payload):
    if isinstance(payload, list):
        for item in payload:
            yield from _nodes(item)
    elif isinstance(payload, dict):
        yield payload
        yield from _nodes(payload.get("@graph"))


def parse_event_page(html, source_url):
    events = []
    soup = BeautifulSoup(html, "html.parser")
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            payload = json.loads(script.get_text())
        except (ValueError, TypeError):
            continue
        for item in _nodes(payload):
            event = _normalize_event_schema(item, source_url)
            if event is None:
                continue
            event["timezone"] = "America/New_York"
            for field in ("startDate", "endTime"):
                if event.get(field):
                    value = parse(event[field])
                    if value.tzinfo is None:
                        value = value.replace(tzinfo=TIMEZONE)
                    event[field] = value.isoformat()
            organizer = item.get("organizer") or {}
            if isinstance(organizer, list):
                organizer = next((o for o in organizer if isinstance(o, dict)), {})
            if isinstance(organizer, dict) and organizer.get("name"):
                event["org_name"] = event["orgName"] = organizer["name"]
            offers = item.get("offers") or []
            if isinstance(offers, dict):
                offers = [offers]
            event["offers"] = offers
            for offer in offers:
                if not isinstance(offer, dict):
                    continue
                registration = str(offer.get("url") or "").strip()
                if urlparse(registration).scheme in {"http", "https"}:
                    event["url"] = registration
                    break
            mode = str(item.get("eventAttendanceMode") or "")
            event["eventAttendanceMode"] = mode
            if mode.endswith("/OnlineEventAttendanceMode"):
                event["location"] = {"name": "Online", "address": ""}
            events.append(event)
    return events


def scrape(source_url="https://startdmv.org/events", *, now=None):
    session = build_session()
    response = polite_get(session, SITEMAP, timeout=30)
    response.raise_for_status()
    root = ElementTree.fromstring(response.content)
    links = dict.fromkeys(
        node.text.strip()
        for node in root.iter()
        if node.tag.rsplit("}", 1)[-1] == "loc" and node.text
        and urlparse(node.text.strip()).hostname == "startdmv.org"
        and urlparse(node.text.strip()).path.startswith("/event/")
    )
    current = now or datetime.now(TIMEZONE)
    events = []
    seen = set()
    for link in links:
        try:
            response = polite_get(session, link, timeout=30)
            response.raise_for_status()
            children = parse_event_page(response.text, link)
        except Exception:
            logging.exception("Failed to scrape StartDMV event %s", link)
            # Let genCalendar record the source failure instead of silently
            # publishing an incomplete calendar.
            raise
        for event in children:
            if parse(event["startDate"]) < current:
                continue
            key = (event["url"], event["startDate"])
            if key not in seen:
                seen.add(key)
                events.append(event)
    return events
