#!/usr/bin/env python3
"""Promote audited worldwide data-center power profiles to a sparse OSM overlay."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from kimi_research_quality import atomic_write_json, load_jsonl, normalize_url


ROOT = Path(__file__).resolve().parent
DEFAULT_AUDIT = ROOT / "research" / "worldwide-datacenters" / "kimi-power-audit.jsonl"
DEFAULT_BASE = ROOT / "data" / "data-centers-openstreetmap-world.json"
FALLBACK_BASE = ROOT / "data" / "data-centers-openstreetmap-us.json"
DEFAULT_OVERLAY = ROOT / "data" / "data-centers-openstreetmap-world-enrichment.json"
DEFAULT_HISTORY = ROOT / "history" / "worldwide-datacenter-enrichment-history.jsonl"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--base", type=Path, default=DEFAULT_BASE if DEFAULT_BASE.exists() else FALLBACK_BASE)
    parser.add_argument("--overlay", type=Path, default=DEFAULT_OVERLAY)
    parser.add_argument("--history", type=Path, default=DEFAULT_HISTORY)
    parser.add_argument("--apply", action="store_true")
    return parser.parse_args()


def base_identities(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result = {}
    for feature in payload.get("features", []):
        properties = feature.get("properties") or {}
        osm_type, osm_id = properties.get("osm_type"), properties.get("osm_id")
        if osm_type and isinstance(osm_id, int):
            result[f"osm-{osm_type}-{osm_id}"] = properties
    return result


def candidate_overlay(audits: list[dict[str, Any]], base: dict[str, Any]) -> dict[str, Any]:
    identities = base_identities(base)
    records = []
    for audit in audits:
        facility_id = audit.get("facility_id")
        decision = (audit.get("facets") or {}).get("power_profile") or {}
        if not decision.get("promotion_ready") or facility_id not in identities:
            continue
        fields = decision.get("fields")
        if not isinstance(fields, dict):
            continue
        supported = {
            normalize_url(url)
            for url in (decision.get("judge") or {}).get("supported_urls", [])
        }
        sources = [
            {
                "title": source.get("title"),
                "publisher": source.get("publisher"),
                "document_date": source.get("document_date"),
                "retrieved_url": source.get("final_url") or source.get("url"),
                "source_class": source.get("source_class"),
                "content_sha256": source.get("content_sha256"),
            }
            for source in decision.get("sources", [])
            if source.get("usable")
            and normalize_url(source.get("final_url") or source.get("url") or "") in supported
        ]
        if not sources:
            continue
        properties = identities[facility_id]
        records.append(
            {
                "id": facility_id,
                "source_id": "openstreetmap",
                "osm_type": properties["osm_type"],
                "osm_id": properties["osm_id"],
                "power_profile": fields,
                "value": decision.get("value"),
                "basis": decision.get("basis"),
                "confidence": decision.get("confidence"),
                "field_evidence": decision.get("field_evidence") or {},
                "sources": sources,
                "research": {
                    "run_id": audit.get("run_id"),
                    "pipeline_id": audit.get("pipeline_id"),
                    "input_fingerprint": audit.get("input_fingerprint"),
                    "audited_at": audit.get("audited_at"),
                    "judge": decision.get("judge"),
                },
            }
        )
    records.sort(key=lambda row: (row["osm_type"], row["osm_id"]))
    return {
        "version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "base_inventory": (base.get("metadata") or {}).get("inventory"),
        "base_snapshot": (base.get("metadata") or {}).get("source_timestamp"),
        "record_count": len(records),
        "records": records,
    }


def main() -> int:
    args = parse_args()
    payload = candidate_overlay(
        load_jsonl(args.audit), json.loads(args.base.read_text(encoding="utf-8"))
    )
    digest = hashlib.sha256(json.dumps(payload["records"], sort_keys=True).encode()).hexdigest()
    print(f"Promotion-ready worldwide profiles: {payload['record_count']}")
    print(f"Candidate records SHA-256: {digest}")
    if not args.apply:
        print("Dry run only; pass --apply to write the overlay")
        return 0
    original = args.overlay.read_bytes() if args.overlay.exists() else None
    try:
        atomic_write_json(args.overlay, payload)
        args.history.parent.mkdir(parents=True, exist_ok=True)
        with args.history.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({
                "event": "worldwide_enrichment_promoted",
                "timestamp": payload["generated_at"],
                "record_count": payload["record_count"],
                "records_sha256": digest,
            }) + "\n")
    except Exception:
        if original is None:
            args.overlay.unlink(missing_ok=True)
        else:
            args.overlay.write_bytes(original)
        raise
    print(f"Wrote {args.overlay}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
