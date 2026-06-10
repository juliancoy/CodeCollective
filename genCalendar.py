import scrape_meetup
import copy
from difflib import SequenceMatcher
import scrape_eventbrite
import scrape_jotform
import scrape_luma
import scrape_ics
import scrape_gform
import scrape_luma_orgpage
import scrape_luma_calendar
import scrape_luma_user
import scrape_mtc
import scrape_gdg
import scrape_partiful
import scrape_web_events
import scrape_legistar
import scrape_thread_helpcenter
import scrape_bniajfi
import json
import datetime
import pytz
import os
from bs4 import BeautifulSoup
import re
import scrape_eventbrite_org
import markdown
from dateutil.parser import parse
import sys
import importlib
from concurrent.futures import ThreadPoolExecutor, as_completed
import traceback
import genSimpleCalendar
from calendar_sources import collect_source_events, write_unmatched_sources
from calendar_normalize import (
    normalize_event_start_dates,
    download_event_images,
    split_upcoming_events,
)
from calendar_dedupe import merge_and_dedupe_events
from calendar_output import persist_calendar_outputs
from events_map_generator import generate_events_map_page
from geocode_upcoming import geocode_upcoming_events
from geocode_cache import (
    load_geocode_cache,
    save_geocode_cache,
    apply_geocode_cache,
)
import unicodedata
from urllib.parse import parse_qs, urlparse
from city_determinant import determine_event_city

# Define the timezone for EST
est_timezone = pytz.timezone("America/New_York")
utc_timezone = datetime.timezone.utc

CITY_DEFAULT_TIMEZONES = {
    "baltimore": "America/New_York",
    "dc": "America/New_York",
    "pittsburgh": "America/New_York",
    "philadelphia": "America/New_York",
    "westvirginia": "America/New_York",
    "virtual": "UTC",
    "hawaii": "Pacific/Honolulu",
    "multicity": "UTC",
}

SOURCE_KIND_CONCURRENCY = {
    "meetup": 1,
    "eventbrite_org": 1,
    "eventbrite_event": 2,
    "luma_org": 2,
    "luma_calendar": 2,
    "luma_user": 2,
    "luma_event": 3,
    "partiful": 3,
    "jotform": 3,
    "google_form": 3,
    "gdg": 3,
    "unknown": 2,
}

CALENDAR_CITIES = [
    "baltimore",
    "westvirginia",
    "hawaii",
    "dc",
    "pittsburgh",
    "philadelphia",
    "virtual",
]
MULTICITY_BUCKET = "multicity"
_MULTICITY_SOURCE_CACHE = None


def merge_tags(*tag_lists):
    merged = []
    seen = set()

    for tag_list in tag_lists:
        if not tag_list:
            continue
        for tag in tag_list:
            if not tag or tag in seen:
                continue
            seen.add(tag)
            merged.append(tag)

    return merged


def normalize_source_entry(entry, legacy_kind=None):
    def _fallback_org_image_url(source_url):
        parsed = urlparse(str(source_url or "").strip())
        host = parsed.netloc.replace("www.", "").strip().lower()
        if not host:
            return ""
        return f"https://www.google.com/s2/favicons?domain={host}&sz=256"

    if isinstance(entry, dict):
        normalized = dict(entry)
        normalized.setdefault("url", "")
        normalized.setdefault("group_name", "")
        normalized["orgImageUrl"] = (
            normalized.get("orgImageUrl")
            or normalized.get("org_image_url")
            or normalized.get("image_url")
            or _fallback_org_image_url(normalized.get("url"))
        )
        normalized["tags"] = list(normalized.get("tags") or [])
        return normalized

    if legacy_kind == "Luma Users" and isinstance(entry, str) and not entry.startswith("http"):
        source_url = f"https://api.lu.ma/user/profile/events-hosting?user_api_id={entry}"
        return {
            "url": source_url,
            "tags": [],
            "group_name": "",
            "orgImageUrl": _fallback_org_image_url(source_url),
            "user_api_id": entry,
        }

    if isinstance(entry, str):
        return {
            "url": entry,
            "tags": [],
            "group_name": "",
            "orgImageUrl": _fallback_org_image_url(entry),
        }

    if isinstance(entry, int) and legacy_kind == "GDGChapters":
        source_url = f"https://gdg.community.dev/chapter/{entry}"
        return {
            "url": source_url,
            "tags": [],
            "group_name": "",
            "orgImageUrl": _fallback_org_image_url(source_url),
            "chapter_id": entry,
        }

    source_url = str(entry)
    return {
        "url": source_url,
        "tags": [],
        "group_name": "",
        "orgImageUrl": _fallback_org_image_url(source_url),
    }


def flatten_sources(raw_sources):
    if isinstance(raw_sources, list):
        return [normalize_source_entry(entry) for entry in raw_sources]

    flattened = []
    for legacy_kind, entries in (raw_sources or {}).items():
        for entry in entries:
            normalized = normalize_source_entry(entry, legacy_kind=legacy_kind)
            normalized.setdefault("legacy_kind", legacy_kind)
            flattened.append(normalized)
    return flattened


