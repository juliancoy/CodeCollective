"""Read Empower DC's public event cards, whose RSVP URLs have no /event path."""

from datetime import datetime
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

from http_client import build_session, polite_get


SOURCE_URL = "https://www.empowerdc.org/events"


def parse_events(html, source_url=SOURCE_URL):
    events = []
    soup = BeautifulSoup(html, "html.parser")
    for card in soup.select(".card-event"):
        title = card.find("h4")
        link = card.select_one("a[href]")
        if not title or not link:
            continue
        start = None
        location = ""
        for line in card.select(".py-1"):
            text = line.get_text(" ", strip=True)
            try:
                start = datetime.strptime(text, "%A %d %b %Y at %I:%M %p").replace(
                    tzinfo=ZoneInfo("America/New_York")
                )
            except ValueError:
                if line.find("p"):
                    location = text
        if start is None:
            continue
        events.append({
            "name": title.get_text(" ", strip=True),
            "startDate": start.isoformat(),
            "endTime": "",
            "url": urljoin(source_url, link["href"]),
            "description": "",
            "location": {"name": location, "address": ""},
            "status": "ACTIVE",
            "imageUrl": "",
        })
    return events


def scrape(source_url=SOURCE_URL):
    response = polite_get(build_session(), source_url, timeout=30)
    response.raise_for_status()
    return parse_events(response.text, source_url)
