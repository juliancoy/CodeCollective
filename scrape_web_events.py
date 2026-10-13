import json
import re
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Set, Tuple
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
from dateutil.parser import parse as parse_date
from icalendar import Calendar

from http_client import build_session, polite_get


def _as_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [value]


def _normalize_event_schema(item: Dict[str, Any], source_url: str) -> Dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    item_type = item.get("@type")
    if isinstance(item_type, list):
        lowered = {str(value or "").strip().lower() for value in item_type}
        is_event = any(value.endswith("event") for value in lowered)
    else:
        normalized_type = str(item_type or "").strip().lower()
        is_event = normalized_type == "event" or normalized_type.endswith("event")
    if not is_event:
        return None

    name = str(item.get("name") or "").strip()
    start = str(item.get("startDate") or "").strip()
    if not name or not start:
        return None

    location = item.get("location") or {}
    loc_name = ""
    loc_addr = ""
    if isinstance(location, dict):
        loc_name = str(location.get("name") or "").strip()
        address = location.get("address")
        if isinstance(address, dict):
            loc_addr = str(
                address.get("streetAddress")
                or address.get("addressLocality")
                or address.get("name")
                or ""
            ).strip()
        elif isinstance(address, str):
            loc_addr = address.strip()
    elif isinstance(location, str):
        loc_name = location.strip()

    image = item.get("image")
    if isinstance(image, list):
        image = image[0] if image else ""
    image_url = str(image or "").strip()

    event_url = str(item.get("url") or item.get("@id") or "").strip()
    if event_url:
        event_url = urljoin(source_url, event_url)
    else:
        event_url = source_url

    status_raw = str(item.get("eventStatus") or "").lower()
    status = "ACTIVE" if ("cancel" not in status_raw and "postpon" not in status_raw) else "CANCELLED"

    return {
        "name": name,
        "description": str(item.get("description") or "").strip(),
        "startDate": start,
        "endTime": str(item.get("endDate") or "").strip(),
        "url": event_url,
        "status": status,
        "location": {"name": loc_name, "address": loc_addr},
        "imageUrl": image_url,
        "source": source_url,
    }


def _extract_events_from_jsonld_payload(payload: Any, source_url: str) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    if isinstance(payload, dict):
        maybe_graph = payload.get("@graph")
        if isinstance(maybe_graph, list):
            for node in maybe_graph:
                evt = _normalize_event_schema(node, source_url)
                if evt:
                    events.append(evt)
        evt = _normalize_event_schema(payload, source_url)
        if evt:
            events.append(evt)
        for item in _as_list(payload.get("itemListElement")):
            if isinstance(item, dict):
                evt = _normalize_event_schema(item.get("item") or item, source_url)
                if evt:
                    events.append(evt)
    elif isinstance(payload, list):
        for node in payload:
            events.extend(_extract_events_from_jsonld_payload(node, source_url))
    return events


def _normalize_wix_event(item: Dict[str, Any], source_url: str) -> Dict[str, Any] | None:
    if not isinstance(item, dict):
        return None

    title = str(item.get("title") or "").strip()
    scheduling = item.get("scheduling") or {}
    config = scheduling.get("config") if isinstance(scheduling, dict) else {}
    if not isinstance(config, dict):
        config = {}

    start = str(config.get("startDate") or "").strip()
    if not title or not start:
        return None

    location_raw = item.get("location") or {}
    location_name = ""
    location_address = ""
    location: Dict[str, Any] = {"name": "", "address": ""}
    if isinstance(location_raw, dict):
        location_name = str(location_raw.get("name") or "").strip()
        location_address = str(location_raw.get("address") or "").strip()
        full_address = location_raw.get("fullAddress") or {}
        if isinstance(full_address, dict):
            location.update(
                {
                    "city": full_address.get("city") or "",
                    "state": full_address.get("subdivision") or "",
                    "postalCode": full_address.get("postalCode") or "",
                    "country": full_address.get("country") or "",
                }
            )
            geocode = full_address.get("geocode") or {}
            if isinstance(geocode, dict):
                location["latitude"] = geocode.get("latitude")
                location["longitude"] = geocode.get("longitude")
    elif isinstance(location_raw, str):
        location_name = location_raw.strip()

    location["name"] = location_name
    location["address"] = location_address

    image_raw = item.get("mainImage") or {}
    image_url = ""
    if isinstance(image_raw, dict):
        image_url = str(image_raw.get("url") or "").strip()
    elif isinstance(image_raw, str):
        image_url = image_raw.strip()

    slug = str(item.get("slug") or "").strip()
    event_url = urljoin(source_url, f"/event-details/{slug}") if slug else source_url

    status_raw = item.get("status")
    status = "CANCELLED" if str(status_raw).lower() in {"cancelled", "canceled", "2"} else "ACTIVE"

    return {
        "name": title,
        "description": str(item.get("description") or item.get("about") or "").strip(),
        "startDate": start,
        "endTime": str(config.get("endDate") or "").strip(),
        "url": event_url,
        "status": status,
        "location": location,
        "imageUrl": image_url,
        "source": source_url,
    }