def infer_source_kind(source_url):
    if not source_url:
        return None

    parsed = urlparse(source_url)
    host = parsed.netloc.lower()
    path = parsed.path or ""
    segments = [segment for segment in path.split("/") if segment]

    if "meetup.com" in host:
        return "meetup"

    if "eventbrite." in host:
        if path.startswith("/o/") or path.startswith("/cc/"):
            return "eventbrite_org"
        return "eventbrite_event"

    if "jotform.com" in host:
        return "jotform"

    if host == "partiful.com" and path.startswith("/e/"):
        return "partiful"

    if (host == "forms.gle") or (host == "docs.google.com" and "/forms/" in path):
        return "google_form"

    if host == "api.lu.ma" and path == "/user/profile/events-hosting":
        return "luma_user"

    if host in {"lu.ma", "luma.com"}:
        if path.startswith("/calendar/") or (path and not path.startswith("/")):
            return "luma_calendar"
        if path.startswith("/user/"):
            return "luma_org"
        if len(segments) == 1 and re.fullmatch(r"[A-Za-z0-9]{8}", segments[0]):
            return "luma_event"
        if len(segments) == 1:
            return "luma_org"

    if "gdg.community.dev" in host:
        return "gdg"

    if "legistar.com" in host and ("calendar.aspx" in path.lower() or "view.ashx" in path.lower()):
        return "legistar"

    if host.endswith(".maryland.gov") and path.lower().startswith("/pages/"):
        return "web_events_page"

    if host == "my.thread.org" and path.startswith("/api/v2/help_center/") and "articles.json" in path:
        return "thread_helpcenter_api"

    if host in {"bniajfi.org", "www.bniajfi.org"} and path.startswith("/currentprojects/baltimore-community-change-events/"):
        return "bniajfi_community_change_events"

    if host in {"sjbc.org", "www.sjbc.org"} and path.rstrip("/") == "/events":
        return "sjbc_events"

    if host in {"baltimorecancersupportgroup.org", "www.baltimorecancersupportgroup.org"}:
        if parse_qs(parsed.query).get("page_id") == ["53"]:
            return "web_events_page"

    if host == "www.managefibromyalgia.org" and "supportgroup" in path.lower():
        return "web_events_page"

    if host == "www.vitality101.com" and path.startswith("/node/"):
        return "web_events_page"

    lower_path = path.lower()
    segment_calendar_like = any(
        re.search(r"(event|calendar|schedule|whatson|what-s-on)", segment.lower())
        for segment in segments
    )
    calendar_like_path = segment_calendar_like or any(
        marker in lower_path
        for marker in ["/events", "/event", "/calendar", "eventcalendar", "whatson", "/schedule"]
    )
    if calendar_like_path:
        return "web_events_page"

    return None


def extract_luma_user_id(source):
    if source.get("user_api_id"):
        return source["user_api_id"]

    parsed = urlparse(source.get("url", ""))
    query = parse_qs(parsed.query)
    values = query.get("user_api_id")
    return values[0] if values else None


def extract_gdg_chapter_id(source):
    if source.get("chapter_id"):
        return source["chapter_id"]

    match = re.search(r"/chapter/(\d+)", source.get("url", ""))
    if match:
        return int(match.group(1))

    return None


def coerce_events(payload):
    if not payload:
        return []
    if isinstance(payload, list):
        return [event for event in payload if isinstance(event, dict) and not event.get("error")]
    if isinstance(payload, dict):
        return [] if payload.get("error") else [payload]
    return []


def apply_source_metadata(events, source):
    normalized_events = coerce_events(events)
    source_url = source.get("url", "")
    source_tags = source.get("tags", [])
    source_group = str(source.get("group_name") or source.get("name") or "").strip()
    if not source_group and source_url:
        parsed = urlparse(source_url)
        source_group = parsed.netloc.replace("www.", "").strip()
    org_image_url = source.get("orgImageUrl") or source.get("org_image_url") or source.get("image_url") or ""
    if not org_image_url and source_url:
        parsed = urlparse(source_url)
        host = parsed.netloc.replace("www.", "").strip().lower()
        if host:
            org_image_url = f"https://www.google.com/s2/favicons?domain={host}&sz=256"

    for event in normalized_events:
        event["tags"] = merge_tags(source_tags, event.get("tags"))
        if source_url:
            event.setdefault("source", source_url)
            event["source_url"] = source_url
        if source_group:
            event.setdefault("source_group", source_group)
            # Canonical org display name for downstream consumers.
            event.setdefault("org_name", source_group)
            event.setdefault("orgName", source_group)
        if org_image_url and not str(event.get("orgImageUrl") or "").strip():
            event["orgImageUrl"] = org_image_url

    return normalized_events


def ensure_org_name_fields(events):
    for event in events or []:
        if not isinstance(event, dict):
            continue
        candidate = (
            str(event.get("org_name") or event.get("orgName") or event.get("source_group") or event.get("group_name") or "").strip()
        )
        if not candidate:
            source_url = str(event.get("source") or event.get("source_url") or "").strip()
            if source_url:
                parsed = urlparse(source_url)
                candidate = parsed.netloc.replace("www.", "").strip()
        if candidate:
            event["org_name"] = candidate
            event["orgName"] = candidate


def canonicalize_event_branding(events):
    for event in events or []:
        if not isinstance(event, dict):
            continue
        name = normalize_event_text(event.get("name", ""))
        source_group = normalize_event_text(event.get("source_group", ""))
        org_name = normalize_event_text(event.get("orgName") or event.get("org_name") or "")
        tags = [normalize_event_text(tag) for tag in (event.get("tags") or [])]

        is_code_collective_named = "code collective" in name
        is_code_collective_tagged = any("code collective" in tag for tag in tags)
        is_code_collective_sourced = "code collective" in source_group or "code collective" in org_name

        if not (is_code_collective_named or is_code_collective_tagged or is_code_collective_sourced):
            continue

        # Canonical org identity for Code Collective events, regardless of source importer.
        event["org_name"] = "Code Collective"
        event["orgName"] = "Code Collective"
        event["source_group"] = "Code Collective"

        org_image_url = str(event.get("orgImageUrl") or "").strip().lower()
        if (not org_image_url) or ("baltimoreindiegames" in org_image_url) or ("big_small" in org_image_url):
            event["orgImageUrl"] = "/images/codecollective.webp"


