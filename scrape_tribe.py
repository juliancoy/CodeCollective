from datetime import datetime, timezone
from typing import Any

from http_client import build_session, polite_get


USER_AGENT = "CodeCollectiveBot/1.0 (+https://github.com/juliancoy/CodeCollective)"


def _utc_iso(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        parsed = datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return ""
    return parsed.replace(tzinfo=timezone.utc).isoformat()


def _location(item: dict[str, Any]) -> dict[str, str]:
    venue = item.get("venue") or {}
    if not isinstance(venue, dict):
        venue = {}

    city = str(venue.get("city") or "").strip()
    state = str(
        venue.get("stateprovince")
        or venue.get("province")
        or venue.get("state")
        or ""
    ).strip()
    postal_code = str(venue.get("zip") or "").strip()
    locality = ", ".join(part for part in (city, state) if part)
    if postal_code:
        locality = f"{locality} {postal_code}".strip()
    address = ", ".join(
        part
        for part in (str(venue.get("address") or "").strip(), locality)
        if part
    )
    return {
        "name": str(venue.get("venue") or "").strip(),
        "address": address,
        "city": city,
        "state": state,
        "postalCode": postal_code,
    }


def _normalize_event(item: dict[str, Any], api_url: str) -> dict[str, Any] | None:
    name = str(item.get("title") or "").strip()
    start = _utc_iso(item.get("utc_start_date"))
    if not name or not start:
        return None

    image = item.get("image") or {}
    image_url = str(image.get("url") or "").strip() if isinstance(image, dict) else ""
    cancelled = name.casefold().startswith(("cancelled", "canceled"))
    return {
        "id": item.get("id"),
        "name": name,
        "description": str(item.get("description") or item.get("excerpt") or "").strip(),
        "startDate": start,
        "endTime": _utc_iso(item.get("utc_end_date")),
        "url": str(item.get("url") or api_url).strip(),
        "status": "CANCELLED" if cancelled else "ACTIVE",
        "location": _location(item),
        "imageUrl": image_url,
        "source": api_url,
    }


def _events_from_payload(payload: Any, api_url: str) -> list[dict[str, Any]]:
    items = payload.get("events") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        return []

    events = []
    for item in items:
        if not isinstance(item, dict):
            continue
        event = _normalize_event(item, api_url)
        if event:
            events.append(event)
    return events


def scrape(api_url: str) -> list[dict[str, Any]]:
    session = build_session(user_agent=USER_AGENT)
    response = polite_get(session, api_url, timeout=30, allow_redirects=True)
    response.raise_for_status()
    return _events_from_payload(response.json(), api_url)
