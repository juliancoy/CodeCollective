"""Scrape Bio-Trac's official workshop calendar and linked course pages."""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

from http_client import build_session, polite_get


USER_AGENT = (
    "Mozilla/5.0 (compatible; CodeCollectiveBot/1.0; "
    "+https://github.com/juliancoy/CodeCollective)"
)
TIMEZONE = ZoneInfo("America/New_York")
DEFAULT_LOCATION = {
    "name": "The Bioscience Education Center at Montgomery College",
    "address": "20200 Observation Drive, Germantown, MD 20876",
    "city": "Germantown",
    "state": "MD",
    "postalCode": "20876",
    "country": "US",
}


def _clean_text(value: str) -> str:
    return " ".join(str(value or "").split())


def _parse_span_days(value: str) -> int:
    match = re.search(r"\b(\d+)\s*day\b", value or "", flags=re.IGNORECASE)
    return max(1, int(match.group(1))) if match else 1


def _parse_daily_hours(soup: BeautifulSoup) -> tuple[tuple[int, int], tuple[int, int]]:
    for heading in soup.find_all(["h3", "h4", "h5"]):
        text = _clean_text(heading.get_text(" ", strip=True))
        match = re.search(
            r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)\s*[-–—]\s*"
            r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)",
            text,
            flags=re.IGNORECASE,
        )
        if not match:
            continue

        def hour_24(hour: str, meridiem: str) -> int:
            parsed = int(hour) % 12
            return parsed + (12 if meridiem.lower() == "pm" else 0)

        return (
            (hour_24(match.group(1), match.group(3)), int(match.group(2) or 0)),
            (hour_24(match.group(4), match.group(6)), int(match.group(5) or 0)),
        )
    return (9, 0), (17, 0)


def _extract_detail(html: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")
    description = ""
    blockquote = soup.find("blockquote")
    if blockquote:
        description = _clean_text(blockquote.get_text(" ", strip=True))

    start_time, end_time = _parse_daily_hours(soup)
    return {
        "description": description,
        "start_time": start_time,
        "end_time": end_time,
    }


def _events_from_calendar_html(
    html: str,
    source_url: str,
    details_by_url: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    details_by_url = details_by_url or {}
    events: list[dict[str, Any]] = []

    for row in soup.select("table tr"):
        cells = row.find_all(["th", "td"])
        if len(cells) < 4:
            continue

        title = _clean_text(cells[0].get_text(" ", strip=True))
        date_text = _clean_text(cells[1].get_text(" ", strip=True))
        if not title or title.casefold().endswith("workshop title"):
            continue
        try:
            start_day = datetime.strptime(date_text, "%m/%d/%y").date()
        except ValueError:
            continue

        link = cells[0].find("a", href=True)
        event_url = urljoin(source_url, link["href"]) if link else source_url
        detail = details_by_url.get(event_url, {})
        start_hour, start_minute = detail.get("start_time", (9, 0))
        end_hour, end_minute = detail.get("end_time", (17, 0))
        span_days = _parse_span_days(cells[2].get_text(" ", strip=True))
        end_day = start_day + timedelta(days=span_days - 1)
        cost = _clean_text(cells[3].get_text(" ", strip=True))
        description = _clean_text(detail.get("description", ""))
        facts = [f"{span_days}-day Bio-Trac training workshop"]
        if cost:
            facts.append(f"registration fee {cost}")
        facts_text = "; ".join(facts)
        facts_text = facts_text[:1].upper() + facts_text[1:] + "."
        description = f"{description} {facts_text}".strip()

        events.append(
            {
                "name": title,
                "description": description,
                "startDate": datetime(
                    start_day.year,
                    start_day.month,
                    start_day.day,
                    start_hour,
                    start_minute,
                    tzinfo=TIMEZONE,
                ).isoformat(),
                "endTime": datetime(
                    end_day.year,
                    end_day.month,
                    end_day.day,
                    end_hour,
                    end_minute,
                    tzinfo=TIMEZONE,
                ).isoformat(),
                "url": event_url,
                "status": "ACTIVE",
                "location": dict(DEFAULT_LOCATION),
                "imageUrl": "",
                "source": source_url,
            }
        )

    return events


def scrape(source_url: str) -> list[dict[str, Any]]:
    session = build_session(user_agent=USER_AGENT)
    response = polite_get(session, source_url, timeout=30, allow_redirects=True)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    detail_urls = []
    seen_urls = set()
    for row in soup.select("table tr"):
        anchor = row.select_one("td:first-child a[href]")
        if not anchor:
            continue
        detail_url = urljoin(source_url, anchor["href"])
        if detail_url not in seen_urls:
            seen_urls.add(detail_url)
            detail_urls.append(detail_url)

    details_by_url: dict[str, dict[str, Any]] = {}
    for detail_url in detail_urls:
        try:
            detail_response = polite_get(session, detail_url, timeout=30, allow_redirects=True)
            detail_response.raise_for_status()
            details_by_url[detail_url] = _extract_detail(detail_response.text)
        except Exception:
            # Calendar rows remain usable if an individual course page is unavailable.
            continue

    return _events_from_calendar_html(response.text, source_url, details_by_url)