def source_pattern_details(source):
    parsed = urlparse(source.get("url", ""))
    segments = [segment for segment in parsed.path.split("/") if segment]
    return {
        "url": source.get("url", ""),
        "host": parsed.netloc.lower(),
        "path": parsed.path,
        "path_segments": segments,
    }


def _classify_event_city(event, fallback_city=None):
    determination = determine_event_city(
        event,
        cities=CALENDAR_CITIES,
        fallback_city=fallback_city,
    )
    event["city_determinant"] = determination
    assigned_city = determination.get("city")
    if assigned_city:
        event["city"] = assigned_city
    return assigned_city


def _load_multicity_source_payload():
    global _MULTICITY_SOURCE_CACHE
    if _MULTICITY_SOURCE_CACHE is not None:
        return copy.deepcopy(_MULTICITY_SOURCE_CACHE["events"]), copy.deepcopy(_MULTICITY_SOURCE_CACHE["errors"])

    multicity_events, unmatched_sources, scrape_errors = collect_source_events(
        MULTICITY_BUCKET,
        flatten_sources=flatten_sources,
        fetch_all_sources=fetch_all_sources,
    )
    write_unmatched_sources(MULTICITY_BUCKET, unmatched_sources)
    _MULTICITY_SOURCE_CACHE = {
        "events": multicity_events,
        "errors": scrape_errors,
    }
    return copy.deepcopy(multicity_events), copy.deepcopy(scrape_errors)


def _route_multicity_events_to_city(multicity_events, target_city):
    routed_events = []
    for event in multicity_events:
        event_copy = copy.deepcopy(event)
        assigned_city = _classify_event_city(event_copy)
        if assigned_city == target_city:
            routed_events.append(event_copy)
    return routed_events


def build_error_entry(city, stage, error, source_url=None, source_kind=None, scraper=None, context=None):
    entry = {
        "timestamp": datetime.datetime.now(est_timezone).isoformat(),
        "city": city,
        "stage": stage,
        "error": str(error),
    }
    if source_url:
        entry["source_url"] = source_url
    if source_kind:
        entry["source_kind"] = source_kind
    if scraper:
        entry["scraper"] = scraper
    if context:
        entry["context"] = context
    if isinstance(error, BaseException):
        entry["error_type"] = type(error).__name__
        entry["traceback"] = traceback.format_exc()
    return entry


def fetch_events_from_source(source, city):
    source_url = source.get("url", "")
    source_kind = infer_source_kind(source_url)
    unmatched_sources = []
    error_entries = []

    def fetch_meetup():
        upcoming_page_content = scrape_meetup.fetch_meetup_page(source_url)
        meetup_token = sanitize_event_name(source_url, max_length=48)
        meetup_cache_path = os.path.join(
            "/tmp",
            f"codecollective_{city}_meetup_upcoming_{meetup_token}.html",
        )
        with open(meetup_cache_path, "w+", encoding="utf-8") as f:
            f.write(upcoming_page_content)

        upcoming_next_data = scrape_meetup.extract_next_data(upcoming_page_content)
        return scrape_meetup.parse_meetup_events(
            upcoming_next_data,
            include_past=False,
            source_url=source_url,
        )

    source_fetchers = {
        "meetup": ("Fetching events from", fetch_meetup),
        "eventbrite_event": (
            "Fetching events from",
            lambda: scrape_eventbrite.parse_eventbrite_event(source_url),
        ),
        "eventbrite_org": (
            "Fetching org events from",
            lambda: scrape_eventbrite_org.scrape_eventbrite_organizer(source_url),
        ),
        "jotform": (
            "Fetching events from",
            lambda: scrape_jotform.parse_jotform_event(source_url),
        ),
        "luma_event": (
            "Fetching events from",
            lambda: scrape_luma.parse_luma_event_page(source_url),
        ),
        "partiful": (
            "Fetching events from",
            lambda: scrape_partiful.parse_partiful_event(source_url),
        ),
        "luma_org": (
            "Fetching events from",
            lambda: scrape_luma_orgpage.fetch_and_parse_luma_events(source_url),
        ),
        "luma_calendar": (
            "Fetching events from",
            lambda: scrape_luma_calendar.scrape(source_url),
        ),
        "google_form": (
            "Fetching events from",
            lambda: scrape_gform.scrape(source_url),
        ),
        "web_events_page": (
            "Fetching events from",
            lambda: scrape_web_events.parse_web_events_page(source_url),
        ),
        "legistar": (
            "Fetching events from",
            lambda: scrape_legistar.scrape(source_url),
        ),
        "thread_helpcenter_api": (
            "Fetching events from",
            lambda: scrape_thread_helpcenter.scrape_thread_helpcenter_events(source_url),
        ),
        "bniajfi_community_change_events": (
            "Fetching events from",
            lambda: scrape_bniajfi.scrape_bniajfi_community_change_events(source_url),
        ),
        "sjbc_events": (
            "Fetching events from",
            lambda: importlib.import_module("baltimore.scrape_sjbc").scrape_events(source_url),
        ),
    }

    try:
        if source_kind == "luma_user":
            user_api_id = extract_luma_user_id(source)
            if not user_api_id:
                unmatched_sources.append(
                    {
                        **source_pattern_details(source),
                        "reason": "missing_luma_user_api_id",
                    }
                )
                return [], unmatched_sources, error_entries
            print(f"Fetching events from {source_url}")
            return apply_source_metadata(
                scrape_luma_user.fetch_and_convert_luma_events(user_api_id, fallback_url=source_url),
                source,
            ), unmatched_sources, error_entries

        if source_kind == "gdg":
            chapter_id = extract_gdg_chapter_id(source)
            if chapter_id is None:
                unmatched_sources.append(
                    {
                        **source_pattern_details(source),
                        "reason": "missing_gdg_chapter_id",
                    }
                )
                return [], unmatched_sources, error_entries
            print(f"Fetching GDG Chapter {chapter_id}")
            return apply_source_metadata(scrape_gdg.scrapeChapterID(chapter_id), source), unmatched_sources, error_entries

        fetcher_entry = source_fetchers.get(source_kind)
        if fetcher_entry:
            label, fetcher = fetcher_entry
            print(f"{label} {source_url}")
            return apply_source_metadata(fetcher(), source), unmatched_sources, error_entries

        unmatched_sources.append(
            {
                **source_pattern_details(source),
                "reason": "unknown_source_pattern",
            }
        )
        return [], unmatched_sources, error_entries

    except Exception as e:
        print(e)
        error_entries.append(
            build_error_entry(
                city=city,
                stage="source_fetch",
                error=e,
                source_url=source_url,
                source_kind=source_kind or "unknown",
            )
        )
        return [], unmatched_sources, error_entries


