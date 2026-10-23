import datetime
import hashlib
import json
import time
from pathlib import Path
from urllib.parse import urlparse
import os
from io import BytesIO

import requests
from PIL import Image


def normalize_event_start_dates(events, get_start_dt, error_logger):
    for event in events:
        if "startDate" not in event:
            continue
        try:
            start_dt = get_start_dt(event)
            if start_dt is None:
                raise ValueError("Missing or invalid startDate")
            event["startDate"] = start_dt.isoformat()
        except Exception as e:
            print(f"Error converting datetime for event {event.get('name', 'Unknown')}: {e}")
            error_logger("normalize_datetime", e, context={"event_name": event.get("name", "Unknown")})


def download_event_images(events, sanitize_event_name, headers, error_logger):
    """Recheck source images daily and publish files named by their content."""
    cache_dir = Path(".cache/calendar-images")
    checked = {}
    for event in events:
        current_url = event.get("imageUrl") or ""
        image_url = current_url
        if current_url.startswith("/event_images/"):
            image_url = event.get("imageSourceUrl") or ""
            if not image_url:
                if not Path(current_url.lstrip("/")).is_file():
                    error_logger("image_download", FileNotFoundError(current_url),
                                 context={"event_name": event.get("name", "Unknown")})
                continue
        if not image_url or urlparse(image_url).scheme not in ("http", "https"):
            continue
        event["imageSourceUrl"] = image_url
        if image_url in checked:
            event["imageUrl"] = checked[image_url]
            continue
        source_hash = hashlib.sha256(image_url.encode()).hexdigest()
        cache_file = cache_dir / f"{source_hash}.json"
        cached = {}
        try:
            cached = json.loads(cache_file.read_text())
            if not isinstance(cached, dict):
                cached = {}
        except (OSError, ValueError):
            pass
        cached_url = cached.get("imageUrl", "")
        has_cache = (isinstance(cached_url, str) and cached_url.startswith("/event_images/")
                     and Path(cached_url.lstrip("/")).is_file())
        try:
            age = time.time() - float(cached.get("checked_at", 0))
        except (ValueError, TypeError):
            age = float("inf")
        if has_cache and 0 <= age < 86400:
            event["imageUrl"] = checked[image_url] = cached_url
            continue
        try:
            response = requests.get(image_url, headers=headers, timeout=10)
            response.raise_for_status()
            with Image.open(BytesIO(response.content)) as img:
                img.thumbnail((400, 400), Image.Resampling.LANCZOS)
                output = BytesIO()
                img.save(output, "WEBP", quality=80, method=6)
            payload = output.getvalue()
            version = hashlib.sha256(payload).hexdigest()[:16]
            safe_name = sanitize_event_name(event.get("name"))
            image_path = Path("event_images") / f"{safe_name}_{version}.webp"
            image_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = image_path.with_suffix(".webp.tmp")
            temporary.write_bytes(payload)
            temporary.replace(image_path)
            local_url = "/" + image_path.as_posix()
            cache_dir.mkdir(parents=True, exist_ok=True)
            temporary_cache = cache_file.with_suffix(".json.tmp")
            temporary_cache.write_text(json.dumps({"imageUrl": local_url,
                                                   "checked_at": time.time()}))
            temporary_cache.replace(cache_file)
            event["imageUrl"] = checked[image_url] = local_url
        except Exception as e:
            error_logger("image_download", e, source_url=image_url,
                         context={"event_name": event.get("name", "Unknown")})
            fallback = cached_url if has_cache else current_url or image_url
            if fallback.startswith("/event_images/") and not Path(fallback.lstrip("/")).is_file():
                fallback = image_url
            event["imageUrl"] = checked[image_url] = fallback


def split_upcoming_events(events, get_start_dt, reference_timezone):
    invalid_events = []
    nonerror_newevents = []
    time_now = datetime.datetime.now(datetime.timezone.utc)
    today_date = time_now.date()

    for event in events:
        start_date = event.get("startDate")
        if not start_date:
            print(f"{event.get('name')} missing startdate ")
            event["invalid_reason"] = "missing startdate"
            invalid_events.append(event)
            continue

        start_date_time = get_start_dt(event)
        if start_date_time is None:
            event["invalid_reason"] = "invalid startdate"
            invalid_events.append(event)
            continue

        if (
            start_date_time.date() == datetime.date(2025, 6, 28)
            and "unity" not in event.get("name", "").lower()
        ):
            print(f"Skipping event on June 28, 2025: {event.get('name', 'Unknown')}")
            event["invalid_reason"] = "UNITY CONFLICT"
            invalid_events.append(event)
            continue

        if start_date_time >= time_now:
            nonerror_newevents.append(event)
        else:
            event["invalid_reason"] = "Already happened"
            invalid_events.append(event)
            print(f"{event.get('name')} already happened ")

        if "Casual Coding" in event.get("name", ""):
            event["recurring"] = True

    return nonerror_newevents, invalid_events, today_date
