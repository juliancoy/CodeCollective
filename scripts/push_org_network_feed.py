#!/usr/bin/env python3
import argparse
import ast
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlparse

import requests

DEFAULT_CITIES = ("baltimore", "dc", "hawaii", "pittsburgh", "philadelphia", "virtual", "westvirginia")
DEFAULT_ORG_CHUNK_SIZE = 40
DEFAULT_EVENT_CHUNK_SIZE = 20


def normalize_url(value: Any) -> Optional[str]:
    if not value:
        return None
    cleaned = str(value).strip()
    if not cleaned:
        return None
    if not cleaned.lower().startswith(("http://", "https://")):
        return None
    return cleaned


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_city_sources(city_dir: Path) -> List[Dict[str, Any]]:
    source_file = city_dir / "event_sources.py"
    if not source_file.exists():
        return []
    module = ast.parse(source_file.read_text(encoding="utf-8"), filename=str(source_file))
    for node in module.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "sources":
                    value = ast.literal_eval(node.value)
                    if isinstance(value, list):
                        return [item for item in value if isinstance(item, dict)]
    return []


def derive_org_name(entry: Dict[str, Any], source_url: Optional[str]) -> str:
    for key in ("group_name", "source_group", "name"):
        value = str(entry.get(key) or "").strip()
        if value:
            return value
    if source_url:
        host = urlparse(source_url).netloc.replace("www.", "")
        if host:
            return host
    return "Organization"


def derive_host_org_name(entry: Dict[str, Any], source_url: Optional[str]) -> str:
    for key in ("group_name", "source_group"):
        value = str(entry.get(key) or "").strip()
        if value:
            return value
    if source_url:
        host = urlparse(source_url).netloc.replace("www.", "")
        if host:
            return host
    return "Organization"


def normalize_tags(raw_tags: Any, city: str) -> List[str]:
    out: List[str] = []
    if isinstance(raw_tags, list):
        for tag in raw_tags:
            text = str(tag or "").strip()
            if text:
                out.append(text)
    out.append(f"city:{city.lower()}")
    return sorted(set(out))


def render_location(raw: Any) -> Optional[str]:
    if isinstance(raw, str):
        text = raw.strip()
        return text or None
    if not isinstance(raw, dict):
        return None
    parts = []
    for key in ("name", "address", "city", "state", "postalCode", "country"):
        value = str(raw.get(key) or "").strip()
        if value:
            parts.append(value)
    if not parts and raw.get("latitude") is not None and raw.get("longitude") is not None:
        parts.append(f"{raw.get('latitude')}, {raw.get('longitude')}")
    return ", ".join(parts) if parts else None


def normalize_datetime_value(raw: Any) -> Optional[str]:
    if raw is None:
        return None
    text = str(raw).strip()
    return text or None