def fetch_all_sources(sources, city, max_workers=6):
    if not sources:
        return [], [], []

    new_events = []
    unmatched_sources = []
    scrape_errors = []

    grouped_sources = {}
    for index, source in enumerate(sources):
        source_kind = infer_source_kind(source.get("url", "")) or "unknown"
        grouped_sources.setdefault(source_kind, []).append((index, source))

    ordered_results = []
    futures = {}
    executors = []

    try:
        for source_kind, grouped_entries in grouped_sources.items():
            kind_limit = SOURCE_KIND_CONCURRENCY.get(source_kind, SOURCE_KIND_CONCURRENCY["unknown"])
            worker_count = max(1, min(kind_limit, max_workers, len(grouped_entries)))
            executor = ThreadPoolExecutor(max_workers=worker_count)
            executors.append(executor)

            for index, source in grouped_entries:
                future = executor.submit(fetch_events_from_source, source, city)
                futures[future] = index

        for future in as_completed(futures):
            index = futures[future]
            events, unmatched, errors = future.result()
            ordered_results.append((index, events, unmatched, errors))
    finally:
        for executor in executors:
            executor.shutdown(wait=True)

    for _, events, unmatched, errors in sorted(ordered_results, key=lambda item: item[0]):
        new_events.extend(events)
        unmatched_sources.extend(unmatched)
        scrape_errors.extend(errors)

    return new_events, unmatched_sources, scrape_errors


def parse_markdown_to_html(text):
    """Convert markdown text to HTML for ICS description"""
    if not text:
        return ""
    # Replace markdown links with HTML links first (markdown module doesn't handle this well)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
    html = markdown.markdown(text)
    return html


def extract_text_from_html(html_text):
    """Use BeautifulSoup to extract clean text from HTML"""
    if not html_text:
        return ""

    try:
        # Parse HTML with BeautifulSoup
        soup = BeautifulSoup(html_text, "html.parser")

        # Handle lists specially to preserve structure
        for ul in soup.find_all(["ul", "ol"]):
            for li in ul.find_all("li"):
                # Add bullet point to list items
                li.string = f"• {li.get_text(strip=True)}"
            # Replace the list with line breaks between items
            ul.replace_with(
                "\n".join([li.get_text(strip=True) for li in ul.find_all("li")])
            )

        # Handle line breaks and paragraphs
        for br in soup.find_all("br"):
            br.replace_with("\n")

        for p in soup.find_all("p"):
            p.append("\n")

        # Handle headers
        for header in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
            header_text = header.get_text(strip=True)
            if header_text:
                header.replace_with(f"\n{header_text}\n")

        # Extract clean text
        clean_text = soup.get_text()

        # Clean up whitespace
        clean_text = re.sub(
            r"\n\s*\n", "\n\n", clean_text
        )  # Multiple newlines to double newline
        clean_text = re.sub(
            r"[ \t]+", " ", clean_text
        )  # Multiple spaces to single space
        clean_text = clean_text.strip()

        return clean_text

    except Exception as e:
        print(f"Error parsing HTML with BeautifulSoup: {e}")
        # Fallback to simple regex if BeautifulSoup fails
        return strip_html_tags_regex(html_text)


def strip_html_tags_regex(text):
    """Fallback regex-based HTML tag removal"""
    if not text:
        return ""

    # Remove HTML tags
    clean_text = re.sub("<.*?>", "", text)

    # Convert common HTML entities
    clean_text = clean_text.replace("&amp;", "&")
    clean_text = clean_text.replace("&lt;", "<")
    clean_text = clean_text.replace("&gt;", ">")
    clean_text = clean_text.replace("&quot;", '"')
    clean_text = clean_text.replace("&#39;", "'")
    clean_text = clean_text.replace("&nbsp;", " ")

    # Remove escaped characters that aren't needed in descriptions
    clean_text = clean_text.replace("\\,", ",")
    clean_text = clean_text.replace("\\;", ";")

    # Clean up markdown remnants
    clean_text = re.sub(
        r"\\#\\#\\#\s*", "", clean_text
    )  # Remove escaped markdown headers
    clean_text = re.sub(r"#+\s*", "", clean_text)  # Remove remaining markdown headers

    # Clean up extra whitespace and newlines
    clean_text = re.sub(
        r"\n\s*\n", "\n\n", clean_text
    )  # Replace multiple newlines with double newline
    clean_text = re.sub(
        r"[ \t]+", " ", clean_text
    )  # Replace multiple spaces/tabs with single space
    clean_text = clean_text.strip()

    return clean_text