def _extract_wix_events_from_payload(payload: Any, source_url: str) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            evt = _normalize_wix_event(value, source_url)
            if evt:
                events.append(evt)
                return
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(payload)
    return events


def _extract_wix_events(soup: BeautifulSoup, source_url: str) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    for script in soup.find_all("script", attrs={"type": "application/json"}):
        raw = script.string or script.get_text() or ""
        raw = raw.strip()
        if not raw or ("appsWarmupData" not in raw and "wix-warmup-data" not in str(script.get("id") or "")):
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        events.extend(_extract_wix_events_from_payload(payload, source_url))
    return events


def _extract_simple_dated_events(soup: BeautifulSoup, source_url: str) -> List[Dict[str, Any]]:
    lines = [
        line.strip()
        for line in soup.get_text("\n").splitlines()
        if line.strip()
    ]
    date_pattern = re.compile(
        r"^(January|February|March|April|May|June|July|August|September|October|November|December)\s+"
        r"\d{1,2}(?:\s*-\s*\d{1,2})?,\s+\d{4}$"
    )
    skip_titles = {
        "click for more info",
        "register",
        "registration",
        "become a member",
        "contact us",
        "event categories",
        "general",
        "meeting",
        "special events",
        "view details",
        "read more",
        "learn more",
        "more information",
        "buy tickets",
        "get tickets",
    }

    events: List[Dict[str, Any]] = []
    for index, line in enumerate(lines):
        if not date_pattern.match(line):
            continue
        title = ""
        for candidate in lines[index + 1 : index + 5]:
            normalized = candidate.strip().lower()
            # A second date belongs to another entry, not this event's title.
            if date_pattern.match(candidate):
                break
            if normalized in {
                "view details", "read more", "learn more", "more information",
                "buy tickets", "get tickets",
            }:
                break
            if normalized in skip_titles or normalized.isdigit():
                continue
            # Separators and time ranges on detail pages are not titles. Do
            # not scan past them into unrelated page text to invent an event.
            if not any(char.isalpha() for char in candidate) or re.match(
                r"^\d{1,2}:\d{2}\s*(?:am|pm)\b", normalized
            ):
                break
            title = candidate.strip()
            break
        if not title:
            continue
        try:
            start_text = re.sub(r"\s*-\s*\d{1,2}", "", line).strip()
            start = parse_date(start_text, fuzzy=False)
        except (TypeError, ValueError, OverflowError):
            continue
        events.append(
            {
                "name": title,
                "description": "",
                "startDate": start.isoformat(),
                "endTime": "",
                "url": source_url,
                "status": "ACTIVE",
                "location": {"name": "", "address": ""},
                "imageUrl": "",
                "source": source_url,
            }
        )
    return events


def _event_key(event: Dict[str, Any]) -> Tuple[str, str]:
    start = str(event.get("startDate", "")).strip()
    try:
        parsed_start = parse_date(start)
        if parsed_start.tzinfo is not None:
            start = parsed_start.astimezone(timezone.utc).replace(microsecond=0).isoformat()
    except (TypeError, ValueError, OverflowError):
        pass

    return (
        str(event.get("name", "")).strip().lower(),
        start,
    )


