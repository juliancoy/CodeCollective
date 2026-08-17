#!/usr/bin/env python3
"""Audit Kimi research evidence and emit a facet-level repair queue."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from kimi_research_quality import (
    FetchResult,
    atomic_write_json,
    atomic_write_jsonl,
    audit_facet,
    evaluate_facet,
    fetch_source,
    load_jsonl,
    normalize_url,
)


ROOT = Path(__file__).resolve().parent
DEFAULT_CHECKPOINT = ROOT / "research" / "kimi-research.jsonl"
DEFAULT_INVENTORY = ROOT / "data" / "infrastructure.json"
DEFAULT_AUDIT = ROOT / "research" / "kimi-evidence-audit.jsonl"
DEFAULT_REPAIR_QUEUE = ROOT / "research" / "kimi-repair-queue.json"
DEFAULT_REVIEW_QUEUE = ROOT / "research" / "kimi-review-queue.json"
DEFAULT_ENV_FILE = ROOT.parent / ".env.kimi"
DEFAULT_BASE_URL = "https://api.moonshot.ai/v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument("--output", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--repair-queue", type=Path, default=DEFAULT_REPAIR_QUEUE)
    parser.add_argument("--review-queue", type=Path, default=DEFAULT_REVIEW_QUEUE)
    parser.add_argument("--run-id")
    parser.add_argument("--pipeline-id")
    parser.add_argument(
        "--reuse-source-audit",
        type=Path,
        help="reuse fetched source decisions from a prior audit of the same checkpoint",
    )
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--judge", action="store_true", help="use K2.6 to verify candidate claim entailment")
    parser.add_argument("--judge-workers", type=int, default=4)
    parser.add_argument("--judge-model", default="kimi-k2.6")
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE)
    parser.add_argument(
        "--no-fetch",
        action="store_true",
        help="classify without fetching sources; no facet can become promotion-ready",
    )
    parser.add_argument("--limit", type=int, help="audit only the first N selected facilities")
    return parser.parse_args()


def select_records(
    rows: list[dict[str, Any]], run_id: str | None, pipeline_id: str | None
) -> tuple[list[dict[str, Any]], str | None]:
    if run_id:
        selected = [row for row in rows if row.get("run_id") == run_id]
        return selected, selected[-1].get("pipeline_id") if selected else pipeline_id
    if pipeline_id is None:
        pipeline_id = next(
            (row.get("pipeline_id") for row in reversed(rows) if row.get("pipeline_id")),
            None,
        )
    filtered = [row for row in rows if row.get("pipeline_id") == pipeline_id]
    latest: dict[tuple[str, str], dict[str, Any]] = {}
    for row in filtered:
        latest[(str(row.get("facility_id")), str(row.get("input_fingerprint")))] = row
    return list(latest.values()), pipeline_id


def collect_sources(rows: list[dict[str, Any]]) -> dict[str, str]:
    urls: dict[str, str] = {}
    for row in rows:
        for facet in (row.get("final_result", {}).get("facets", {}) or {}).values():
            if not isinstance(facet, dict):
                continue
            for source in facet.get("sources") or []:
                if not isinstance(source, dict) or not source.get("url"):
                    continue
                url = str(source["url"])
                urls.setdefault(normalize_url(url), url)
    return urls


def fetch_all(urls: dict[str, str], workers: int, timeout: float) -> dict[str, FetchResult]:
    results: dict[str, FetchResult] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(fetch_source, url, timeout): normalized
            for normalized, url in urls.items()
        }
        completed = 0
        for future in concurrent.futures.as_completed(futures):
            normalized = futures[future]
            results[normalized] = future.result()
            completed += 1
            if completed % 25 == 0 or completed == len(futures):
                print(f"Fetched {completed}/{len(futures)} unique sources", flush=True)
    return results


def build_audit(
    row: dict[str, Any],
    record: dict[str, Any],
    fetched: dict[str, FetchResult],
    audited_at: str,
    reused_sources: dict[tuple[str, str], list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    result_facets = row.get("final_result", {}).get("facets", {}) or {}
    decisions = {}
    for facet in row.get("requested_facets", []):
        value = result_facets.get(facet)
        reused = (reused_sources or {}).get((row["facility_id"], facet))
        if reused is not None and isinstance(value, dict):
            decisions[facet] = evaluate_facet(facet, value, reused)
        else:
            decisions[facet] = audit_facet(facet, value, record, fetched)
    counts = Counter(decision["state"] for decision in decisions.values())
    return {
        "audit_version": 1,
        "audited_at": audited_at,
        "facility_id": row.get("facility_id"),
        "facility_name": row.get("facility_name"),
        "record_type": row.get("record_type"),
        "run_id": row.get("run_id"),
        "pipeline_id": row.get("pipeline_id"),
        "input_fingerprint": row.get("input_fingerprint"),
        "research_status": row.get("status"),
        "promotion_ready": bool(decisions) and all(
            decision["promotion_ready"] for decision in decisions.values()
        ),
        "state_counts": dict(counts),
        "facets": decisions,
    }


def load_env_key(path: Path) -> str | None:
    if not path.exists():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.removeprefix("export ").split("=", 1)
        if key.strip() == "MOONSHOT_API_KEY":
            return value.strip().strip("'\"") or None
    return None


def judge_prompt(audit: dict[str, Any], facet_name: str, decision: dict[str, Any]) -> str:
    evidence = [
        {
            "title": source.get("title"),
            "publisher": source.get("publisher"),
            "url": source.get("final_url"),
            "source_class": source.get("source_class"),
            "excerpt": source.get("excerpt"),
        }
        for source in decision.get("sources", [])
        if source.get("usable") and source.get("source_class") in {"government", "court"}
    ]
    return f"""Act as a strict evidence auditor. Decide whether the supplied source excerpts directly