def parse_markdown_to_plain_text(markdown_text):
    """Convert markdown to plain text (removing markdown syntax)"""
    if not markdown_text:
        return ""

    # Remove markdown formatting
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", markdown_text)  # Bold
    text = re.sub(r"\*(.*?)\*", r"\1", text)  # Italic
    text = re.sub(r"`(.*?)`", r"\1", text)  # Code
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)  # Links
    text = re.sub(r"^#+\s*(.*)$", r"\1", text, flags=re.MULTILINE)  # Headers
    text = re.sub(
        r"^[\*\-\+]\s*(.*)$", r"• \1", text, flags=re.MULTILINE
    )  # Bullet points
    text = re.sub(r"^\d+\.\s*(.*)$", r"\1", text, flags=re.MULTILINE)  # Numbered lists

    return text.strip()


def sanitize_event_name(name, max_length=80):
    """Return an ASCII-only, safe name for storing event assets."""
    if not name:
        name = "event"

    normalized = unicodedata.normalize("NFKD", name)
    ascii_name = normalized.encode("ascii", "ignore").decode("ascii")
    sanitized = re.sub(r"[^A-Za-z0-9]+", "_", ascii_name).strip("_")

    if not sanitized:
        sanitized = "event"

    return sanitized[:max_length]


def normalize_event_text(value):
    if not value:
        return ""
    normalized = unicodedata.normalize("NFKD", str(value))
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    ascii_value = re.sub(r"\s+", " ", ascii_value).strip().lower()
    return ascii_value


def enrich_event_tags_by_content(events):
    """Add high-signal tags from event text when sources under-tag events."""
    if not isinstance(events, list):
        return

    food_patterns = [
        r"\bfarmers?\s+market\b",
        r"\bfood\s+bank\b",
        r"\bfood\s+pantry\b",
        r"\bhunger\b",
        r"\bsoup\s+kitchen\b",
        r"\bmeal(s)?\b",
        r"\bbrunch\b",
        r"\bbreakfast\b",
        r"\blunch\b",
        r"\bdinner\b",
        r"\bbuffet\b",
        r"\bcooking\b",
        r"\bchef\b",
        r"\bvegan\b",
        r"\bfeast\b",
        r"\bkamayan\b",
    ]

    for event in events:
        if not isinstance(event, dict):
            continue
        tags = list(event.get("tags") or [])
        tag_set = set(tags)
        text_blob = " ".join(
            [
                str(event.get("name") or ""),
                str(event.get("description") or ""),
                str((event.get("location") or {}).get("name") or ""),
            ]
        ).lower()

        if any(re.search(pattern, text_blob, re.IGNORECASE) for pattern in food_patterns):
            if "Food" not in tag_set:
                tags.append("Food")
                tag_set.add("Food")

        if tags != list(event.get("tags") or []):
            event["tags"] = tags


def get_city_default_timezone(city=None):
    timezone_name = CITY_DEFAULT_TIMEZONES.get((city or "").lower(), "UTC")
    try:
        return pytz.timezone(timezone_name)
    except Exception:
        return pytz.UTC


def _event_source_timezone(event, fallback_timezone):
    timezone_name = (
        event.get("timezone")
        or event.get("timeZone")
        or event.get("source_timezone")
        or event.get("sourceTimeZone")
    )
    if timezone_name:
        try:
            return pytz.timezone(str(timezone_name).strip())
        except Exception:
            pass
    return fallback_timezone


def parse_event_start(event, fallback_timezone=pytz.UTC):
    start_value = event.get("startDate", "")
    if not start_value:
        return None
    start_dt = parse(start_value)
    if start_dt.tzinfo is None:
        source_timezone = _event_source_timezone(event, fallback_timezone)
        start_dt = source_timezone.localize(start_dt)
    else:
        start_dt = start_dt.astimezone(utc_timezone)
    return start_dt.astimezone(utc_timezone)


def normalize_location_name(event):
    location = event.get("location") or {}
    return normalize_event_text(location.get("name") or location.get("address") or "")


def canonical_event_url_key(event):
    raw_url = (event.get("url") or "").strip()
    if not raw_url:
        return ""

    try:
        parsed = urlparse(raw_url)
    except Exception:
        return ""

    host = parsed.netloc.lower().replace("www.", "")
    path = parsed.path.rstrip("/").lower()

    if host in {"lu.ma", "luma.com"} and path:
        return f"{host}{path}"
    if "eventbrite." in host and path:
        return f"{host}{path}"
    if "meetup.com" in host and path:
        return f"{host}{path}"
    if host == "partiful.com" and path:
        return f"{host}{path}"

    return ""


def event_time_bucket(event, minutes=90):
    start_dt = parse_event_start(event)
    if not start_dt:
        return None
    total_minutes = start_dt.hour * 60 + start_dt.minute
    bucket = total_minutes // minutes
    return (start_dt.date().isoformat(), bucket)


def event_title_similarity(event_a, event_b):
    title_a = normalize_event_text(event_a.get("name", ""))
    title_b = normalize_event_text(event_b.get("name", ""))
    if not title_a or not title_b:
        return 0.0
    if title_a == title_b:
        return 1.0
    return SequenceMatcher(None, title_a, title_b).ratio()


def duplicate_match_score(event_a, event_b):
    start_a = parse_event_start(event_a)
    start_b = parse_event_start(event_b)
    if not start_a or not start_b:
        return None

    day_diff = abs((start_a.date() - start_b.date()).days)
    if day_diff > 1:
        return None

    title_similarity = event_title_similarity(event_a, event_b)
    time_delta_minutes = abs((start_a - start_b).total_seconds()) / 60
    same_bucket = event_time_bucket(event_a) == event_time_bucket(event_b)
    url_a = canonical_event_url_key(event_a)
    url_b = canonical_event_url_key(event_b)
    same_url = bool(url_a and url_b and url_a == url_b)
    location_a = normalize_location_name(event_a)
    location_b = normalize_location_name(event_b)
    same_location = bool(location_a and location_b and location_a == location_b)

    score = 0
    if same_url:
        score += 100
    if title_similarity >= 0.995:
        score += 50
    elif title_similarity >= 0.94:
        score += 35
    elif title_similarity >= 0.88:
        score += 20

    if time_delta_minutes <= 15:
        score += 25
    elif time_delta_minutes <= 90:
        score += 15
    elif time_delta_minutes <= 180:
        score += 5

    if same_bucket:
        score += 10
    if same_location:
        score += 12

    if same_url:
        return score

    if title_similarity >= 0.995 and time_delta_minutes <= 180:
        return score

    if title_similarity >= 0.94 and time_delta_minutes <= 90 and (same_location or same_bucket):
        return score

    if title_similarity >= 0.88 and time_delta_minutes <= 15 and same_location:
        return score

    return None


