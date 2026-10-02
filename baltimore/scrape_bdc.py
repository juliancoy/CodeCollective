import html
import re
from datetime import datetime, timedelta
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup
from dateutil.parser import parse as parse_date


BASE_URL = "https://baltimoredevelopment.com"
EVENTS_URL = f"{BASE_URL}/events/"
API_URL = f"{BASE_URL}/wp-json/wp/v2/bdc-event"
EASTERN_TZ = ZoneInfo("America/New_York")


def _clean_text(value):
    return re.sub(r"\s+", " ", html.unescape(value or "")).strip()


def _element_text(element):
    if not element:
        return ""
    for marker in element.select("[data-markjs]"):
        marker.unwrap()
    element.smooth()
    paragraphs = element.find_all("p", recursive=False)
    if paragraphs:
        return _clean_text(" ".join(paragraph.get_text(" ", strip=True) for paragraph in paragraphs))
    return _clean_text(element.get_text(" ", strip=True))


def _img_candidates(src):
    if not src:
        return set()
    candidates = {src}
    candidates.add(re.sub(r"-\d+x\d+(\.[A-Za-z0-9]+)$", r"\1", src))
    return {candidate for candidate in candidates if candidate}


def _embedded_media_urls(item):
    urls = set()
    embedded = item.get("_embedded") or {}
    for media in embedded.get("wp:featuredmedia") or []:
        source_url = media.get("source_url")
        if source_url:
            urls.update(_img_candidates(source_url))
        details = media.get("media_details") or {}
        for size in (details.get("sizes") or {}).values():
            if isinstance(size, dict):
                urls.update(_img_candidates(size.get("source_url")))
    return urls


def _fetch_event_posts(session):
    posts = []
    page = 1
    while True:
        response = session.get(
            API_URL,
            params={"per_page": 100, "page": page, "_embed": "wp:featuredmedia"},
            timeout=30,
        )
        if response.status_code == 400 and page > 1:
            break
        response.raise_for_status()
        batch = response.json()
        if not batch:
            break
        posts.extend(batch)
        total_pages = int(response.headers.get("X-WP-TotalPages") or page)
        if page >= total_pages:
            break
        page += 1
    return posts


def _build_post_image_index(posts):
    index = {}
    for item in posts:
        title = _clean_text((item.get("title") or {}).get("rendered"))
        if not title:
            continue
        post = {
            "title": title,
            "link": item.get("link") or "",
        }
        for media_url in _embedded_media_urls(item):
            index[media_url] = post
    return index


def _strip_label(element, label):
    if not element:
        return ""
    text = _element_text(element)
    return re.sub(rf"^{re.escape(label)}:\s*", "", text, flags=re.IGNORECASE).strip()


def _parse_time_piece(piece, fallback_period=None):
    piece = piece.strip().lower().replace(".", "")
    match = re.search(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", piece)
    if not match:
        return None
    hour = int(match.group(1))
    minute = int(match.group(2) or 0)
    period = match.group(3) or fallback_period
    if period == "pm" and hour < 12:
        hour += 12
    if period == "am" and hour == 12:
        hour = 0
    return hour, minute


def _parse_datetimes(date_text, time_text):
    try:
        day = parse_date(date_text, fuzzy=True).date()
    except (TypeError, ValueError, OverflowError):
        return "", ""

    normalized_time = re.sub(r"\s*[-\u2013\u2014]\s*", "-", time_text or "").strip()
    parts = [part for part in normalized_time.split("-", 1) if part.strip()]
    if not parts:
        start_dt = datetime(day.year, day.month, day.day, 12, 0, tzinfo=EASTERN_TZ)
        return start_dt.isoformat(), (start_dt + timedelta(hours=1)).isoformat()

    end_period = None
    if len(parts) > 1:
        end_period_match = re.search(r"(am|pm)", parts[1], re.IGNORECASE)
        if end_period_match:
            end_period = end_period_match.group(1).lower()
    start_time = _parse_time_piece(parts[0], fallback_period=end_period)
    if not start_time:
        return "", ""

    start_dt = datetime(day.year, day.month, day.day, start_time[0], start_time[1], tzinfo=EASTERN_TZ)
    if len(parts) > 1:
        end_time = _parse_time_piece(parts[1])
        if end_time:
            end_dt = datetime(day.year, day.month, day.day, end_time[0], end_time[1], tzinfo=EASTERN_TZ)
            if end_dt <= start_dt:
                end_dt += timedelta(days=1)
            return start_dt.isoformat(), end_dt.isoformat()
    return start_dt.isoformat(), (start_dt + timedelta(hours=1)).isoformat()


def _extract_image_url(box, page_url):
    img = box.select_one("img.event-featured-image, .event-image img, img")
    if not img:
        return ""
    src = img.get("src") or img.get("data-src") or ""
    if not src:
        srcset = img.get("srcset") or ""
        src = srcset.split(",", 1)[0].strip().split(" ", 1)[0]
    return urljoin(page_url, src) if src else ""


def _post_for_card(image_url, image_index):
    for candidate in _img_candidates(image_url):
        if candidate in image_index:
            return image_index[candidate]
    return None


def _title_fallback(box, description):
    linked = box.select_one(".about a")
    linked_text = _element_text(linked)
    if linked_text and linked_text.lower() not in {"events", "register for event"}:
        return linked_text
    first_sentence = re.split(r"(?<=[.!?])\s+", description or "", maxsplit=1)[0]
    return _clean_text(first_sentence[:90]) or "Baltimore Development Corporation Event"


def _parse_card(box, page_url, image_index):
    date_text = _strip_label(box.select_one(".date"), "DATE")
    time_text = _strip_label(box.select_one(".time"), "TIME")
    location_text = _strip_label(box.select_one(".location"), "LOCATION")
    start_date, end_time = _parse_datetimes(date_text, time_text)
    if not start_date:
        return None

    description = _element_text(box.select_one(".about"))
    image_url = _extract_image_url(box, page_url)
    post = _post_for_card(image_url, image_index)
    register_link = box.select_one(".register a[href]") or box.select_one("h3 a[href]")
    event_url = urljoin(page_url, register_link.get("href")) if register_link and register_link.get("href") else ""
    name = post["title"] if post else _title_fallback(box, description)

    return {
        "name": name,
        "description": description,
        "startDate": start_date,
        "endTime": end_time,
        "url": event_url or (post or {}).get("link") or page_url,
        "status": "ACTIVE",
        "location": {"name": location_text, "address": location_text},
        "imageUrl": image_url,
        "source": page_url,
    }


def scrape_events(source_url=EVENTS_URL):
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125 Safari/537.36"
            )
        }
    )
    posts = _fetch_event_posts(session)
    image_index = _build_post_image_index(posts)

    response = session.get(source_url, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    events = []
    seen = set()
    for box in soup.select(".event-box"):
        event = _parse_card(box, response.url or source_url, image_index)
        if not event:
            continue
        key = (event["name"].lower(), event["startDate"])
        if key in seen:
            continue
        seen.add(key)
        events.append(event)
    return events


if __name__ == "__main__":
    import json

    print(json.dumps(scrape_events(), indent=2))