support every material clause in the proposed facility-specific claim. Do not use outside
knowledge. Reject a claim when an excerpt merely mentions the facility or topic, when a draft
is presented as a final decision, when current status is inferred from an old record, or when
any material date, identifier, status, or absence statement is unsupported.

Facility: {audit['facility_name']} ({audit['facility_id']})
Facet: {facet_name}
Claim: {decision.get('value')}
Basis: {decision.get('basis')}
Evidence:
{json.dumps(evidence, indent=2, ensure_ascii=False)}

Return JSON only:
{{"verdict":"supported|partial|unsupported","reason":"concise explanation","supported_urls":["..."]}}
"""


def judge_candidate(
    audit: dict[str, Any],
    facet_name: str,
    decision: dict[str, Any],
    api_key: str,
    model: str,
    timeout: float,
) -> dict[str, Any]:
    response = requests.post(
        f"{DEFAULT_BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": "You validate claim-to-source entailment conservatively."},
                {"role": "user", "content": judge_prompt(audit, facet_name, decision)},
            ],
            "thinking": {"type": "disabled"},
            "response_format": {"type": "json_object"},
            "max_tokens": 800,
        },
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    content = payload["choices"][0]["message"]["content"]
    value = json.loads(re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip(), flags=re.I))
    if value.get("verdict") not in {"supported", "partial", "unsupported"}:
        raise ValueError("judge returned an invalid verdict")
    return {
        "model": model,
        "verdict": value["verdict"],
        "reason": value.get("reason"),
        "supported_urls": value.get("supported_urls") or [],
        "usage": payload.get("usage"),
        "response_id": payload.get("id"),
    }


def apply_judgments(
    audits: list[dict[str, Any]],
    api_key: str | None,
    model: str,
    workers: int,
    timeout: float,
    reused_judgments: dict[tuple[str, str], dict[str, Any]] | None = None,
) -> None:
    candidates = []
    for audit in audits:
        for facet_name, decision in audit["facets"].items():
            if not decision.get("promotion_ready"):
                continue
            decision["lexical_candidate"] = True
            decision["promotion_ready"] = False
            decision["state"] = "candidate"
            decision["recommended_action"] = "judge"
            prior_judgment = (reused_judgments or {}).get((audit["facility_id"], facet_name))
            if prior_judgment is not None:
                finish_judgment(decision, prior_judgment)
            else:
                candidates.append((audit, facet_name, decision))
    if api_key is None:
        for _audit, _facet_name, decision in candidates:
            decision["reasons"].append("claim entailment judge has not approved this candidate")
        return
    print(f"Judging {len(candidates)} evidence candidates with {model}")
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(
                judge_candidate, audit, facet_name, decision, api_key, model, timeout
            ): (audit, facet_name, decision)
            for audit, facet_name, decision in candidates
        }
        for future in concurrent.futures.as_completed(futures):
            _audit, _facet_name, decision = futures[future]
            try:
                judgment = future.result()
            except Exception as exc:
                judgment = {
                    "model": model,
                    "verdict": "error",
                    "reason": str(exc),
                    "supported_urls": [],
                }
            finish_judgment(decision, judgment)


def finish_judgment(decision: dict[str, Any], judgment: dict[str, Any]) -> None:
    decision["judge"] = judgment
    if judgment["verdict"] == "supported":
        decision["promotion_ready"] = True
        decision["state"] = "promotion_ready"
        decision["recommended_action"] = "promote"
    else:
        decision["state"] = "review"
        decision["recommended_action"] = "research"
        decision["reasons"].append(
            "claim entailment judge did not fully support the proposed value"
        )


def repair_item(audit: dict[str, Any], source_row: dict[str, Any]) -> dict[str, Any] | None:
    failed = {
        name: decision
        for name, decision in audit["facets"].items()
        if decision.get("recommended_action") == "research"
    }
    if not failed:
        return None
    prior_queries = []
    for attempt in source_row.get("attempts", []):
        prior_queries.extend(attempt.get("search_queries") or [])
    return {
        "facility_id": audit["facility_id"],
        "facility_name": audit["facility_name"],
        "record_type": audit["record_type"],
        "input_fingerprint": audit["input_fingerprint"],
        "facets": sorted(failed),
        "evidence_gaps": {
            name: decision["reasons"] for name, decision in failed.items()
        },
        "prior_search_queries": list(dict.fromkeys(prior_queries)),
    }


def review_item(audit: dict[str, Any]) -> dict[str, Any] | None:
    facets = {
        name: {
            "action": decision.get("recommended_action"),
            "confidence": decision.get("confidence"),
            "value": decision.get("value"),
            "reasons": decision.get("reasons", []),
        }
        for name, decision in audit["facets"].items()
        if decision.get("recommended_action") in {"human_review", "regulatory_rule", "judge"}
    }
    if not facets:
        return None
    return {
        "facility_id": audit["facility_id"],
        "facility_name": audit["facility_name"],
        "record_type": audit["record_type"],
        "run_id": audit["run_id"],
        "facets": facets,
    }


def main() -> int:
    args = parse_args()
    if args.workers < 1:
        raise SystemExit("--workers must be at least 1")
    rows = load_jsonl(args.checkpoint)
    selected, pipeline_id = select_records(rows, args.run_id, args.pipeline_id)
    if args.limit is not None:
        if args.limit < 1:
            raise SystemExit("--limit must be at least 1")
        selected = selected[: args.limit]
    inventory = json.loads(args.inventory.read_text(encoding="utf-8"))
    records = {record["id"]: record for record in inventory}
    missing = sorted({row.get("facility_id") for row in selected} - set(records))
    if missing:
        raise SystemExit("checkpoint facilities missing from inventory: " + ", ".join(missing))
    urls = collect_sources(selected)
    print(
        f"Auditing {len(selected)} facilities from pipeline {pipeline_id or 'unknown'}; "
        f"{len(urls)} unique sources"
    )
    reused_sources = None
    reused_judgments = None
    if args.reuse_source_audit is not None:
        reused_rows = load_jsonl(args.reuse_source_audit)
        reused_sources = {
            (row["facility_id"], facet): decision.get("sources", [])
            for row in reused_rows
            for facet, decision in row.get("facets", {}).items()
        }
        reused_judgments = {
            (row["facility_id"], facet): decision["judge"]
            for row in reused_rows
            for facet, decision in row.get("facets", {}).items()
            if decision.get("judge")
        }
    fetched = (
        {}
        if args.no_fetch or reused_sources is not None
        else fetch_all(urls, args.workers, args.timeout)
    )
    audited_at = datetime.now(timezone.utc).isoformat()
    audits = [
        build_audit(
            row,
            records[row["facility_id"]],
            fetched,
            audited_at,
            reused_sources,
        )
        for row in selected
    ]
    api_key = None
    if args.judge:
        api_key = os.getenv("MOONSHOT_API_KEY") or load_env_key(args.env_file)
        if not api_key:
            raise SystemExit(f"--judge requires MOONSHOT_API_KEY or {args.env_file}")
    apply_judgments(
        audits,
        api_key,
        args.judge_model,
        args.judge_workers,
        args.timeout,
        reused_judgments,
    )
    for audit in audits:
        counts = Counter(decision["state"] for decision in audit["facets"].values())
        audit["state_counts"] = dict(counts)
        audit["promotion_ready"] = bool(audit["facets"]) and all(
            decision["promotion_ready"] for decision in audit["facets"].values()
        )
    source_by_id = {row["facility_id"]: row for row in selected}
    repairs = [
        item
        for audit in audits
        if (item := repair_item(audit, source_by_id[audit["facility_id"]])) is not None
    ]
    reviews = [item for audit in audits if (item := review_item(audit)) is not None]
    atomic_write_jsonl(args.output, audits)
    atomic_write_json(
        args.repair_queue,
        {
            "queue_version": 1,
            "created_at": audited_at,
            "pipeline_id": pipeline_id,
            "audit_path": str(args.output),
            "facilities": repairs,
        },
    )
    atomic_write_json(
        args.review_queue,
        {
            "queue_version": 1,
            "created_at": audited_at,
            "pipeline_id": pipeline_id,
            "audit_path": str(args.output),
            "facilities": reviews,
        },
    )
    states = Counter(
        decision["state"]
        for audit in audits
        for decision in audit["facets"].values()
    )
    reachable = sum(
        bool(source["reachable"])
        for audit in audits
        for decision in audit["facets"].values()
        for source in decision["sources"]
    )
    source_count = sum(
        len(decision["sources"])
        for audit in audits
        for decision in audit["facets"].values()
    )
    print(f"Facet states: {dict(states)}")
    print(f"Reachable citation uses: {reachable}/{source_count}")
    print(f"Repair queue: {len(repairs)} facilities -> {args.repair_queue}")
    print(f"Review queue: {len(reviews)} facilities -> {args.review_queue}")
    print(f"Audit: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