def find_existing_duplicate(event, existing_events):
    best_match = None
    best_score = -1

    for existing_event in existing_events:
        score = duplicate_match_score(existing_event, event)
        if score is None:
            continue
        if score > best_score:
            best_score = score
            best_match = existing_event

    return best_match


def is_code_collective_event(event):
    candidates = [
        event.get("source", ""),
        event.get("source_url", ""),
        event.get("source_group", ""),
        event.get("url", ""),
    ]
    tag_candidates = event.get("tags", []) or []

    if any(tag == "Code Collective & Partners" for tag in tag_candidates):
        return True

    return any("codecollective" in normalize_event_text(candidate) for candidate in candidates)


def event_metadata_score(event):
    description = (event.get("description") or "").strip()
    image_url = (event.get("imageUrl") or "").strip()
    org_image_url = (event.get("orgImageUrl") or "").strip()
    source_url = (event.get("source") or event.get("source_url") or "").strip()
    event_url = (event.get("url") or "").strip()
    source_group = (event.get("source_group") or "").strip()
    tags = event.get("tags") or []
    location = event.get("location") or {}
    location_name = (location.get("name") or "").strip()
    location_address = (location.get("address") or "").strip()

    is_direct_event_url = bool(event_url and source_url and event_url.rstrip("/") != source_url.rstrip("/"))
    is_source_page_url = bool(event_url and source_url and event_url.rstrip("/") == source_url.rstrip("/"))

    scrape_time = event.get("scrapeTime") or ""
    try:
        parsed_scrape_time = parse(scrape_time).isoformat() if scrape_time else ""
    except Exception:
        parsed_scrape_time = ""

    return (
        1 if is_code_collective_event(event) else 0,
        1 if description else 0,
        len(description),
        1 if image_url else 0,
        1 if org_image_url else 0,
        1 if is_direct_event_url else 0,
        0 if is_source_page_url else 1,
        1 if source_group else 0,
        len(tags),
        1 if location_name else 0,
        1 if location_address else 0,
        parsed_scrape_time,
    )


def merge_event_records(preferred_event, other_event):
    merged_event = copy.deepcopy(preferred_event)

    merged_event["tags"] = merge_tags(preferred_event.get("tags"), other_event.get("tags"))

    for field in ["description", "imageUrl", "orgImageUrl", "source_group", "url", "source", "source_url"]:
        preferred_value = merged_event.get(field)
        other_value = other_event.get(field)
        if (not preferred_value) and other_value:
            merged_event[field] = other_value

    preferred_location = merged_event.get("location") or {}
    other_location = other_event.get("location") or {}
    if other_location:
        merged_location = dict(other_location)
        merged_location.update({k: v for k, v in preferred_location.items() if v not in ("", None, [])})
        merged_event["location"] = merged_location

    if not merged_event.get("scrapeTime") and other_event.get("scrapeTime"):
        merged_event["scrapeTime"] = other_event["scrapeTime"]

    return merged_event


def choose_preferred_duplicate(existing_event, candidate_event):
    existing_score = event_metadata_score(existing_event)
    candidate_score = event_metadata_score(candidate_event)

    if candidate_score > existing_score:
        winner = merge_event_records(candidate_event, existing_event)
        loser = existing_event.copy()
        loser["invalid_reason"] = "Replaced by higher-priority duplicate"
        return winner, loser

    winner = merge_event_records(existing_event, candidate_event)
    loser = candidate_event.copy()
    loser["invalid_reason"] = "Removed as lower-priority duplicate"
    return winner, loser


