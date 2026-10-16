"""Official Banner event cards and Impact Maryland's Framer landing page."""

from datetime import datetime
import json
import re
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

from http_client import build_session, polite_get


DATE = r"(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan\.?|Feb\.?|Mar\.?|Apr\.?|Jun\.?|Jul\.?|Aug\.?|Sep\.?|Sept\.?|Oct\.?|Nov\.?|Dec\.?)\s+\d{1,2},\s+\d{4}"
TIMEZONE = ZoneInfo("America/New_York")


def _date(text):
    match = re.search(DATE, text)
    if not match:
        return None
    value = match[0].replace(".", "")
    for fmt in ("%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def parse_impact(html: str, source_url: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    day = next((day for node in soup.select("h3") if (day := _date(node.get_text(" ", strip=True)))), None)
    clocks = []
    for heading in soup.select("h3"):
        match = re.fullmatch(r"(\d{1,2}:\d{2})(?:\s*-\s*\d{1,2}:\d{2})?\s*([ap])\.?m\.?", heading.get_text(" ", strip=True), re.I)
        if match:
            clocks.append(datetime.strptime(f"{match[1]} {match[2]}m", "%I:%M %p").time())
    if not day or not clocks:
        raise ValueError("Impact Maryland's published date or agenda times were not found")

    # FAQ answers are serialized in Framer's handover data, even when collapsed.
    handover = soup.select_one("script#__framer__handoverData")
    values = json.loads(handover.string) if handover else []
    venue = {}
    for value in values:
        if not isinstance(value, str) or "The event will be held on" not in value:
            continue
        match = re.search(r"at (.+?) located at ([^\"\]]+)", value)
        if match:
            venue = {"name": match[1], "address": match[2].rstrip(".")}
            break
    if not venue:
        raise ValueError("Impact Maryland's published venue was not found")
    def meta(prop):
        node = soup.find("meta", property=prop)
        return node.get("content", "") if node else ""
    return [{
        "name": f"Impact Maryland {day.year}",
        "startDate": datetime.combine(day, min(clocks), TIMEZONE).isoformat(),
        # The page lists a separate VIP reception end, not a general admission end.
        "endTime": "",
        "description": meta("og:description") + " Registration and breakfast begin at the listed start time; see the published agenda for sessions and VIP reception details.",
        "url": source_url,
        "source": source_url,
        "status": "ACTIVE",
        "location": venue,
        "imageUrl": meta("og:image"),
    }]


def parse_index(html: str, source_url: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select(".article-section-body")
    if not cards:
        raise ValueError("The Banner's event cards were not found")
    events = []
    seen = set()
    for card in cards:
        title = card.select_one("a.main-headline[href]")
        date = card.select_one(".relative-timestamp__date")
        day = _date(date.get_text(" ", strip=True)) if date else None
        if not title or not day or urlparse(title["href"]).scheme != "https":
            continue  # No guessed year/day for month-only or undated announcements.
        if urlparse(title["href"]).hostname == "impactmaryland.thebaltimorebanner.com":
            continue  # Tracked separately with its precise agenda and venue.
        key = (title["href"], day)
        if key in seen:
            continue
        seen.add(key)
        description = card.select_one(".description")
        events.append({
            "name": title.get_text(" ", strip=True),
            "startDate": day.isoformat(),
            "endTime": "",
            "description": (description.get_text(" ", strip=True) if description else "") + " Time and venue are not specified on the event index; check the event page.",
            "url": title["href"], "source": source_url,
            "status": "ACTIVE", "location": {"name": "", "address": ""},
        })
    return events


def scrape_events(source_url: str) -> list[dict]:
    response = polite_get(build_session(), source_url, timeout=30)
    response.raise_for_status()
    # Parse bytes so BeautifulSoup honors the page's declared UTF-8 encoding.
    html = response.content
    if urlparse(source_url).hostname == "impactmaryland.thebaltimorebanner.com":
        return parse_impact(html, source_url)
    return parse_index(html, source_url)
