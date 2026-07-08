import json
import re
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
from typing import Any, Dict, List
from urllib.parse import quote, urljoin, urlparse

import requests


SOURCE_URL = "https://events.blackthorn.io/en/KbOkKk6/g/K6RWFzv502"
ACCOUNT_ID = "00DKb000000OkKkMAK"
GROUP_KEY = "K6RWFzv502"
BASE_URL = "https://events.blackthorn.io"


class _HTMLTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts: List[str] = []

    def handle_data(self, data: str) -> None:
        cleaned = data.strip()
        if cleaned:
            self.parts.append(cleaned)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in {"br", "p", "div", "li"}:
            self.parts.append("\n")


def _strip_html(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    parser = _HTMLTextExtractor()
    parser.feed(raw)
    text = " ".join(part.strip() for part in parser.parts if part.strip())
    text = unescape(" ".join(text.split()))
    return re.sub(r"\s+([.,;:!?])", r"\1", text)


def _headers(source_url: str = SOURCE_URL) -> Dict[str, str]:
    return {
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en",
        "Content-Type": "application/json",
        "Referer": source_url,
        "User-Agent": "Mozilla/5.0 (compatible; CodeCollectiveBot/1.0; +https://codecollective.us)",
    }


def _json_get(session: requests.Session, path: str, params: Dict[str, str], source_url: str) -> Dict[str, Any]:
    url = urljoin(BASE_URL, path)
    response = session.get(url, params=params, headers=_headers(source_url), timeout=30)
    response.raise_for_status()
    return response.json()


def _is_visible_event(summary: Dict[str, Any]) -> bool:
    name = str(summary.get("name") or "").strip()
    if not name or "template" in name.lower():
        return False
    status = str(summary.get("status") or summary.get("statusFormula") or "Active").lower()
    if "cancel" in status or "inactive" in status:
        return False
    start = summary.get("startDateUTC") or summary.get("startDate")
    if not start:
        return False
    try:
        start_dt = datetime.fromisoformat(str(start).replace("Z", "+00:00"))
    except ValueError:
        return True
    if start_dt.tzinfo is None:
        start_dt = start_dt.replace(tzinfo=timezone.utc)
    return start_dt >= datetime.now(timezone.utc)


def _event_url(event_id: str, source_url: str = SOURCE_URL) -> str:
    parsed = urlparse(source_url)
    path = parsed.path.rstrip("/")
    return f"{parsed.scheme}://{parsed.netloc}{path}/{quote(event_id)}"


def _normalize_event(detail: Dict[str, Any], summary: Dict[str, Any], source_url: str) -> Dict[str, Any] | None:
    name = str(detail.get("name") or summary.get("name") or "").strip()
    event_id = str(detail.get("id") or summary.get("id") or "").strip()
    start = str(detail.get("startDateUTC") or summary.get("startDateUTC") or detail.get("startDate") or "").strip()
    if not name or not event_id or not start:
        return None

    venue = detail.get("venue") if isinstance(detail.get("venue"), dict) else {}
    if not venue:
        venue = {
            "name": summary.get("venueName") or "",
            "zipcode": summary.get("venueZipcode") or "",
        }
        geocode = summary.get("venueGeocode")
        if isinstance(geocode, dict):
            venue["latitude"] = geocode.get("latitude")
            venue["longitude"] = geocode.get("longitude")

    street = str(venue.get("street") or "").strip()
    city = str(venue.get("city") or "").strip()
    state = str(venue.get("state") or "").strip()
    zipcode = str(venue.get("zipcode") or "").strip()
    address = ", ".join(part for part in [street, city, state, zipcode] if part)

    description = _strip_html(detail.get("description")) or str(detail.get("shortDescription") or "").strip()
    image_url = (
        detail.get("imageUrl")
        or detail.get("listingImageURL")
        or detail.get("thumbnailAndMobileImageUrl")
        or detail.get("detailImageURL")
        or ""
    )

    location: Dict[str, Any] = {
        "name": str(venue.get("name") or summary.get("venueName") or "").strip(),
        "address": address,
    }
    if venue.get("latitude") is not None:
        location["latitude"] = venue.get("latitude")
    if venue.get("longitude") is not None:
        location["longitude"] = venue.get("longitude")

    return {
        "name": name,
        "description": description,
        "startDate": start,
        "endTime": str(detail.get("endDateUTC") or summary.get("endDateUTC") or detail.get("endDate") or "").strip(),
        "url": _event_url(event_id, source_url),
        "source": source_url,
        "status": "ACTIVE",
        "location": location,
        "imageUrl": str(image_url or "").strip(),
        "tags": [str(detail.get("category") or summary.get("category") or "").strip()] if (detail.get("category") or summary.get("category")) else [],
    }


def _extract_events_from_payloads(
    summaries_payload: Dict[str, Any],
    detail_payloads: Dict[str, Dict[str, Any]],
    source_url: str = SOURCE_URL,
) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    summaries = summaries_payload.get("data") if isinstance(summaries_payload, dict) else []
    if not isinstance(summaries, list):
        return events

    for summary in summaries:
        if not isinstance(summary, dict) or not _is_visible_event(summary):
            continue
        event_id = str(summary.get("id") or "").strip()
        detail_payload = detail_payloads.get(event_id) or {}
        detail_items = detail_payload.get("data") if isinstance(detail_payload, dict) else []
        detail = detail_items[0] if isinstance(detail_items, list) and detail_items else summary
        if isinstance(detail, dict):
            event = _normalize_event(detail, summary, source_url)
            if event:
                events.append(event)
    return events


def scrape_events(
    source_url: str = SOURCE_URL,
    account_id: str = ACCOUNT_ID,
    group_key: str = GROUP_KEY,
) -> List[Dict[str, Any]]:
    session = requests.Session()
    summaries_payload = _json_get(
        session,
        f"/{account_id}/api/event-group-summaries",
        {"groupKey": group_key},
        source_url,
    )
    summaries = summaries_payload.get("data") if isinstance(summaries_payload, dict) else []
    detail_payloads: Dict[str, Dict[str, Any]] = {}
    for summary in summaries if isinstance(summaries, list) else []:
        if not isinstance(summary, dict) or not _is_visible_event(summary):
            continue
        event_id = str(summary.get("id") or "").strip()
        if not event_id:
            continue
        detail_payloads[event_id] = _json_get(
            session,
            f"/{account_id}/api/events/next",
            {"id": event_id, "groupKey": group_key},
            source_url,
        )
    return _extract_events_from_payloads(summaries_payload, detail_payloads, source_url)


if __name__ == "__main__":
    print(json.dumps(scrape_events(), indent=2))