def events_to_ics(events_json, city, output_file="baltimore_tech_events.ics"):
    """
    Convert event JSON data to ICS format and save to a file using icalendar library
    
    Args:
        events_json (str or list): JSON string or list of event dictionaries
        output_file (str): Path to save the ICS file
    """
    # Try to import icalendar
    try:
        from icalendar import Calendar, Event as ICalEvent
        icalendar_available = True
    except ImportError:
        print("ERROR: icalendar library not available. Cannot generate ICS file.")
        print("Please install icalendar: pip install icalendar")
        return None
    
    # Parse JSON if it's a string
    if isinstance(events_json, str):
        events = json.loads(events_json)
    else:
        events = events_json

    # Create a new calendar
    cal = Calendar()
    cal.add('prodid', f'-//{city} Tech Events//CodeCollective//')
    cal.add('version', '2.0')
    cal.add('method', 'PUBLISH')

    event_count = 0
    default_timezone = get_city_default_timezone(city)
    
    # Add each event to the calendar
    for event_data in events:
        # Create event
        event = ICalEvent()
        
        # Set basic event properties
        event.add('summary', event_data.get("name", "Unnamed Event"))
        event.add('uid', f"{event_data.get('id', '')}-{datetime.datetime.now().timestamp()}@codecollective")
        event.add('dtstamp', datetime.datetime.now(datetime.timezone.utc))
        
        # Process description
        description = event_data.get("description", "")
        
        # First extract clean text from HTML using BeautifulSoup
        clean_description = extract_text_from_html(description)
        
        # Then parse any remaining markdown
        plain_description = parse_markdown_to_plain_text(clean_description)
        plain_description = plain_description[:200]
        
        # Add location and URL information to description
        location_info = event_data.get("location", {})
        location_str = ""
        if location_info:
            location_parts = [
                location_info.get("name", ""),
                location_info.get("address", ""),
                f"{location_info.get('city', '')}, {location_info.get('state', '')} {location_info.get('country', '')}",
            ]
            location_str = ", ".join(
                [p for p in location_parts if p and p.strip() and p.strip() != ", "]
            )
        
        # Add group name if available
        group_name = event_data.get("group", "")
        group_info = f"\n\nGroup: {group_name}" if group_name else ""
        
        # Add event URL if available
        event_url = event_data.get("url", "")
        url_info = f"\n\nEvent Link: {event_url}" if event_url else ""
        
        # Combine all information for the description (plain text only)
        full_description = f"{plain_description}{group_info}{url_info}".strip()
        
        # Ensure description is not empty
        if not full_description:
            full_description = "No description available"
        
        event.add('description', full_description)
        
        # Set date/time information
        start_str = event_data.get("startDate")
        end_str = event_data.get("endTime")
        
        if start_str:
            # Parse ISO format dates
            try:
                start_time = parse(start_str)
                # Make timezone aware if needed
                if start_time.tzinfo is None:
                    source_timezone = _event_source_timezone(event_data, default_timezone)
                    start_time = source_timezone.localize(start_time)
                
                event.add('dtstart', start_time)
                
                if end_str:
                    end_time = parse(end_str)
                    if end_time.tzinfo is None:
                        source_timezone = _event_source_timezone(event_data, default_timezone)
                        end_time = source_timezone.localize(end_time)
                    event.add('dtend', end_time)
                else:
                    # Default to 2 hours if no end time specified
                    event.add('dtend', start_time + datetime.timedelta(hours=2))
                    
            except ValueError as e:
                print(f"Error parsing date for event {event_data.get('name', 'Unknown')}: {e}")
                print(f"Start date string: {start_str}")
                if end_str:
                    print(f"End date string: {end_str}")
                continue
        else:
            print(f"Warning: Event '{event_data.get('name', 'Unknown')}' has no start date, skipping...")
            continue
        
        # Set location
        if location_str:
            event.add('location', location_str)
        
        # Set URL
        if event_url:
            event.add('url', event_url)
        
        # Add to calendar
        cal.add_component(event)
        event_count += 1

    # Write the calendar to a file
    with open(output_file, "wb") as f:
        f.write(cal.to_ical())

    print(f"Calendar with {event_count} events saved to {output_file}")
    return output_file

def extract_proper_extension(url):
    """Extract proper file extension from URL, handling complex URLs with query parameters"""
    # First get the part before any query parameters
    url_without_query = url.split("?")[0]

    # Look for common image extensions in the URL
    import re

    matches = re.search(
        r"\.(jpe?g|png|gif|webp|svg|bmp)$", url_without_query, re.IGNORECASE
    )
    if matches:
        return matches.group(1).lower()

    # If we can't find a standard extension, check if there's any extension
    path_parts = url_without_query.split(".")
    if len(path_parts) > 1:
        last_part = path_parts[-1]
        # Verify it's a reasonable length for an extension
        if len(last_part) <= 5:
            return last_part.lower()

    # Default fallback to jpg for Eventbrite images (which are typically JPEG)
    return "jpg"


def download_image(url, filename):
    """Download image from URL and save to filename"""
    try:
        # Make sure the directory exists
        import os

        os.makedirs(os.path.dirname(filename), exist_ok=True)

        # Download the image
        import requests

        response = requests.get(url, stream=True)
        response.raise_for_status()

        # Save the image
        with open(filename, "wb") as file:
            for chunk in response.iter_content(chunk_size=8192):
                file.write(chunk)

        return True
    except Exception as e:
        print(f"Error downloading image from {url}: {e}")
        return False


