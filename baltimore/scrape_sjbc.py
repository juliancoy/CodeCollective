import json
import re
from datetime import datetime
from typing import Dict, List
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

from http_client import polite_get


SOURCE_URL = "https://sjbc.org/events/"
BASE_URL = "https://sjbc.org"
TIMEZONE = ZoneInfo("America/New_York")
BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)
DEFAULT_LOCATION = {
    "name": "St John Baptist Church",
    "address": "9055 Tamar Dr",
    "city": "Columbia",
    "state": "MD",
    "postalCode": "21045",
    "country": "US",
}


def _build_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": BROWSER_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
    )
    return session


def _extract_json_assignment(html: str, variable_name: str) -> Dict:
    pattern = rf"var\s+{re.escape(variable_name)}\s*=\s*(\{{.*?\}});"
    match = re.search(pattern, html, re.DOTALL)
    if not match:
        return {}
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return {}


def _extract_calendar_payload(html: str) -> tuple[Dict, str]:
    soup = BeautifulSoup(html, "html.parser")
    calendar_data = soup.select_one(".evo_cal_data")
    if not calendar_data or not calendar_data.get("data-sc"):
        return {}, ""

    try:
        shortcode = json.loads(calendar_data["data-sc"])
    except json.JSONDecodeError:
        return {}, ""

    general_params = _extract_json_assignment(html, "evo_general_params")
    return shortcode, str(general_params.get("n") or "")


def _post_eventon_events(session: requests.Session, shortcode: Dict, nonce: str) -> Dict:
    post_data = {
        "direction": "none",
        "ajaxtype": "initial",
        "nonce": nonce,
    }
    for key, value in shortcode.items():
        post_data[f"shortcode[{key}]"] = value

    response = session.post(
        urljoin(BASE_URL, "/?evo-ajax=eventon_get_events"),
        data=post_data,
        headers={
            "Referer": SOURCE_URL,
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "application/json, text/javascript, */*; q=0.01",
        },
        timeout=20,
    )
    response.raise_for_status()
    return response.json()


def _first_meta_value(event_meta: Dict, key: str) -> str:
    value = event_meta.get(key)
    if isinstance(value, list):
        return str(value[0]) if value else ""
    return str(value or "")


def _event_datetime_from_eventon(event_item: Dict, bound: str) -> datetime | None:
    event_meta = event_item.get("event_pmv") or {}
    unix_key = "event_start_unix" if bound == "start" else "event_end_unix"
    hour_key = "_start_hour" if bound == "start" else "_end_hour"
    minute_key = "_start_minute" if bound == "start" else "_end_minute"
    ampm_key = "_start_ampm" if bound == "start" else "_end_ampm"

    try:
        date_value = datetime.fromtimestamp(int(event_item[unix_key]), ZoneInfo("UTC")).date()
    except (KeyError, TypeError, ValueError):
        return None

    try:
        hour = int(_first_meta_value(event_meta, hour_key) or "0")
        minute = int(_first_meta_value(event_meta, minute_key) or "0")
    except ValueError:
        hour = 0
        minute = 0

    ampm = _first_meta_value(event_meta, ampm_key).lower()
    if ampm == "pm" and hour != 12:
        hour += 12
    elif ampm == "am" and hour == 12:
        hour = 0

    return datetime(date_value.year, date_value.month, date_value.day, hour, minute, tzinfo=TIMEZONE)


def _load_event_schema(event_node) -> Dict:
    schema_node = event_node.select_one('script[type="application/ld+json"]')
    if not schema_node:
        return {}
    try:
        return json.loads(schema_node.get_text(strip=True))
    except json.JSONDecodeError:
        return {}


def _clean_description(description_html: str) -> str:
    if not description_html:
        return ""
    return BeautifulSoup(description_html, "html.parser").get_text(" ", strip=True)


def _parse_events_payload(payload: Dict) -> List[Dict]:
    event_items = {
        str(item.get("event_id") or item.get("ID")): item
        for item in payload.get("json", [])
        if isinstance(item, dict)
    }
    soup = BeautifulSoup(payload.get("html") or "", "html.parser")
    events: List[Dict] = []

    for event_node in soup.select(".eventon_list_event[data-event_id]"):
        event_id = str(event_node.get("data-event_id"))
        event_item = event_items.get(event_id, {})
        schema = _load_event_schema(event_node)
        if not schema and not event_item:
            continue

        start_dt = _event_datetime_from_eventon(event_item, "start")
        if not start_dt and schema.get("startDate"):
            start_dt = datetime.fromisoformat(str(schema["startDate"]))
        if not start_dt:
            continue

        end_dt = _event_datetime_from_eventon(event_item, "end")
        event_meta = event_item.get("event_pmv") or {}
        registration_url = _first_meta_value(event_meta, "evcal_lmlink")
        detail_url = schema.get("url") or _first_meta_value(event_meta, "evcal_exlink") or SOURCE_URL
        location_attrs = event_node.select_one(".event_location_attrs")
        location = dict(DEFAULT_LOCATION)
        if location_attrs:
            location["name"] = location_attrs.get("data-location_name") or location["name"]
            location["address"] = location_attrs.get("data-location_address") or location["address"]

        event: Dict = {
            "name": schema.get("name") or event_item.get("event_title", ""),
            "description": _clean_description(str(schema.get("description") or "")),
            "startDate": start_dt.isoformat(),
            "url": urljoin(BASE_URL, str(detail_url)),
            "status": "ACTIVE",
            "location": location,
            "recurring": _first_meta_value(event_meta, "evcal_repeat").lower() == "yes",
            "scrapeTime": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
        }
        if end_dt and end_dt > start_dt:
            event["endTime"] = end_dt.isoformat()
        if schema.get("image"):
            event["imageUrl"] = urljoin(BASE_URL, str(schema["image"]))
        if registration_url:
            event["registrationUrl"] = registration_url

        events.append(event)

    return events


def scrape_events(url: str = SOURCE_URL) -> List[Dict]:
    session = _build_session()
    response = polite_get(session, url, timeout=20)
    response.raise_for_status()

    shortcode, nonce = _extract_calendar_payload(response.text)
    if not shortcode or not nonce:
        return []

    payload = _post_eventon_events(session, shortcode, nonce)
    return _parse_events_payload(payload)


if __name__ == "__main__":
    import json as json_module

    print(json_module.dumps(scrape_events(), indent=2))
