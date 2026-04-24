#!/usr/bin/env python3
"""Build versioned, sharded USAJOBS datasets for object storage publishing."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


STATE_NAME_TO_CODE = {
    "alabama": "AL",
    "alaska": "AK",
    "arizona": "AZ",
    "arkansas": "AR",
    "california": "CA",
    "colorado": "CO",
    "connecticut": "CT",
    "delaware": "DE",
    "district of columbia": "DC",
    "florida": "FL",
    "georgia": "GA",
    "hawaii": "HI",
    "idaho": "ID",
    "illinois": "IL",
    "indiana": "IN",
    "iowa": "IA",
    "kansas": "KS",
    "kentucky": "KY",
    "louisiana": "LA",
    "maine": "ME",
    "maryland": "MD",
    "massachusetts": "MA",
    "michigan": "MI",
    "minnesota": "MN",
    "mississippi": "MS",
    "missouri": "MO",
    "montana": "MT",
    "nebraska": "NE",
    "nevada": "NV",
    "new hampshire": "NH",
    "new jersey": "NJ",
    "new mexico": "NM",
    "new york": "NY",
    "north carolina": "NC",
    "north dakota": "ND",
    "ohio": "OH",
    "oklahoma": "OK",
    "oregon": "OR",
    "pennsylvania": "PA",
    "rhode island": "RI",
    "south carolina": "SC",
    "south dakota": "SD",
    "tennessee": "TN",
    "texas": "TX",
    "utah": "UT",
    "vermont": "VT",
    "virginia": "VA",
    "washington": "WA",
    "west virginia": "WV",
    "wisconsin": "WI",
    "wyoming": "WY",
    "puerto rico": "PR",
    "guam": "GU",
    "american samoa": "AS",
    "northern mariana islands": "MP",
    "u.s. virgin islands": "VI",
    "virgin islands": "VI",
}
STATE_CODES = set(STATE_NAME_TO_CODE.values())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Shard USAJOBS dataset into versioned gzip pages.")
    parser.add_argument(
        "--input",
        default="usa/data/usajobs-lite.json.gz",
        help="Input normalized USAJOBS payload JSON or JSON.GZ.",
    )
    parser.add_argument(
        "--output-root",
        default="usa/data/publish",
        help="Output directory where versioned keys are written.",
    )
    parser.add_argument(
        "--prefix",
        default="jobs",
        help="Object key prefix for output (default: jobs).",
    )
    parser.add_argument(
        "--shard-size",
        type=int,
        default=500,
        help="Records per shard page (default: 500).",
    )
    parser.add_argument(
        "--keep-fields",
        action="store_true",
        help="Keep records as-is. Default behavior is also as-is for backward compatibility.",
    )
    return parser.parse_args()


def load_payload(path: Path) -> dict[str, Any]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("Input payload must be a JSON object")
    return payload


def normalize_text(value: Any) -> str:
    return str(value or "").strip().lower()


def infer_states(record: dict[str, Any]) -> list[str]:
    values: list[str] = []
    locations = record.get("locations")
    if isinstance(locations, list):
        values.extend(str(item or "") for item in locations)
    values.append(str(record.get("location_display") or ""))

    states: set[str] = set()
    for raw in values:
        text = raw.strip()
        if not text:
            continue

        parts = [part.strip() for part in text.split(",") if part.strip()]
        for part in parts[::-1]:
            upper = part.upper()
            lower = part.lower()
            if upper in STATE_CODES:
                states.add(upper)
                break
            if lower in STATE_NAME_TO_CODE:
                states.add(STATE_NAME_TO_CODE[lower])
                break

    if not states and record.get("remote_indicator") is True:
        return ["REMOTE"]
    if not states:
        return ["NA"]
    return sorted(states)


def sort_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def sort_key(record: dict[str, Any]) -> tuple[str, str]:
        publication = str(record.get("publication_date") or "")
        job_id = str(record.get("job_id") or "")
        return (publication, job_id)

    return sorted(records, key=sort_key, reverse=True)


def write_gzip_json(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    compressed = gzip.compress(raw, compresslevel=6)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(compressed)
    return {
        "size_bytes": len(compressed),
        "sha256": hashlib.sha256(compressed).hexdigest(),
    }


def main() -> int:
    args = parse_args()
    input_path = Path(args.input).resolve()
    output_root = Path(args.output_root).resolve()
    prefix = args.prefix.strip("/ ")
    if not prefix:
        raise ValueError("Prefix cannot be empty")
    if args.shard_size < 1:
        raise ValueError("Shard size must be >= 1")

    payload = load_payload(input_path)
    records = payload.get("records")
    if not isinstance(records, list):
        raise ValueError("Payload missing records list")

    fetched_at = str(payload.get("fetched_at") or "").strip()
    version = datetime.now(UTC).strftime("v%Y%m%dT%H%M%SZ")

    state_records: dict[str, list[dict[str, Any]]] = defaultdict(list)
    all_records: list[dict[str, Any]] = []

    for item in records:
        if not isinstance(item, dict):
            continue
        record = dict(item) if args.keep_fields else dict(item)
        all_records.append(record)
        for state_code in infer_states(record):
            state_records[state_code].append(record)

    state_records["ALL"] = all_records

    manifest: dict[str, Any] = {
        "version": version,
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "source_fetched_at": fetched_at,
        "source_record_count": len(all_records),
        "shard_size": args.shard_size,
        "prefix": prefix,
        "states": {},
    }

    for state_code in sorted(state_records.keys()):
        bucket = sort_records(state_records[state_code])
        page_count = math.ceil(len(bucket) / args.shard_size) if bucket else 0
        shards: list[dict[str, Any]] = []

        for page in range(1, page_count + 1):
            start = (page - 1) * args.shard_size
            end = start + args.shard_size
            page_records = bucket[start:end]
            key = f"{prefix}/{version}/shards/state={state_code}/page={page:04d}.json.gz"
            out_path = output_root / key
            stats = write_gzip_json(
                out_path,
                {
                    "version": version,
                    "state": state_code,
                    "page": page,
                    "page_size": args.shard_size,
                    "record_count": len(page_records),
                    "records": page_records,
                },
            )
            shards.append(
                {
                    "page": page,
                    "key": key,
                    "record_count": len(page_records),
                    "size_bytes": stats["size_bytes"],
                    "sha256": stats["sha256"],
                }
            )

        manifest["states"][state_code] = {
            "record_count": len(bucket),
            "page_count": page_count,
            "shards": shards,
        }

    manifest_key = f"{prefix}/{version}/manifest.json"
    latest_key = f"{prefix}/latest.json"
    manifest_path = output_root / manifest_key
    latest_path = output_root / latest_key
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    latest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")

    latest_payload = {
        "version": version,
        "generated_at": manifest["generated_at"],
        "manifest_key": manifest_key,
    }
    latest_path.write_text(json.dumps(latest_payload, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")

    print(json.dumps({"version": version, "manifest_key": manifest_key, "latest_key": latest_key}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