def main(city = "baltimore"):
    newEvents = []
    cache_path = os.path.join(city, "geocode_cache.json")
    geocode_cache = load_geocode_cache(cache_path)
    cache_updated = False

    source_events, unmatched_sources, scrape_errors = collect_source_events(
        city,
        flatten_sources=flatten_sources,
        fetch_all_sources=fetch_all_sources,
    )
    newEvents += source_events

    write_unmatched_sources(city, unmatched_sources)

    if city == MULTICITY_BUCKET:
        for event in newEvents:
            _classify_event_city(event)
    elif city in CALENDAR_CITIES:
        multicity_events, multicity_errors = _load_multicity_source_payload()
        routed_multicity_events = _route_multicity_events_to_city(multicity_events, city)
        if routed_multicity_events:
            print(
                f"Routed {len(routed_multicity_events)} multicity events into {city} via city determinant."
            )
            newEvents += routed_multicity_events
        if multicity_errors:
            print(
                f"Multicity source scrape reported {len(multicity_errors)} error(s); check {MULTICITY_BUCKET}/scrape_errors.json."
            )

    def error_logger(stage, error, source_url=None, source_kind=None, scraper=None, context=None):
        entry = build_error_entry(
            city=city,
            stage=stage,
            error=error,
            source_url=source_url,
            source_kind=source_kind,
            scraper=scraper,
            context=context,
        )
        scrape_errors.append(entry)
        return entry


    # upcoming_events += scrape_equitech.scrape_equitech_tuesday()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
    }

    if city == "dc":
        dc_gen_calendar = importlib.import_module("dc.gen_calendar")
        newEvents += dc_gen_calendar.collect_events(city, error_logger=error_logger)
        
    if city == "baltimore":
        baltimore_gen_calendar = importlib.import_module("baltimore.gen_calendar")
        newEvents += baltimore_gen_calendar.collect_events(city, error_logger=error_logger)

    if city == "westvirginia":

        newEvents += scrape_ics.fetch_calendar_events(
            ICS_URL="https://wvbusinesslink.com/?post_type=tribe_events&ical=1&eventDisplay=list",
            imageURL="https://baltimoreindiegames.com/wp-content/uploads/2025/03/BIG_small.png",
            eventUrl="https://baltimoreindiegames.com/events/",
            city="westvirginia",
            preface="",
            recurring=False
        )

    if city == "virtual":
        try:
            scrape_abwippm = importlib.import_module("virtual.scrape_ABWIPPM")
            newEvents += scrape_abwippm.scrape_events()
        except Exception as e:
            print(f"Error fetching ABWIPPM events: {e}")
            error_logger("city_collect", e, scraper="virtual.scrape_ABWIPPM")

    start_dt_cache = {}
    default_timezone = get_city_default_timezone(city)

    def get_start_dt(event):
        cache_key = id(event)
        if cache_key in start_dt_cache:
            return start_dt_cache[cache_key]

        start_value = event.get("startDate")
        if not start_value:
            start_dt_cache[cache_key] = None
            return None

        try:
            parsed_start = parse(start_value)
            if parsed_start.tzinfo is None:
                source_timezone = _event_source_timezone(event, default_timezone)
                parsed_start = source_timezone.localize(parsed_start)
            else:
                parsed_start = parsed_start.astimezone(utc_timezone)
            normalized_start = parsed_start.astimezone(utc_timezone)
            start_dt_cache[cache_key] = normalized_start
            return normalized_start
        except Exception:
            start_dt_cache[cache_key] = None
            return None

    normalize_event_start_dates(newEvents, get_start_dt=get_start_dt, error_logger=error_logger)
    download_event_images(
        newEvents,
        sanitize_event_name=sanitize_event_name,
        headers=headers,
        error_logger=error_logger,
    )
    nonerror_newevents, invalid_events, today_date = split_upcoming_events(
        newEvents,
        get_start_dt=get_start_dt,
        reference_timezone=default_timezone,
    )

    sorted_events, invalid_events, dedupe_cache_updated = merge_and_dedupe_events(
        city=city,
        nonerror_newevents=nonerror_newevents,
        invalid_events=invalid_events,
        today_date=today_date,
        get_start_dt=get_start_dt,
        normalize_event_text=normalize_event_text,
        find_existing_duplicate=find_existing_duplicate,
        choose_preferred_duplicate=choose_preferred_duplicate,
        apply_geocode_cache=apply_geocode_cache,
        geocode_cache=geocode_cache,
    )
    cache_updated = cache_updated or dedupe_cache_updated

    GEOCODE = True
    if GEOCODE:
        geocoded_payload, geocode_cache_changed = geocode_upcoming_events(
            city,
            geocode_cache,
            events=sorted_events,
        )
        if geocoded_payload is not None:
            sorted_events = geocoded_payload
        cache_updated = cache_updated or geocode_cache_changed

    ensure_org_name_fields(sorted_events)
    ensure_org_name_fields(invalid_events)
    enrich_event_tags_by_content(sorted_events)
    enrich_event_tags_by_content(invalid_events)
    canonicalize_event_branding(sorted_events)
    canonicalize_event_branding(invalid_events)

    persist_calendar_outputs(
        city=city,
        sorted_events=sorted_events,
        invalid_events=invalid_events,
        scrape_errors=scrape_errors,
        events_to_ics=events_to_ics,
    )
    if GEOCODE:
        generate_events_map_page(city)
    if cache_updated:
        save_geocode_cache(geocode_cache, cache_path)
    genSimpleCalendar.main(city)


def write_root_aggregate(processed_cities):
    aggregate_cities = [city for city in processed_cities if city != MULTICITY_BUCKET]
    aggregate_events = []

    for city in aggregate_cities:
        city_events_path = os.path.join(city, "upcoming_events.json")
        if not os.path.exists(city_events_path):
            print(f"Skipping {city}: missing {city_events_path}")
            continue

        try:
            with open(city_events_path, "r", encoding="utf-8") as f:
                city_events = json.load(f)
            if isinstance(city_events, list):
                aggregate_events.extend(city_events)
            else:
                print(f"Skipping {city}: {city_events_path} is not a list")
        except Exception as e:
            print(f"Skipping {city}: unable to read {city_events_path}: {e}")

    def sort_key(event):
        if not isinstance(event, dict):
            return datetime.datetime.max.replace(tzinfo=utc_timezone), ""
        start_value = event.get("startDate", "")
        try:
            parsed_start = parse(start_value) if start_value else datetime.datetime.max
            if parsed_start.tzinfo is None:
                parsed_start = parsed_start.replace(tzinfo=utc_timezone)
            parsed_start = parsed_start.astimezone(utc_timezone)
            return parsed_start, str(event.get("name", ""))
        except Exception:
            return datetime.datetime.max.replace(tzinfo=utc_timezone), str(
                event.get("name", "")
            )

    aggregate_events.sort(key=sort_key)

    with open("upcoming_events.json", "w+", encoding="utf-8") as f:
        json.dump(aggregate_events, f, indent=4)
    events_to_ics(aggregate_events, "all-cities", output_file="cc_events.ics")
    print(
        f"Root aggregate saved from {len(aggregate_cities)} cities to upcoming_events.json and cc_events.ics."
    )

if __name__ == "__main__":
    cities = [MULTICITY_BUCKET, *CALENDAR_CITIES]
    if len(sys.argv) > 1:
        cities = sys.argv[1:]
    for city in cities:
        main(city)
    write_root_aggregate(cities)
