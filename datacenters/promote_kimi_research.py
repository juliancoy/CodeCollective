#!/usr/bin/env python3
"""Promote evidence-audited Kimi facets into the canonical inventory."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from kimi_research_quality import atomic_write_json, canonical_json, load_jsonl, normalize_url
from research_inventory_with_kimi import target_context


ROOT = Path(__file__).resolve().parents[1]
DATACENTERS = ROOT / "datacenters"
DEFAULT_AUDIT = DATACENTERS / "research" / "kimi-evidence-audit.jsonl"
DEFAULT_INVENTORY = DATACENTERS / "data" / "infrastructure.json"
DEFAULT_SOURCES = DATACENTERS / "data" / "sources.json"
DEFAULT_OVERRIDES = DATACENTERS / "data" / "research-overrides.json"
DEFAULT_HISTORY = DATACENTERS / "history" / "infrastructure-history.jsonl"
SOURCE_ARRAY_BY_FACET = {
    "permit_status": "status_source_ids",
    "air_permit_status": "status_source_ids",
    "legal_status": "status_source_ids",
    "public_opposition_status": "sentiment_source_ids",
    "on_site_natural_gas_power_plant": "profile_source_ids",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument("--sources", type=Path, default=DEFAULT_SOURCES)
    parser.add_argument("--overrides", type=Path, default=DEFAULT_OVERRIDES)
    parser.add_argument("--history", type=Path, default=DEFAULT_HISTORY)
    parser.add_argument("--run-id")
    parser.add_argument("--id", action="append", default=[], help="limit promotion to a facility ID")
    parser.add_argument("--apply", action="store_true", help="publish changes; default is dry-run")
    parser.add_argument("--skip-tests", action="store_true")
    return parser.parse_args()


def file_hash_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def value_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:55] or "source"


def source_id(source: dict[str, Any]) -> str:
    label = str(source.get("publisher") or source.get("title") or "source")
    digest = hashlib.sha256(source["normalized_url"].encode()).hexdigest()[:10]
    return f"kimi-{slug(label)}-{digest}"


def load_overrides(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"version": 1, "facilities": {}}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not isinstance(value.get("facilities"), dict):
        raise SystemExit(f"Invalid research overrides file: {path}")
    return value


def append_history(path: Path, event: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")
        handle.flush()


def validate_candidates(
    inventory: list[dict[str, Any]], sources: list[dict[str, Any]], overrides: dict[str, Any]
) -> None:
    ids = [record.get("id") for record in inventory]
    if not ids or len(ids) != len(set(ids)):
        raise ValueError("candidate inventory IDs are missing or duplicated")
    source_ids = [source.get("id") for source in sources]
    if len(source_ids) != len(set(source_ids)):
        raise ValueError("candidate source IDs are duplicated")
    source_id_set = set(source_ids)
    records = {record["id"]: record for record in inventory}
    for facility_id, fields in overrides["facilities"].items():
        if facility_id not in records:
            raise ValueError(f"override facility is absent from inventory: {facility_id}")
        for field in fields:
            if field not in records[facility_id]:
                raise ValueError(f"override field is absent from {facility_id}: {field}")
    for record in inventory:
        for field in ("status_source_ids", "sentiment_source_ids", "profile_source_ids", "source_ids"):
            if field in record and not set(record.get(field) or []) <= source_id_set:
                raise ValueError(f"{record['id']} has unresolved IDs in {field}")


def main() -> int:
    args = parse_args()
    audits = load_jsonl(args.audit)
    selected_ids = set(args.id)
    if args.run_id:
        audits = [audit for audit in audits if audit.get("run_id") == args.run_id]
    if selected_ids:
        audits = [audit for audit in audits if audit.get("facility_id") in selected_ids]
    inventory = json.loads(args.inventory.read_text(encoding="utf-8"))
    sources = json.loads(args.sources.read_text(encoding="utf-8"))
    overrides = load_overrides(args.overrides)
    records = {record["id"]: record for record in inventory}
    source_by_url = {
        normalize_url(source["url"]): source
        for source in sources
        if isinstance(source.get("url"), str) and source["url"]
    }
    changes: list[dict[str, Any]] = []
    stale: list[str] = []

    for audit in audits:
        facility_id = audit["facility_id"]
        record = records.get(facility_id)
        if record is None:
            stale.append(f"{facility_id}: facility missing from canonical inventory")
            continue
        facets = tuple(audit.get("facets", {}))
        for facet_name, decision in audit.get("facets", {}).items():
            if not decision.get("promotion_ready"):
                continue
            origin = decision.get("research_origin") or {
                "input_fingerprint": audit.get("input_fingerprint"),
                "requested_facets": facets,
            }
            origin_facets = tuple(origin.get("requested_facets") or (facet_name,))
            fingerprint = hashlib.sha256(
                canonical_json(target_context(record, origin_facets)).encode()
            ).hexdigest()
            if fingerprint != origin.get("input_fingerprint"):
                stale.append(f"{facility_id} {facet_name}: canonical input changed after research")
                continue
            source_field = SOURCE_ARRAY_BY_FACET[facet_name]
            if source_field not in record:
                stale.append(f"{facility_id}: canonical record lacks {source_field}")
                continue
            supported_urls = {
                normalize_url(url)
                for url in (decision.get("judge") or {}).get("supported_urls", [])
            }
            usable_sources = [
                source
                for source in decision.get("sources", [])
                if source.get("usable") and source.get("source_class") in {"government", "court"}
                and normalize_url(source.get("final_url") or source["url"]) in supported_urls
            ]
            added_source_ids: list[str] = []
            for audited_source in usable_sources:
                normalized = audited_source["normalized_url"]
                source = source_by_url.get(normalized)
                if source is None:
                    identifier = source_id(audited_source)
                    source = {
                        "id": identifier,
                        "title": audited_source.get("title") or audited_source["final_url"],
                        "publisher": audited_source.get("publisher") or url_host(audited_source["final_url"]),
                        "document_date": audited_source.get("document_date"),
                        "retrieved_date": date.today().isoformat(),
                        "url": audited_source["final_url"],
                        "local_path": None,
                        "local_sha256": None,
                        "source_tier": f"audited {audited_source['source_class']}",
                        "used_for": (
                            f"{audit['facility_name']} {facet_name}: "
                            f"{audited_source.get('supports') or decision.get('value')}"
                        ),
                    }
                    sources.append(source)
                    source_by_url[normalized] = source
                added_source_ids.append(source["id"])
            if not added_source_ids:
                continue
            old_value = record.get(facet_name)
            new_value = decision["value"]
            old_source_ids = list(record.get(source_field) or [])
            new_source_ids = list(dict.fromkeys(old_source_ids + added_source_ids))
            record[facet_name] = new_value
            record[source_field] = new_source_ids
            if "source_ids" in record:
                record["source_ids"] = list(dict.fromkeys((record.get("source_ids") or []) + added_source_ids))
            override = overrides["facilities"].setdefault(facility_id, {})
            override[facet_name] = new_value
            override[source_field] = new_source_ids
            if "source_ids" in record:
                override["source_ids"] = record["source_ids"]
            changes.append(
                {
                    "facility_id": facility_id,
                    "facility_name": audit["facility_name"],
                    "facet": facet_name,
                    "old_value": old_value,
                    "new_value": new_value,
                    "old_source_ids": old_source_ids,
                    "new_source_ids": new_source_ids,
                    "run_id": audit.get("run_id"),
                    "pipeline_id": audit.get("pipeline_id"),
                    "input_fingerprint": audit.get("input_fingerprint"),
                    "judge": decision.get("judge"),
                    "evidence_hashes": {
                        source["final_url"]: source.get("content_sha256")
                        for source in usable_sources
                    },
                }
            )

    if stale:
        print("Skipped stale or incompatible records:")
        for message in stale:
            print(f"- {message}")
    print(f"Promotion-ready changes: {len(changes)} facets across {len({c['facility_id'] for c in changes})} facilities")
    for change in changes[:30]:
        print(f"- {change['facility_id']} {change['facet']}: {change['new_value'][:100]}")
    if len(changes) > 30:
        print(f"- ... and {len(changes) - 30} more")
    if not args.apply or not changes:
        print("Dry run only; pass --apply to publish" if changes else "Nothing to publish")
        return 0

    validate_candidates(inventory, sources, overrides)
    originals = {
        args.inventory: args.inventory.read_bytes(),
        args.sources: args.sources.read_bytes(),
        args.overrides: args.overrides.read_bytes() if args.overrides.exists() else None,
    }
    transaction_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()
    resulting_hashes = {
        "sources": value_hash(sources),
        "overrides": value_hash(overrides),
        "inventory": value_hash(inventory),
    }
    append_history(
        args.history,
        {
            "event": "promotion_prepared",
            "transaction_id": transaction_id,
            "timestamp": timestamp,
            "changes": changes,
            "resulting_hashes": resulting_hashes,
        },
    )
    try:
        atomic_write_json(args.sources, sources)
        atomic_write_json(args.overrides, overrides)
        atomic_write_json(args.inventory, inventory)
        if not args.skip_tests:
            subprocess.run(
                [sys.executable, "-m", "pytest", "-q", "tests/test_datacenters.py"],
                cwd=ROOT,
                check=True,
            )
    except Exception as exc:
        for path, content in originals.items():
            if content is None:
                path.unlink(missing_ok=True)
            else:
                temporary = path.with_name(f".{path.name}.rollback")
                temporary.write_bytes(content)
                temporary.replace(path)
        append_history(
            args.history,
            {
                "event": "promotion_rolled_back",
                "transaction_id": transaction_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error": str(exc),
            },
        )
        raise
    append_history(
        args.history,
        {
            "event": "promotion_committed",
            "transaction_id": transaction_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "change_count": len(changes),
            "resulting_hashes": resulting_hashes,
        },
    )
    print(f"Committed promotion transaction {transaction_id}")
    return 0


def url_host(url: str) -> str:
    from urllib.parse import urlparse

    return urlparse(url).hostname or "unknown publisher"


if __name__ == "__main__":
    raise SystemExit(main())