def build_ingest_key(event: Dict[str, Any]) -> str:
    material = "|".join(
        [
            str(event.get("city") or "").strip().lower(),
            str(event.get("host_org_source_url") or "").strip().lower(),
            str(event.get("source_url") or "").strip().lower(),
            str(event.get("title") or "").strip().lower(),
            str(event.get("starts_at") or "").strip(),
            str(event.get("ends_at") or "").strip(),
            str(event.get("location") or "").strip().lower(),
        ]
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def collect_orgs_and_events(repo_root: Path, cities: Iterable[str]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    orgs_by_key: Dict[str, Dict[str, Any]] = {}
    events_by_key: Dict[str, Dict[str, Any]] = {}

    for city in cities:
        city_dir = repo_root / city
        if not city_dir.exists():
            continue

        sources = load_city_sources(city_dir)
        for source in sources:
            source_url = normalize_url(source.get("url"))
            org_name = derive_org_name(source, source_url)
            org_image = normalize_url(source.get("orgImageUrl"))
            org_key = source_url or f"{city}:{org_name.lower()}"
            if org_key not in orgs_by_key:
                orgs_by_key[org_key] = {
                    "name": org_name,
                    "source_url": source_url,
                    "image_url": org_image,
                    "tags": normalize_tags(source.get("tags"), city),
                    "description": f"Ingested from CodeCollective {city} calendar sources",
                    "city": city,
                }
            else:
                merged = sorted(set(orgs_by_key[org_key].get("tags", []) + normalize_tags(source.get("tags"), city)))
                orgs_by_key[org_key]["tags"] = merged
                if org_name and not orgs_by_key[org_key].get("name"):
                    orgs_by_key[org_key]["name"] = org_name
                if org_image and not orgs_by_key[org_key].get("image_url"):
                    orgs_by_key[org_key]["image_url"] = org_image

        events_path = city_dir / "upcoming_events.json"
        if not events_path.exists():
            continue
        raw_events = load_json(events_path)
        if not isinstance(raw_events, list):
            continue

        for raw in raw_events:
            if not isinstance(raw, dict):
                continue
            title = str(raw.get("name") or "").strip()
            if not title:
                continue
            source_url = normalize_url(raw.get("url"))
            host_org_source_url = normalize_url(raw.get("source")) or normalize_url(raw.get("source_url"))
            host_org_name = derive_host_org_name(raw, host_org_source_url)
            host_org_image_url = normalize_url(raw.get("orgImageUrl"))
            image_url = normalize_url(raw.get("imageUrl")) or host_org_image_url
            event = {
                "title": title,
                "description": str(raw.get("description") or "").strip() or None,
                "starts_at": normalize_datetime_value(raw.get("startDate")),
                "ends_at": normalize_datetime_value(raw.get("endDate")),
                "location": render_location(raw.get("location")),
                "source_url": source_url,
                "host_org_source_url": host_org_source_url,
                "host_org_name": host_org_name,
                "host_org_image_url": host_org_image_url,
                "image_url": image_url,
                "tags": normalize_tags(raw.get("tags"), city),
                "city": city,
            }
            event["ingest_key"] = build_ingest_key(event)
            events_by_key[event["ingest_key"]] = event

            if host_org_source_url:
                org_key = host_org_source_url
                if org_key not in orgs_by_key:
                    orgs_by_key[org_key] = {
                        "name": host_org_name,
                        "source_url": host_org_source_url,
                        "image_url": host_org_image_url,
                        "tags": normalize_tags(raw.get("tags"), city),
                        "description": f"Inferred from CodeCollective {city} event feed",
                        "city": city,
                    }
                else:
                    merged = sorted(set(orgs_by_key[org_key].get("tags", []) + normalize_tags(raw.get("tags"), city)))
                    orgs_by_key[org_key]["tags"] = merged
                    if host_org_name and not orgs_by_key[org_key].get("name"):
                        orgs_by_key[org_key]["name"] = host_org_name
                    if host_org_image_url and not orgs_by_key[org_key].get("image_url"):
                        orgs_by_key[org_key]["image_url"] = host_org_image_url

    return list(orgs_by_key.values()), list(events_by_key.values())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Push calendar-generated org/event feed into org backend.")
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Path to CodeCollective repository root.",
    )
    parser.add_argument(
        "--cities",
        nargs="*",
        default=list(DEFAULT_CITIES),
        help="Cities to include (defaults to known calendar cities).",
    )
    parser.add_argument(
        "--url",
        default=os.getenv("ORG_BACKEND_INGEST_URL", "").strip(),
        help="Org backend ingest URL. Can also be set by ORG_BACKEND_INGEST_URL.",
    )
    parser.add_argument(
        "--token",
        default=os.getenv("ORG_BACKEND_INGEST_TOKEN", "").strip(),
        help="Ingest token. Can also be set by ORG_BACKEND_INGEST_TOKEN.",
    )
    parser.add_argument(
        "--org-chunk-size",
        type=int,
        default=int(os.getenv("ORG_BACKEND_ORG_CHUNK_SIZE", str(DEFAULT_ORG_CHUNK_SIZE))),
        help=f"Organizations per request (default: {DEFAULT_ORG_CHUNK_SIZE}).",
    )
    parser.add_argument(
        "--event-chunk-size",
        type=int,
        default=int(os.getenv("ORG_BACKEND_EVENT_CHUNK_SIZE", str(DEFAULT_EVENT_CHUNK_SIZE))),
        help=f"Events per request (default: {DEFAULT_EVENT_CHUNK_SIZE}).",
    )
    return parser.parse_args()


def chunks(items: List[Dict[str, Any]], size: int) -> Iterable[List[Dict[str, Any]]]:
    safe_size = max(1, size)
    for index in range(0, len(items), safe_size):
        yield items[index : index + safe_size]


def post_payload(url: str, token: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=120)
    if not resp.ok:
        raise RuntimeError(f"Ingest failed ({resp.status_code}): {resp.text}")
    return resp.json()


def main() -> int:
    args = parse_args()
    if not args.url:
        print("ORG_BACKEND_INGEST_URL is required.")
        return 1
    if not args.token:
        print("ORG_BACKEND_INGEST_TOKEN is required.")
        return 1

    repo_root = Path(args.repo_root).resolve()
    orgs, events = collect_orgs_and_events(repo_root, args.cities)
    print(f"Prepared payload with {len(orgs)} organizations and {len(events)} events.")

    generated_at = datetime.now(timezone.utc).isoformat()
    run_id = os.getenv("GITHUB_RUN_ID")
    org_count = 0
    event_count = 0

    try:
        for index, org_chunk in enumerate(chunks(orgs, args.org_chunk_size), start=1):
            data = post_payload(
                args.url,
                args.token,
                {
                    "source": "genCalendar",
                    "run_id": run_id,
                    "generated_at": generated_at,
                    "batch_type": "organizations",
                    "batch_index": index,
                    "organizations": org_chunk,
                    "events": [],
                },
            )
            org_count += int(data.get("organizations") or 0)
            print(f"Imported org batch {index}: {data.get('organizations', 0)} organizations.")

        for index, event_chunk in enumerate(chunks(events, args.event_chunk_size), start=1):
            data = post_payload(
                args.url,
                args.token,
                {
                    "source": "genCalendar",
                    "run_id": run_id,
                    "generated_at": generated_at,
                    "batch_type": "events",
                    "batch_index": index,
                    "organizations": [],
                    "events": event_chunk,
                },
            )
            event_count += int(data.get("events") or 0)
            print(f"Imported event batch {index}: {data.get('events', 0)} events.")
    except RuntimeError as exc:
        print(str(exc))
        return 1

    print(f"Ingest succeeded: {json.dumps({'ok': True, 'organizations': org_count, 'events': event_count}, indent=2)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
