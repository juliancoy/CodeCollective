import html
import json
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import unquote, urljoin, urlparse

from bs4 import BeautifulSoup

from http_client import build_session, polite_get


API_KEY = "c6e5e0363b5925b28552de8805464c66f25ba0ce"
DEFAULT_TIMEZONE = "America/New_York"


def _extract_calendar_id(page_html: str) -> int:
    soup = BeautifulSoup(page_html, "html.parser")
    calendar = soup.select_one("timely-calendar[data-info]")
    if calendar is None:
        raise ValueError("Timely calendar metadata was not found")

    encoded_info = calendar.get("data-info") or ""
    info = json.loads(html.unescape(unquote(encoded_info)))
    calendar_id = info.get("id")
    if not isinstance(calendar_id, int):
        raise ValueError("Timely calendar id was not found")
    return calendar_id


def _image_url(item: dict[str, Any]) -> str:
    images = item.get("images") or []
    if not images or not isinstance(images[0], dict):
        return ""
    image = images[0]
    for size in ("full", "medium", "small", "thumbnail"):
        candidate = image.get(size)
        if isinstance(candidate, dict) and candidate.get("url"):
            return str(candidate["url"])
    return ""


def _location(item: dict[str, Any]) -> dict[str, Any]:
    taxonomies = item.get("taxonomies") or {}
    venues = taxonomies.get("taxonomy_venue") or []
    if not venues or not isinstance(venues[0], dict):
        return {"name": "", "address": ""}

    venue = venues[0]
    city = str(venue.get("city") or "").strip()
    state = str(venue.get("country_first_division") or "").strip()
    postal_code = str(venue.get("postal_code") or "").strip()
    locality = ", ".join(part for part in (city, state) if part)
    if postal_code:
        locality = f"{locality} {postal_code}".strip()
    address = ", ".join(
        part
        for part in (
            str(venue.get("address") or "").strip(),
            str(venue.get("address2") or "").strip(),
            locality,
        )
        if part
    )

    location: dict[str, Any] = {
        "name": str(venue.get("title") or "").strip(),
        "address": address,
        "city": city,
        "state": state,
        "postalCode": postal_code,
        "country": str(venue.get("country") or "").strip(),
    }
    coordinates = str(venue.get("geo_location") or "").split(",", 1)
    if len(coordinates) == 2:
        try:
            location["latitude"] = float(coordinates[0])
            location["longitude"] = float(coordinates[1])
        except ValueError:
            pass
    return location


def _utc_iso(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        parsed = datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return ""
    return parsed.replace(tzinfo=timezone.utc).isoformat()


def _normalize_event(item: dict[str, Any], calendar_url: str) -> dict[str, Any] | None:
    name = str(item.get("title") or "").strip()
    start = _utc_iso(item.get("start_utc_datetime"))
    if not name or not start:
        return None

    status = str(item.get("event_status") or "").strip().lower()
    cancelled = status in {"cancelled", "canceled"} or name.lower().startswith(
        ("cancelled", "canceled")
    )
    return {
        "id": item.get("uid") or item.get("id"),
        "name": name,
        "description": str(item.get("description_short") or "").strip(),
        "startDate": start,
        "endTime": _utc_iso(item.get("end_utc_datetime")),
        "url": str(item.get("canonical_url") or item.get("url") or calendar_url),
        "status": "CANCELLED" if cancelled else "ACTIVE",
        "location": _location(item),
        "imageUrl": _image_url(item),
        "source": calendar_url,
    }


def _events_from_payload(payload: Any, calendar_url: str) -> list[dict[str, Any]]:
    data = payload.get("data") if isinstance(payload, dict) else None
    grouped_items = data.get("items") if isinstance(data, dict) else None
    if not isinstance(grouped_items, dict):
        return []

    events = []
    for items in grouped_items.values():
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            event = _normalize_event(item, calendar_url)
            if event:
                events.append(event)
    return events


def scrape(calendar_url: str, *, now: datetime | None = None) -> list[dict[str, Any]]:
    session = build_session()
    page_response = polite_get(session, calendar_url, timeout=30)
    page_response.raise_for_status()
    calendar_id = _extract_calendar_id(page_response.text)

    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    start = current - timedelta(days=30)
    end = current + timedelta(days=365)

    parsed = urlparse(calendar_url)
    api_url = urljoin(f"{parsed.scheme}://{parsed.netloc}", f"/api/calendars/{calendar_id}/events")
    api_response = polite_get(
        session,
        api_url,
        timeout=30,
        headers={
            "Accept": "application/json",
            "Referer": calendar_url,
            "X-Api-Key": API_KEY,
        },
        params={
            "group_by_date": 1,
            "timezone": DEFAULT_TIMEZONE,
            "view": "month",
            "start_date_utc": int(start.timestamp()),
            "end_date_utc": int(end.timestamp()),
            "per_page": 1000,
            "page": 1,
        },
    )
    api_response.raise_for_status()
    return _events_from_payload(api_response.json(), calendar_url)