def _normalize_dt_for_output(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.isoformat()
        return value.isoformat()
    return str(value)


def _parse_ics_events(ics_bytes: bytes, source_url: str) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    try:
        calendar = Calendar.from_ical(ics_bytes)
    except Exception:
        return events

    now = datetime.now(timezone.utc)
    past_cutoff = now - timedelta(days=30)
    for component in calendar.walk():
        if component.name != "VEVENT":
            continue
        try:
            summary = str(component.get("summary") or "").strip()
            dtstart_prop = component.get("dtstart")
            if not summary or dtstart_prop is None:
                continue

            dtstart = getattr(dtstart_prop, "dt", dtstart_prop)
            dtend_prop = component.get("dtend")
            dtend = getattr(dtend_prop, "dt", dtend_prop) if dtend_prop else None
            start_dt = parse_date(str(dtstart))
            if start_dt.tzinfo is None:
                start_dt = start_dt.replace(tzinfo=timezone.utc)
            if start_dt < past_cutoff:
                continue

            event_url = str(component.get("url") or "").strip() or source_url
            location_text = str(component.get("location") or "").strip()
            description = str(component.get("description") or "").strip()

            events.append(
                {
                    "name": summary,
                    "description": description,
                    "startDate": _normalize_dt_for_output(dtstart),
                    "endTime": _normalize_dt_for_output(dtend),
                    "url": event_url,
                    "status": "ACTIVE",
                    "location": {"name": location_text, "address": location_text},
                    "imageUrl": "",
                    "source": source_url,
                }
            )
        except Exception:
            continue
    return events


def _extract_nava_event(soup: BeautifulSoup, source_url: str) -> List[Dict[str, Any]]:
    """Nava detail pages publish labeled UTC dates, but no Event JSON-LD."""
    if urlparse(source_url).hostname not in {"navapbc.com", "www.navapbc.com"}:
        return []
    label = soup.find("p", string="Event Date")
    date_node = label.find_next_sibling() if label else None
    title = soup.find("meta", property="og:title")
    if not date_node or not title:
        return []
    match = re.fullmatch(
        r"(.+?\d{4}) at (\d{1,2}:\d{2})(?:\s*(AM|PM))?"
        r"(?:[–—-](\d{1,2}:\d{2}))?\s*(AM|PM) UTC",
        date_node.get_text(" ", strip=True),
    )
    if not match:
        return []
    day, start_clock, start_period, end_clock, period = match.groups()
    try:
        start = parse_date(f"{day} {start_clock} {start_period or period}").replace(tzinfo=timezone.utc)
        end = parse_date(f"{day} {end_clock} {period}").replace(tzinfo=timezone.utc) if end_clock else None
        if end and end < start:
            end += timedelta(days=1)
    except ValueError:
        return []
    location_label = soup.find("p", string="Location")
    location_node = location_label.find_next_sibling() if location_label else None
    location = location_node.get_text(" ", strip=True) if location_node else ""
    # This source belongs to the Baltimore calendar; Nava also holds events
    # in other cities. Do not import its nationwide program indiscriminately.
    if "baltimore" not in location.lower():
        return []
    description = soup.find("meta", property="og:description")
    image = soup.find("meta", property="og:image")
    return [{
        "name": title.get("content", "").removesuffix(" | Nava"),
        "startDate": start.isoformat(), "endTime": end.isoformat() if end else "",
        "url": source_url, "source": source_url, "status": "ACTIVE",
        "description": description.get("content", "") if description else "",
        "imageUrl": image.get("content", "") if image else "",
        "location": {"name": location, "address": location},
    }]


def _extract_events_from_page(soup: BeautifulSoup, source_url: str) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    seen: Set[Tuple[str, str]] = set()
    title = soup.select_one('.SystemPageTitle')
    date_node = soup.select_one('.eventInfoStartDate .eventInfoBoxValue')
    time_node = soup.select_one('.eventInfoStartTime [client-tz-item]')
    if title and date_node and time_node:
        date_text = date_node.get_text(' ', strip=True)
        times = time_node.get_text(' ', strip=True).split(' - ')
        try:
            tz = ZoneInfo(time_node['client-tz-item'])
            start = parse_date(f'{date_text} {times[0]}').replace(tzinfo=tz)
            end = parse_date(f'{date_text} {times[-1]}').replace(tzinfo=tz)
            location = soup.select_one('.eventInfoLocation .eventInfoBoxValue')
            location_text = location.get_text(' ', strip=True) if location else ''
            events.append({
                'name': title.get_text(' ', strip=True),
                'startDate': start.isoformat(),
                'endTime': end.isoformat(),
                'url': source_url,
                'status': 'ACTIVE',
                'location': {'name': location_text, 'address': location_text},
                'source': source_url,
            })
        except (ValueError, KeyError):
            pass
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = script.string or script.get_text() or ""
        raw = raw.strip()
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        for evt in _extract_events_from_jsonld_payload(payload, source_url):
            key = _event_key(evt)
            if key in seen:
                continue
            seen.add(key)
            events.append(evt)
    for evt in _extract_wix_events(soup, source_url):
        key = _event_key(evt)
        if key in seen:
            continue
        seen.add(key)
        events.append(evt)
    if not events:
        # University calendars such as Hopkins Hub use schema.org microdata.
        for node in soup.select('[itemscope][itemtype$="/Event"]'):
            def prop(name):
                element = node.select_one(f'[itemprop="{name}"]')
                return (element.get('content') or element.get('datetime') or element.get_text(' ', strip=True)) if element else ''
            event = _normalize_event_schema({
                '@type': 'Event', 'name': prop('name'),
                'startDate': prop('startDate'), 'endDate': prop('endDate'),
                'description': prop('description'), 'location': prop('location'),
                'url': source_url,
            }, source_url)
            if event:
                events.append(event)
    if not events:
        events.extend(_extract_nava_event(soup, source_url))
    # Text heuristics are a fallback; structured events already provide the
    # authoritative titles and dates for this page.
    for evt in _extract_simple_dated_events(soup, source_url) if not events else []:
        key = _event_key(evt)
        if key in seen:
            continue
        seen.add(key)
        events.append(evt)
    return events


def _is_probable_ics_url(url: str) -> bool:
    lower = (url or "").lower()
    return lower.startswith("webcal://") or ".ics" in lower or "ical=" in lower or "icalendar" in lower


def _looks_like_ics_payload(payload: bytes) -> bool:
    if not payload:
        return False
    sample = payload[:2048].decode("utf-8", errors="ignore").upper()
    return "BEGIN:VCALENDAR" in sample


def _extract_candidate_links(soup: BeautifulSoup, source_url: str) -> Tuple[List[str], List[str]]:
    parsed_source = urlparse(source_url)
    source_host = (parsed_source.netloc or "").lower()
    event_links: List[str] = []
    feed_links: List[str] = []
    seen_events: Set[str] = set()
    seen_feeds: Set[str] = set()

    for embed in soup.select('[data-tockify-calendar]'):
        calendar_name = (embed.get('data-tockify-calendar') or '').strip()
        if re.fullmatch(r'[A-Za-z0-9_-]+', calendar_name):
            feed_url = f'https://tockify.com/api/feeds/ics/{calendar_name}'
            if feed_url not in seen_feeds:
                seen_feeds.add(feed_url)
                feed_links.append(feed_url)

    for anchor in soup.select("a[href]"):
        href = (anchor.get("href") or "").strip()
        if not href:
            continue
        absolute = urljoin(source_url, href)
        parsed = urlparse(absolute)
        if parsed.scheme not in {"http", "https", "webcal"}:
            continue
        host = (parsed.netloc or "").lower()
        if source_host and host and host != source_host:
            if not _is_probable_ics_url(absolute):
                continue

        text = " ".join(anchor.get_text(" ", strip=True).split()).lower()
        path_lower = (parsed.path or "").lower()
        full_lower = absolute.lower()

        if _is_probable_ics_url(absolute) or "add to calendar" in text or "calendar feed" in text:
            if absolute not in seen_feeds:
                seen_feeds.add(absolute)
                feed_links.append(absolute)
            continue

        is_eventish = (
            "event" in text
            or "upcoming" in text
            or "/event" in path_lower
            or "/events" in path_lower
            or "/article/" in path_lower
            or "/articles/" in path_lower
            or "/hc/en-us/articles/" in full_lower
        )
        if is_eventish and absolute not in seen_events:
            seen_events.add(absolute)
            event_links.append(absolute)

    return event_links, feed_links


def parse_web_events_page(source_url: str, location_pattern: str | None = None,
                          title_pattern: str | None = None) -> List[Dict[str, Any]]:
    session = build_session()
    response = polite_get(session, source_url, timeout=30, allow_redirects=True)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    events: List[Dict[str, Any]] = []
    seen: Set[Tuple[str, str]] = set()

    for evt in _extract_events_from_page(soup, source_url):
        key = _event_key(evt)
        if key in seen:
            continue
        seen.add(key)
        events.append(evt)

    event_links, feed_links = _extract_candidate_links(soup, source_url)

    for feed_url in feed_links:
        fetch_url = feed_url.replace("webcal://", "https://")
        try:
            feed_response = polite_get(session, fetch_url, timeout=30, allow_redirects=True)
            feed_response.raise_for_status()
            if not _looks_like_ics_payload(feed_response.content):
                continue
            for evt in _parse_ics_events(feed_response.content, feed_url):
                key = _event_key(evt)
                if key in seen:
                    continue
                seen.add(key)
                events.append(evt)
        except PermissionError:
            raise
        except Exception:
            continue

    # Follow a bounded set of likely event/article links for sites that list events on child pages.
    for link in event_links[:20]:
        try:
            child_response = polite_get(session, link, timeout=30, allow_redirects=True)
            if child_response.status_code >= 400:
                continue
            child_soup = BeautifulSoup(child_response.text, "html.parser")
            for evt in _extract_events_from_page(child_soup, link):
                key = _event_key(evt)
                if key in seen:
                    continue
                seen.add(key)
                events.append(evt)
        except Exception:
            continue

    if location_pattern:
        events = [event for event in events if re.search(
            location_pattern, json.dumps(event.get("location") or {}), re.IGNORECASE
        )]
    if title_pattern:
        events = [event for event in events if re.search(
            title_pattern, event.get("name", ""), re.IGNORECASE
        )]
    return events
