"""Structured ticket listings linked by Baltimore poetry organizers."""
import json
from datetime import datetime, timedelta
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
from http_client import build_session, polite_get
from scrape_web_events import _extract_events_from_page

TIMEZONE = ZoneInfo("America/New_York")


def _next_session(value):
    if isinstance(value, dict):
        if value.get("nextAvailableSession"):
            return value["nextAvailableSession"]
        for child in value.values():
            found = _next_session(child)
            if found:
                return found
    elif isinstance(value, list):
        for child in value:
            found = _next_session(child)
            if found:
                return found
    return None


def parse_ticket_events(html, url):
    soup = BeautifulSoup(html, "html.parser")
    next_data = soup.find("script", id="__NEXT_DATA__")
    try:
        next_session = _next_session(json.loads(next_data.string or "{}")) if next_data else None
    except (ValueError, TypeError):
        next_session = None
    events = []
    for event in _extract_events_from_page(soup, url):
        location_text = " ".join(str(v) for v in event["location"].values())
        if "baltimore" not in (location_text + " " + event["description"]).lower():
            continue
        start = datetime.fromisoformat(event["startDate"])
        start = start.replace(tzinfo=TIMEZONE) if start.tzinfo is None else start
        raw_end = event.pop("endTime", "")
        end = datetime.fromisoformat(raw_end) if raw_end else None
        if end and end.tzinfo is None:
            end = end.replace(tzinfo=TIMEZONE)
        # Eventbrite can describe an entire season as one months-long event.
        # Only publish its explicitly advertised next session, never invent recurrence.
        if end and end - start > timedelta(days=1):
            if not next_session:
                continue
            start = datetime.fromisoformat(next_session)
            start = start.replace(tzinfo=TIMEZONE) if start.tzinfo is None else start
            end = None
        event["startDate"] = start.isoformat()
        if end and end > start:
            event["endTime"] = end.isoformat()
        event["location"].update(city="Baltimore", state="MD", country="US")
        if "15006512AAB98F81" in event["url"]:
            event["description"] += (
                " Organizer homepage lists October 16 as 7–11 p.m.; "
                "Ticketmaster lists a 7:30 p.m. show start. Confirm arrival time with the organizer."
            )
        events.append(event)
    return events


def scrape_events(url, ticket_url=None):
    session = build_session()
    response = polite_get(session, ticket_url or url, timeout=30)
    response.raise_for_status()
    if ticket_url:
        return parse_ticket_events(response.text, ticket_url)

    # Discover current ticket links from the organizer, including newly posted shows.
    soup = BeautifulSoup(response.text, "html.parser")
    links = dict.fromkeys(
        a["href"].split("?")[0]
        for a in soup.select("a[href]")
        if urlparse(a["href"]).hostname in {"eventbrite.com", "www.eventbrite.com"}
        and urlparse(a["href"]).path.startswith("/e/")
    )
    events = []
    for link in list(links)[:10]:
        page = polite_get(session, link, timeout=30)
        page.raise_for_status()
        events.extend(parse_ticket_events(page.text, link))
    return events
