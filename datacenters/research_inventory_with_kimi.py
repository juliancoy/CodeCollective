#!/usr/bin/env python3
"""Research unresolved infrastructure facets with Kimi and official web search.

The script writes append-only JSONL checkpoints. It does not modify the canonical
inventory: model-generated research must be reviewed before it enters generated
project data.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import http.server
import json
import os
import random
import re
import sys
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests


EVENT_WRITE_LOCK = threading.Lock()
DEFAULT_BASE_URL = "https://api.moonshot.ai/v1"
DEFAULT_PRIMARY_MODEL = "kimi-k2.6"
DEFAULT_ESCALATION_MODEL = "kimi-k3"
DEFAULT_FORMULA = "moonshot/web-search:latest"
DEFAULT_INPUT = Path(__file__).with_name("data") / "infrastructure.json"
DEFAULT_SOURCES = Path(__file__).with_name("data") / "sources.json"
DEFAULT_CHECKPOINT = Path(__file__).with_name("research") / "kimi-research.jsonl"
DEFAULT_EVENTS = Path(__file__).with_name("research") / "kimi-events.jsonl"
DEFAULT_ENV_FILE = Path(__file__).resolve().parent.parent / ".env.kimi"

PRICING_SNAPSHOT = {
    "as_of": "2026-08-16",
    "currency": "USD",
    "per_million_tokens": {
        "kimi-k2.6": {"cached_input": 0.16, "input": 0.95, "output": 4.00},
        "kimi-k3": {"cached_input": 0.30, "input": 3.00, "output": 15.00},
    },
    "web_search_call": 0.005,
    "web_search_fee_basis": "conservative; Formula tools may be temporarily free",
    "sources": [
        "https://platform.kimi.ai/docs/pricing/chat-k26",
        "https://platform.kimi.ai/docs/pricing/chat-k3",
        "https://platform.kimi.ai/docs/pricing/tools",
    ],
}

RESEARCHABLE_FIELDS = (
    "permit_status",
    "air_permit_status",
    "legal_status",
    "public_opposition_status",
    "on_site_natural_gas_power_plant",
    "power_profile",
)
UNRESOLVED_PATTERNS = (
    re.compile(r"\bnot (?:yet )?researched\b", re.IGNORECASE),
    re.compile(r"\bhistorical .+ permits not researched\b", re.IGNORECASE),
    re.compile(r"\bnot included in this inventory\b", re.IGNORECASE),
)
CONFIDENCE_VALUES = {"high", "medium", "low", "insufficient"}

SYSTEM_PROMPT = """You research Maryland energy infrastructure for a public inventory.
Use the web_search tool before answering. Prefer primary sources in this order:
Maryland and federal agency records, county or municipal records, court dockets,
operator filings, then reliable reporting. Directory listings and search snippets
alone are weak evidence. Distinguish a facility-specific finding from a fleet,
campus, county, or industry-wide rule. Never infer that a permit, lawsuit,
opposition, or gas plant does not exist merely because a search did not find one.

Return only one JSON object. Every factual facet value and basis must be supported
by the sources listed for that facet. Use cautious language such as "not identified
in the reviewed sources as of YYYY-MM-DD" for a well-searched absence. If evidence
is inadequate or facilities may be confused, use confidence "insufficient" and
say exactly what could not be established. Do not invent URLs, dates, agencies,
case numbers, permit numbers, or quotations."""

WORLDWIDE_POWER_SYSTEM_PROMPT = """You research physical data-center facilities worldwide for a public map.
Use the web_search tool before answering. Search in the facility's country and local
language when useful, but return normalized English JSON. Prefer government planning,
permit, regulator, grid-operator, and utility records, followed by exact-facility
operator specifications and filings. Directories and search snippets are leads only.

Never transfer a fleet, market, region, availability-zone, or portfolio figure to an
individual facility. Distinguish operating grid demand, published capacity envelope,
projected demand, IT or critical load, utility service, substation capacity, and backup
generation. Do not use backup-generator capacity as facility demand. Every non-null
number needs a facility-specific source, unit, scope, and URL. Use null when evidence
does not establish a value. Do not invent or average values."""

PROMPT_PROFILES = {
    "maryland-infrastructure": SYSTEM_PROMPT,
    "worldwide-datacenter-power": WORLDWIDE_POWER_SYSTEM_PROMPT,
}

RESEARCH_PROFILES = {
    "maryland-infrastructure": tuple(
        field for field in RESEARCHABLE_FIELDS if field != "power_profile"
    ),
    "worldwide-datacenter-power": ("power_profile",),
}


@dataclass(frozen=True)
class Target:
    record: dict[str, Any]
    facets: tuple[str, ...]
    fingerprint: str
    repair_context: dict[str, Any] | None = None


@dataclass(frozen=True)
class Stage:
    name: str
    model: str
    minimum_searches: int
    thinking: str | None = None
    reasoning_effort: str | None = None


@dataclass(frozen=True)
class ResearchRun:
    result: dict[str, Any]
    queries: list[str]
    requests: list[dict[str, Any]]


class KimiError(RuntimeError):
    """Raised for a Kimi API or response-contract failure."""


class ControlState:
    def __init__(
        self,
        run_id: str,
        pipeline_id: str,
        total: int,
        workers: int,
        verbose: bool,
        max_workers: int | None = None,
        event_path: Path | None = None,
    ):
        self.run_id = run_id
        self.pipeline_id = pipeline_id
        self.total = total
        self.max_workers = max_workers or workers
        self.active_workers = workers
        self.verbose = verbose
        self.paused = False
        self.stop_requested = False
        self.submitted = 0
        self.processed = 0
        self.status_counts = {"ok": 0, "review": 0, "error": 0}
        self.metrics = {"search_count": 0, "http_retry_count": 0, "estimated_cost_usd": 0.0}
        self.in_flight: dict[str, str] = {}
        self.started = time.monotonic()
        self.event_path = event_path
        self._event_lock = threading.Lock()
        self._condition = threading.Condition()

    def update(self, values: dict[str, Any]) -> dict[str, Any]:
        allowed = {"paused", "stop", "workers", "verbose"}
        unknown = set(values) - allowed
        if unknown:
            raise ValueError(f"unsupported controls: {', '.join(sorted(unknown))}")
        if "paused" in values and not isinstance(values["paused"], bool):
            raise ValueError("paused must be a boolean")
        if "stop" in values and values["stop"] is not True:
            raise ValueError("stop must be true")
        if "workers" in values:
            workers = values["workers"]
            if not isinstance(workers, int) or isinstance(workers, bool):
                raise ValueError("workers must be an integer")
            if not 1 <= workers <= self.max_workers:
                raise ValueError(f"workers must be between 1 and {self.max_workers}")
        if "verbose" in values and not isinstance(values["verbose"], bool):
            raise ValueError("verbose must be a boolean")
        with self._condition:
            if "paused" in values:
                self.paused = values["paused"]
            if "stop" in values:
                self.stop_requested = True
                self.paused = False
            if "workers" in values:
                self.active_workers = values["workers"]
            if "verbose" in values:
                self.verbose = values["verbose"]
            self._condition.notify_all()
            snapshot = self.snapshot_unlocked()
        if self.event_path is not None:
            with self._event_lock, self.event_path.open("a", encoding="utf-8") as events:
                write_event(
                    events,
                    {
                        "event": "control_update",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "run_id": self.run_id,
                        "pipeline_id": self.pipeline_id,
                        "changes": values,
                        "state": snapshot,
                    },
                )
        return snapshot

    def wait_until_runnable(self) -> bool:
        with self._condition:
            while self.paused and not self.stop_requested:
                self._condition.wait(timeout=1)
            return not self.stop_requested

    def mark_submitted(self, facility_id: str) -> None:
        with self._condition:
            self.submitted += 1
            self.in_flight[facility_id] = "starting"

    def mark_stage(self, facility_id: str, stage: str) -> None:
        with self._condition:
            self.in_flight[facility_id] = stage

    def mark_completed(self, entry: dict[str, Any]) -> None:
        with self._condition:
            self.processed += 1
            self.in_flight.pop(entry["facility_id"], None)
            self.status_counts[entry["status"]] += 1
            for key in self.metrics:
                value = entry["metrics"].get(key)
                if isinstance(value, (int, float)):
                    self.metrics[key] += value

    def snapshot_unlocked(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "pipeline_id": self.pipeline_id,
            "state": "stopping" if self.stop_requested else "paused" if self.paused else "running",
            "elapsed_seconds": round(time.monotonic() - self.started, 3),
            "total": self.total,
            "submitted": self.submitted,
            "processed": self.processed,
            "queued": self.total - self.submitted,
            "in_flight": dict(self.in_flight),
            "workers": self.active_workers,
            "max_workers": self.max_workers,
            "verbose": self.verbose,
            "status_counts": dict(self.status_counts),
            "metrics": {
                **self.metrics,
                "estimated_cost_usd": round(self.metrics["estimated_cost_usd"], 6),
            },
        }

    def snapshot(self) -> dict[str, Any]:
        with self._condition:
            return self.snapshot_unlocked()


def start_control_server(
    host: str, port: int, control: ControlState
) -> tuple[http.server.ThreadingHTTPServer, threading.Thread]:
    class Handler(http.server.BaseHTTPRequestHandler):
        def send_json(self, status: int, value: dict[str, Any]) -> None:
            body = json.dumps(value).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            if self.path != "/status":
                self.send_json(404, {"error": "not found"})
                return
            self.send_json(200, control.snapshot())

        def do_POST(self) -> None:
            if self.path != "/control":
                self.send_json(404, {"error": "not found"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length > 65536:
                    raise ValueError("request body is too large")
                value = json.loads(self.rfile.read(length))
                if not isinstance(value, dict):
                    raise ValueError("request body must be a JSON object")
                self.send_json(200, control.update(value))
            except (ValueError, json.JSONDecodeError) as exc:
                self.send_json(400, {"error": str(exc)})

        def log_message(self, _format: str, *_args: Any) -> None:
            return

    server = http.server.ThreadingHTTPServer((host, port), Handler)
    thread = threading.Thread(target=server.serve_forever, name="kimi-control-api", daemon=True)
    thread.start()
    return server, thread


class KimiClient:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        formula_uri: str,
        timeout: float,
        retries: int,
        max_tool_rounds: int,
        max_searches: int,
        prompt_profile: str = "auto",
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.formula_uri = formula_uri
        self.timeout = timeout
        self.retries = retries
        self.max_tool_rounds = max_tool_rounds
        self.max_searches = max_searches
        self.prompt_profile = prompt_profile
        self._local = threading.local()
        self.tools = self._request("GET", f"/formulas/{formula_uri}/tools")["tools"]

    def _session(self) -> requests.Session:
        if not hasattr(self._local, "session"):
            session = requests.Session()
            session.headers.update(
                {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "User-Agent": "CodeCollective-infrastructure-research/1.0",
                }
            )
            self._local.session = session
        return self._local.session

    def _request(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        metrics: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        started = time.monotonic()
        retry_events: list[dict[str, Any]] = []
        for attempt in range(self.retries + 1):
            try:
                response = self._session().request(
                    method,
                    self.base_url + path,
                    json=body,
                    timeout=self.timeout,
                )
            except requests.RequestException as exc:
                if attempt == self.retries:
                    self._append_request_metric(
                        metrics,
                        method,
                        path,
                        started,
                        attempt + 1,
                        retry_events,
                        error=type(exc).__name__,
                    )
                    raise KimiError(f"request failed after {attempt + 1} attempts: {exc}") from exc
                delay = self._backoff(attempt, None)
                retry_events.append(
                    {"reason": type(exc).__name__, "delay_seconds": round(delay, 3)}
                )
                continue

            if response.status_code < 400:
                try:
                    data = response.json()
                except ValueError as exc:
                    self._append_request_metric(
                        metrics,
                        method,
                        path,
                        started,
                        attempt + 1,
                        retry_events,
                        status_code=response.status_code,
                        request_id=response.headers.get("x-request-id"),
                        error="non_json_response",
                    )
                    raise KimiError("Kimi returned a non-JSON response") from exc
                self._append_request_metric(
                    metrics,
                    method,
                    path,
                    started,
                    attempt + 1,
                    retry_events,
                    status_code=response.status_code,
                    request_id=response.headers.get("x-request-id"),
                    data=data,
                )
                return data

            retryable = response.status_code in {408, 409, 429} or response.status_code >= 500
            if retryable and attempt < self.retries:
                delay = self._backoff(attempt, response.headers.get("Retry-After"))
                retry_events.append(
                    {"reason": f"http_{response.status_code}", "delay_seconds": round(delay, 3)}
                )
                continue
            try:
                detail = response.json().get("error", {}).get("message")
            except ValueError:
                detail = response.text[:500]
            self._append_request_metric(
                metrics,
                method,
                path,
                started,
                attempt + 1,
                retry_events,
                status_code=response.status_code,
                request_id=response.headers.get("x-request-id"),
                error=detail or "unknown error",
            )
            raise KimiError(f"Kimi HTTP {response.status_code}: {detail or 'unknown error'}")
        raise AssertionError("unreachable")

    @staticmethod
    def _backoff(attempt: int, retry_after: str | None) -> float:
        try:
            delay = float(retry_after) if retry_after else min(30.0, 2**attempt + random.random())
        except ValueError:
            delay = min(30.0, 2**attempt + random.random())
        time.sleep(delay)
        return delay

    @staticmethod
    def _append_request_metric(
        metrics: list[dict[str, Any]] | None,
        method: str,
        path: str,
        started: float,
        attempts: int,
        retry_events: list[dict[str, Any]],
        status_code: int | None = None,
        request_id: str | None = None,
        data: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        if metrics is None:
            return
        if path == "/chat/completions":
            kind = "chat_completion"
        elif path.endswith("/fibers"):
            kind = "formula_fiber"
        else:
            kind = "api"
        metric: dict[str, Any] = {
            "kind": kind,
            "method": method,
            "path": path,
            "status_code": status_code,
            "attempts": attempts,
            "retry_count": len(retry_events),
            "retry_events": list(retry_events),
            "elapsed_seconds": round(time.monotonic() - started, 3),
        }
        if request_id:
            metric["request_id"] = request_id
        if data:
            if data.get("id"):
                metric["response_id"] = data["id"]
            if data.get("usage"):
                metric["usage"] = data["usage"]
            if kind == "formula_fiber" and data.get("status"):
                metric["fiber_status"] = data["status"]
        if error:
            metric["error"] = error
        metrics.append(metric)

    def research(
        self,
        target: Target,
        known_sources: list[dict[str, Any]],
        stage: Stage,
        request_metrics: list[dict[str, Any]] | None = None,
        queries_out: list[str] | None = None,
        prior_result: dict[str, Any] | None = None,
        prior_queries: list[str] | None = None,
    ) -> ResearchRun:
        prior_queries = prior_queries or []
        prompt = build_user_prompt(
            target,
            known_sources,
            stage.minimum_searches,
            prior_result,
            prior_queries,
        )
        messages: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": system_prompt_for_target(
                    target,
                    getattr(self, "prompt_profile", "auto"),
                ),
            },
            {"role": "user", "content": prompt},
        ]
        queries = queries_out if queries_out is not None else []
        request_metrics = request_metrics if request_metrics is not None else []

        for _ in range(self.max_tool_rounds):
            request_body: dict[str, Any] = {
                "model": stage.model,
                "messages": messages,
                "tools": self.tools,
                "tool_choice": (
                    {
                        "type": "function",
                        "function": {"name": "web_search"},
                    }
                    if (
                        stage.thinking == "disabled"
                        and len(set(prior_queries + queries)) < stage.minimum_searches
                    )
                    else "auto"
                ),
                "response_format": {"type": "json_object"},
                "max_tokens": 8192,
            }
            if stage.thinking is not None:
                request_body["thinking"] = {"type": stage.thinking}
            if stage.reasoning_effort is not None:
                request_body["reasoning_effort"] = stage.reasoning_effort
            response = self._request(
                "POST",
                "/chat/completions",
                request_body,
                request_metrics,
            )
            try:
                message = response["choices"][0]["message"]
            except (KeyError, IndexError, TypeError) as exc:
                raise KimiError("chat completion omitted choices[0].message") from exc

            tool_calls = message.get("tool_calls") or []
            messages.append(
                {
                    key: value
                    for key, value in message.items()
                    if key in {"role", "content", "reasoning_content", "tool_calls"}
                    and value is not None
                }
            )
            if not tool_calls:
                content = message.get("content")
                if not isinstance(content, str) or not content.strip():
                    raise KimiError("final chat completion had no content")
                return ResearchRun(parse_json_object(content), queries, request_metrics)

            if len(queries) + len(tool_calls) > self.max_searches:
                raise KimiError(f"model exceeded the {self.max_searches}-search limit")
            for tool_call in tool_calls:
                function = tool_call.get("function") or {}
                if function.get("name") != "web_search":
                    raise KimiError(f"unexpected tool call: {function.get('name')!r}")
                arguments = function.get("arguments")
                if not isinstance(arguments, str):
                    raise KimiError("web_search arguments were not a JSON string")
                try:
                    query = json.loads(arguments).get("query")
                except (ValueError, AttributeError) as exc:
                    raise KimiError("web_search arguments were invalid") from exc
                if not isinstance(query, str) or not query.strip():
                    raise KimiError("web_search call omitted a query")
                queries.append(query.strip())
                fiber = self._request(
                    "POST",
                    f"/formulas/{self.formula_uri}/fibers",
                    {"name": function["name"], "arguments": arguments},
                    request_metrics,
                )
                context = fiber.get("context") or {}
                result = context.get("output") or context.get("encrypted_output")
                if not result:
                    raise KimiError("web_search formula returned no output")
                messages.append(
                    {"role": "tool", "tool_call_id": tool_call["id"], "content": result}
                )
        raise KimiError(f"model did not finish within {self.max_tool_rounds} tool rounds")


def is_unresolved(value: Any) -> bool:
    return isinstance(value, str) and any(pattern.search(value) for pattern in UNRESOLVED_PATTERNS)


def find_targets(
    records: list[dict[str, Any]],
    record_types: set[str],
    ids: set[str],
    states: set[str] | None = None,
    facet_overrides: dict[str, dict[str, Any]] | None = None,
) -> list[Target]:
    targets: list[Target] = []
    states = states or set()
    for record in records:
        if record_types and record.get("record_type") not in record_types:
            continue
        if states and str(record.get("state") or "").upper() not in states:
            continue
        if ids and record.get("id") not in ids:
            continue
        if facet_overrides is not None:
            repair = facet_overrides.get(str(record.get("id")))
            if repair is None:
                continue
            requested = repair.get("facets") or []
            facets = tuple(field for field in RESEARCHABLE_FIELDS if field in requested)
        else:
            repair = None
            facets = tuple(field for field in RESEARCHABLE_FIELDS if is_unresolved(record.get(field)))
        if not facets:
            continue
        context = target_context(record, facets)
        fingerprint = hashlib.sha256(canonical_json(context).encode()).hexdigest()
        targets.append(
            Target(
                record=record,
                facets=facets,
                fingerprint=fingerprint,
                repair_context=repair,
            )
        )
    return targets


def target_context(record: dict[str, Any], facets: tuple[str, ...]) -> dict[str, Any]:
    fields = (
        "id",
        "record_type",
        "eia_plant_code",
        "name",
        "operator",
        "owner",
        "campus",
        "street_address",
        "city",
        "county",
        "state",
        "postal_code",
        "latitude",
        "longitude",
        "primary_technology",
        "technology_tags",
        "energy_source_codes",
        "development_status",
        "status",
        "source_ids",
        "status_source_ids",
        "census_state_fips",
        "census_county_fips",
        "census_place_fips",
        "iso_region",
        "iso_zone",
        "location_tags",
        "country",
        "country_code",
        "osm_type",
        "osm_id",
        "osm_url",
        "website",
        "facility_tags",
        "research_priority",
        "reported_grid_demand_mw",
        "reported_power_capacity_mw",
        "projected_power_demand_mw",
        "estimated_power_draw_mw",
        "on_site_generation_capacity_mw",
    )
    context = {field: record.get(field) for field in fields if record.get(field) is not None}
    context["unresolved_facets"] = {field: record.get(field) for field in facets}
    return context


def build_user_prompt(
    target: Target,
    known_sources: list[dict[str, Any]],
    minimum_searches: int,
    prior_result: dict[str, Any] | None = None,
    prior_queries: list[str] | None = None,
) -> str:
    today = date.today().isoformat()
    power_profile = {
        "value": "concise scope-aware facility power summary",
        "confidence": "high | medium | low | insufficient",
        "basis": "what the cited evidence establishes and its limits",
        "fields": {
            "reported_grid_demand_mw": None,
            "reported_power_capacity_mw": None,
            "projected_power_demand_mw": None,
            "estimated_power_draw_mw": None,
            "estimated_power_draw_method": None,
            "on_site_generation_capacity_mw": None,
            "energy_source_codes": [],
            "lifecycle_status": None,
            "value_scope": "unknown",
            "as_of_date": None,
        },
        "field_evidence": {},
        "sources": [
            {
                "title": "document or page title",
                "publisher": "publisher",
                "url": "https://...",
                "document_date": "YYYY-MM-DD or null",
                "source_type": "primary government | regulator | grid operator | utility | operator | filing | news",
                "supports": "exact facility-specific claim, number, unit, and scope",
            }
        ],
    }
    schema = {
        "facility_id": target.record["id"],
        "facility_name": target.record["name"],
        "researched_at": today,
        "facets": {
            facet: power_profile if facet == "power_profile" else {
                "value": "concise inventory-ready finding",
                "confidence": "high | medium | low | insufficient",
                "basis": "what the cited evidence establishes and its limits",
                "sources": [
                    {
                        "title": "document or page title",
                        "publisher": "publisher",
                        "url": "https://...",
                        "document_date": "YYYY-MM-DD or null",
                        "source_type": "primary government | court | operator | news | directory",
                        "supports": "specific claim supported by this source",
                    }
                ],
            }
            for facet in target.facets
        },
        "research_notes": "remaining ambiguity or null",
    }
    prior_queries = prior_queries or []
    search_word = "search" if minimum_searches == 1 else "searches"
    primary_instruction = (
        "Target an official government, regulator, grid, utility, filing, or exact-facility operator source in at least one query."
        if "power_profile" in target.facets
        else "Target primary government or court records in at least one query."
    )
    return f"""Research every unresolved facet for this one facility as of {today}.
Ensure at least {minimum_searches} distinct web {search_word} have been completed
across all attempts. Prior queries listed below count toward that total. Run only
the additional searches needed to resolve evidence gaps, and do not repeat an
equivalent query. {primary_instruction}
Search alternate facility/operator names when useful. Do not research or return
facets outside the requested list.

Facility context:
{json.dumps(target_context(target.record, target.facets), indent=2, ensure_ascii=False)}

Already cataloged sources (leads only; verify claims through search):
{json.dumps(known_sources, indent=2, ensure_ascii=False)}

Queries completed by earlier attempts (do not repeat):
{json.dumps(prior_queries, indent=2, ensure_ascii=False)}

Previous validated research (reuse its cited evidence, then address its gaps):
{json.dumps(prior_result, indent=2, ensure_ascii=False)}

Evidence-audit repair context (address these failures directly):
{json.dumps(target.repair_context, indent=2, ensure_ascii=False)}

Return this exact JSON shape, with exactly these facet keys:
{json.dumps(schema, indent=2)}
"""


def parse_json_object(content: str) -> dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise KimiError(f"final response was not valid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise KimiError("final response must be a JSON object")
    return value


def facet_validation_errors(name: str, facet: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(facet, dict):
        return [f"{name}: result is not an object"]
    if not isinstance(facet.get("value"), str) or not facet["value"].strip():
        errors.append(f"{name}: value is empty")
    if facet.get("confidence") not in CONFIDENCE_VALUES:
        errors.append(f"{name}: invalid confidence")
    if not isinstance(facet.get("basis"), str) or len(facet["basis"].strip()) < 20:
        errors.append(f"{name}: basis is too short")
    sources = facet.get("sources")
    if not isinstance(sources, list) or not sources:
        errors.append(f"{name}: at least one source is required")
        return errors
    for index, source in enumerate(sources):
        if not isinstance(source, dict):
            errors.append(f"{name}: source {index + 1} is not an object")
            continue
        parsed = urlparse(str(source.get("url", "")))
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            errors.append(f"{name}: source {index + 1} has an invalid URL")
        for field in ("title", "publisher", "source_type", "supports"):
            if not isinstance(source.get(field), str) or not source[field].strip():
                errors.append(f"{name}: source {index + 1} lacks {field}")
    if name == "power_profile":
        fields = facet.get("fields")
        evidence = facet.get("field_evidence")
        required = {
            "reported_grid_demand_mw",
            "reported_power_capacity_mw",
            "projected_power_demand_mw",
            "estimated_power_draw_mw",
            "estimated_power_draw_method",
            "on_site_generation_capacity_mw",
            "energy_source_codes",
            "lifecycle_status",
            "value_scope",
            "as_of_date",
        }
        if not isinstance(fields, dict) or set(fields) != required:
            errors.append(f"{name}: fields must exactly match the power-profile schema")
            fields = fields if isinstance(fields, dict) else {}
        if not isinstance(evidence, dict):
            errors.append(f"{name}: field_evidence must be an object")
            evidence = {}
        numeric_fields = {
            "reported_grid_demand_mw",
            "reported_power_capacity_mw",
            "projected_power_demand_mw",
            "estimated_power_draw_mw",
            "on_site_generation_capacity_mw",
        }
        source_urls = {
            source.get("url") for source in sources if isinstance(source, dict)
        }
        for field in numeric_fields:
            value = fields.get(field)
            if value is not None and (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or value < 0
            ):
                errors.append(
                    f"{name}: {field} must be a nonnegative JSON number or null"
                )
            citations = evidence.get(field, [])
            if value is not None and (
                not isinstance(citations, list)
                or not citations
                or not set(citations) <= source_urls
            ):
                errors.append(f"{name}: {field} lacks matching field evidence")
        if (
            fields.get("estimated_power_draw_mw") is not None
            and not fields.get("estimated_power_draw_method")
        ):
            errors.append(f"{name}: estimated power draw requires a method")
        if not isinstance(fields.get("energy_source_codes"), list):
            errors.append(f"{name}: energy_source_codes must be an array")
        if fields.get("value_scope") not in {
            "building",
            "facility",
            "campus",
            "availability_zone",
            "portfolio",
            "unknown",
        }:
            errors.append(f"{name}: invalid value_scope")
    return errors


def validate_result(result: dict[str, Any], target: Target, queries: list[str], minimum_searches: int) -> None:
    errors: list[str] = []
    if result.get("facility_id") != target.record.get("id"):
        errors.append("facility_id does not match")
    if result.get("facility_name") != target.record.get("name"):
        errors.append("facility_name does not match")
    if len(set(queries)) < minimum_searches:
        errors.append(f"only {len(set(queries))} distinct searches; require {minimum_searches}")
    facets = result.get("facets")
    if not isinstance(facets, dict) or set(facets) != set(target.facets):
        errors.append("facet keys do not exactly match the requested facets")
        facets = facets if isinstance(facets, dict) else {}

    for name in target.facets:
        errors.extend(facet_validation_errors(name, facets.get(name)))
    if errors:
        raise KimiError("invalid research result: " + "; ".join(errors))


def salvage_result(
    result: dict[str, Any],
    target: Target,
    queries: list[str],
    minimum_searches: int,
) -> dict[str, Any] | None:
    if result.get("facility_id") != target.record.get("id"):
        return None
    if result.get("facility_name") != target.record.get("name"):
        return None
    if len(set(queries)) < minimum_searches:
        return None
    facets = result.get("facets")
    if not isinstance(facets, dict):
        return None
    valid_facets = {
        name: facets[name]
        for name in target.facets
        if name in facets and not facet_validation_errors(name, facets[name])
    }
    if not valid_facets:
        return None
    partial = {
        "facility_id": target.record["id"],
        "facility_name": target.record["name"],
        "facets": valid_facets,
    }
    for field in ("researched_at", "research_notes"):
        if field in result:
            partial[field] = result[field]
    return partial


def merge_results(
    previous: dict[str, Any] | None, current: dict[str, Any]
) -> dict[str, Any]:
    merged = dict(previous or current)
    merged.update({key: value for key, value in current.items() if key != "facets"})
    merged["facets"] = {
        **((previous or {}).get("facets") or {}),
        **(current.get("facets") or {}),
    }
    return merged


def normalize_result(
    result: dict[str, Any], target: Target
) -> tuple[dict[str, Any], list[str]]:
    facets = result.get("facets")
    if not isinstance(facets, dict):
        return result, []
    requested = set(target.facets)
    ignored = sorted(set(facets) - requested)
    if not ignored:
        return result, []
    normalized = dict(result)
    normalized["facets"] = {
        name: value for name, value in facets.items() if name in requested
    }
    return normalized, ignored


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def load_env_value(path: Path, requested_key: str) -> str | None:
    if not path.exists():
        return None
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            raise SystemExit(f"Invalid environment assignment in {path} on line {line_number}")
        key, value = line.split("=", 1)
        if key.strip() != requested_key:
            continue
        value = value.strip()
        if value[:1] in {"'", '"'}:
            quote = value[0]
            if len(value) < 2 or value[-1] != quote:
                raise SystemExit(f"Unclosed quote in {path} on line {line_number}")
            value = value[1:-1]
        else:
            value = value.split(" #", 1)[0].rstrip()
        return value or None
    return None


def numeric(value: Any) -> int:
    return int(value) if isinstance(value, (int, float)) else 0


def summarize_requests(
    requests_: list[dict[str, Any]],
    model: str,
    search_count: int,
) -> dict[str, Any]:
    prompt_tokens = 0
    completion_tokens = 0
    cached_tokens = 0
    reasoning_tokens = 0
    reported_total_tokens = 0
    for request in requests_:
        usage = request.get("usage") or {}
        prompt_tokens += numeric(usage.get("prompt_tokens", usage.get("input_tokens")))
        completion_tokens += numeric(
            usage.get("completion_tokens", usage.get("output_tokens"))
        )
        reported_total_tokens += numeric(usage.get("total_tokens"))
        input_details = usage.get("prompt_tokens_details") or usage.get("input_tokens_details") or {}
        output_details = usage.get("completion_tokens_details") or usage.get("output_tokens_details") or {}
        cached_tokens += numeric(input_details.get("cached_tokens"))
        reasoning_tokens += numeric(output_details.get("reasoning_tokens"))

    token_prices = PRICING_SNAPSHOT["per_million_tokens"].get(model)
    estimated_cost: float | None = None
    if token_prices:
        uncached_tokens = max(0, prompt_tokens - cached_tokens)
        token_cost = (
            uncached_tokens * token_prices["input"]
            + cached_tokens * token_prices["cached_input"]
            + completion_tokens * token_prices["output"]
        ) / 1_000_000
        estimated_cost = token_cost + search_count * PRICING_SNAPSHOT["web_search_call"]

    return {
        "request_count": len(requests_),
        "http_retry_count": sum(numeric(request.get("retry_count")) for request in requests_),
        "request_elapsed_seconds": round(
            sum(float(request.get("elapsed_seconds") or 0) for request in requests_), 3
        ),
        "search_count": search_count,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "cached_prompt_tokens": cached_tokens,
        "reasoning_tokens": reasoning_tokens,
        "reported_total_tokens": reported_total_tokens,
        "estimated_cost_usd": round(estimated_cost, 6) if estimated_cost is not None else None,
    }


def summarize_attempts(attempts: list[dict[str, Any]]) -> dict[str, Any]:
    summaries = [attempt.get("metrics") or {} for attempt in attempts]
    executed = [attempt for attempt in attempts if attempt.get("status") != "skipped"]
    costs = [summary.get("estimated_cost_usd") for summary in summaries]
    known_costs = [float(cost) for cost in costs if isinstance(cost, (int, float))]
    return {
        "stage_count": len(executed),
        "skipped_stage_count": len(attempts) - len(executed),
        "escalated": len(executed) > 1,
        "request_count": sum(numeric(summary.get("request_count")) for summary in summaries),
        "http_retry_count": sum(numeric(summary.get("http_retry_count")) for summary in summaries),
        "search_count": sum(numeric(summary.get("search_count")) for summary in summaries),
        "prompt_tokens": sum(numeric(summary.get("prompt_tokens")) for summary in summaries),
        "completion_tokens": sum(numeric(summary.get("completion_tokens")) for summary in summaries),
        "cached_prompt_tokens": sum(
            numeric(summary.get("cached_prompt_tokens")) for summary in summaries
        ),
        "reasoning_tokens": sum(numeric(summary.get("reasoning_tokens")) for summary in summaries),
        "estimated_cost_usd": round(sum(known_costs), 6) if known_costs else None,
    }


def load_known_sources(path: Path) -> dict[str, dict[str, Any]]:
    sources = json.loads(path.read_text())
    return {source["id"]: source for source in sources}


def sources_for_target(target: Target, registry: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    source_ids = list(
        dict.fromkeys(
            (target.record.get("source_ids") or [])
            + (target.record.get("status_source_ids") or [])
        )
    )
    fields = ("id", "title", "publisher", "document_date", "url", "source_tier", "used_for")
    return [
        {field: registry[source_id].get(field) for field in fields}
        for source_id in source_ids
        if source_id in registry
    ]


def load_completed(path: Path, pipeline_id: str) -> set[tuple[str, str]]:
    completed: set[tuple[str, str]] = set()
    if not path.exists():
        return completed
    for line_number, line in enumerate(path.read_text().splitlines(), 1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"Invalid checkpoint JSON on line {line_number}: {exc}") from exc
        if item.get("status") in {"ok", "review"} and item.get("pipeline_id") == pipeline_id:
            completed.add((item.get("facility_id"), item.get("input_fingerprint")))
    return completed


def checkpoint_entry(
    target: Target,
    run_id: str,
    pipeline_id: str,
    status: str,
    started_at: str,
    attempts: list[dict[str, Any]],
    result: dict[str, Any] | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "status": status,
        "facility_id": target.record["id"],
        "facility_name": target.record["name"],
        "record_type": target.record["record_type"],
        "requested_facets": list(target.facets),
        "input_fingerprint": target.fingerprint,
        "run_id": run_id,
        "pipeline_id": pipeline_id,
        "started_at": started_at,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "attempts": attempts,
        "metrics": summarize_attempts(attempts),
    }
    if result is not None:
        entry["final_result"] = result
        entry["final_stage"] = next(
            attempt["stage"]
            for attempt in reversed(attempts)
            if attempt["status"] in {"valid", "partial"}
        )
    if error is not None:
        entry["error"] = error
    return entry


def result_meets_threshold(result: dict[str, Any], threshold: str) -> bool:
    ranks = {"insufficient": 0, "low": 1, "medium": 2, "high": 3}
    facets = result.get("facets") or {}
    return bool(facets) and all(
        ranks.get(facet.get("confidence"), -1) >= ranks[threshold]
        for facet in facets.values()
        if isinstance(facet, dict)
    )


def pipeline_identifier(
    stages: list[Stage],
    confidence_threshold: str,
    profile: str = "maryland-infrastructure",
    prompt_profile: str = "auto",
) -> str:
    configuration = {
        "stages": [stage.__dict__ for stage in stages],
        "confidence_threshold": confidence_threshold,
        "profile": profile,
        "prompt_profile": prompt_profile,
        "schema_version": 4,
    }
    return hashlib.sha256(canonical_json(configuration).encode()).hexdigest()[:16]


def system_prompt_for_target(target: Target, prompt_profile: str = "auto") -> str:
    if prompt_profile == "auto":
        return (
            WORLDWIDE_POWER_SYSTEM_PROMPT
            if "power_profile" in target.facets
            else SYSTEM_PROMPT
        )
    return PROMPT_PROFILES[prompt_profile]


def research_one(
    client: KimiClient,
    target: Target,
    registry: dict[str, dict[str, Any]],
    stages: list[Stage],
    confidence_threshold: str,
    run_id: str,
    pipeline_id: str,
    control: ControlState | None = None,
) -> dict[str, Any]:
    started_at = datetime.now(timezone.utc).isoformat()
    attempts: list[dict[str, Any]] = []
    best_result: dict[str, Any] | None = None
    best_result_complete = False
    prior_queries: list[str] = []
    known_sources = sources_for_target(target, registry)
    for stage in stages:
        if control is not None:
            if not control.wait_until_runnable() and attempts:
                break
        if (
            stage.name == "retry"
            and best_result_complete
            and len(set(prior_queries)) >= stage.minimum_searches
        ):
            now = datetime.now(timezone.utc).isoformat()
            attempts.append(
                {
                    "stage": stage.name,
                    "model": stage.model,
                    "thinking": stage.thinking,
                    "reasoning_effort": stage.reasoning_effort,
                    "minimum_searches": stage.minimum_searches,
                    "status": "skipped",
                    "reason": "complete valid result already met cumulative search minimum",
                    "started_at": now,
                    "finished_at": now,
                    "elapsed_seconds": 0.0,
                    "requests": [],
                    "search_queries": [],
                    "prior_search_queries": list(prior_queries),
                    "metrics": summarize_requests([], stage.model, 0),
                }
            )
            continue
        if control is not None:
            control.mark_stage(target.record["id"], stage.name)
        stage_started_at = datetime.now(timezone.utc).isoformat()
        stage_started = time.monotonic()
        request_metrics: list[dict[str, Any]] = []
        stage_queries: list[str] = []
        run: ResearchRun | None = None
        normalized_result: dict[str, Any] | None = None
        ignored_facets: list[str] = []
        attempt: dict[str, Any] = {
            "stage": stage.name,
            "model": stage.model,
            "thinking": stage.thinking,
            "reasoning_effort": stage.reasoning_effort,
            "minimum_searches": stage.minimum_searches,
            "started_at": stage_started_at,
        }
        try:
            run = client.research(
                target,
                known_sources,
                stage,
                request_metrics,
                stage_queries,
                best_result,
                prior_queries,
            )
            normalized_result, ignored_facets = normalize_result(run.result, target)
            validate_result(
                normalized_result,
                target,
                prior_queries + run.queries,
                stage.minimum_searches,
            )
            attempt.update(
                {
                    "status": "valid",
                    "search_queries": run.queries,
                    "result": normalized_result,
                    "requests": run.requests,
                    "prior_search_queries": list(prior_queries),
                }
            )
            if ignored_facets:
                attempt["ignored_unrequested_facets"] = ignored_facets
            attempt["finished_at"] = datetime.now(timezone.utc).isoformat()
            attempt["elapsed_seconds"] = round(time.monotonic() - stage_started, 3)
            attempt["metrics"] = summarize_requests(
                request_metrics, stage.model, len(run.queries)
            )
            attempts.append(attempt)
            prior_queries = list(dict.fromkeys(prior_queries + run.queries))
            best_result = normalized_result
            best_result_complete = True
            if result_meets_threshold(normalized_result, confidence_threshold):
                return checkpoint_entry(
                    target,
                    run_id,
                    pipeline_id,
                    "ok",
                    started_at,
                    attempts,
                    result=normalized_result,
                )
        except Exception as exc:  # A failed tier should escalate, not lose prior evidence.
            cumulative_queries = list(dict.fromkeys(prior_queries + stage_queries))
            partial_result = None
            if normalized_result is not None:
                partial_result = salvage_result(
                    normalized_result,
                    target,
                    cumulative_queries,
                    stage.minimum_searches,
                )
            attempt.update(
                {
                    "status": "partial" if partial_result is not None else "error",
                    "error": str(exc),
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                    "elapsed_seconds": round(time.monotonic() - stage_started, 3),
                    "requests": request_metrics,
                    "search_queries": stage_queries,
                    "prior_search_queries": list(prior_queries),
                    "metrics": summarize_requests(
                        request_metrics, stage.model, len(stage_queries)
                    ),
                }
            )
            if run is not None:
                attempt["invalid_result"] = run.result
            if partial_result is not None:
                attempt["salvaged_facets"] = sorted(partial_result["facets"])
                best_result = merge_results(best_result, partial_result)
                try:
                    validate_result(
                        best_result,
                        target,
                        cumulative_queries,
                        stage.minimum_searches,
                    )
                    best_result_complete = True
                except KimiError:
                    best_result_complete = False
            if ignored_facets:
                attempt["ignored_unrequested_facets"] = ignored_facets
            attempts.append(attempt)
            prior_queries = cumulative_queries

    if best_result is not None:
        unresolved = sorted(set(target.facets) - set(best_result.get("facets") or {}))
        reason = f"final confidence remained below {confidence_threshold}"
        if unresolved:
            reason = "unresolved facets after validation: " + ", ".join(unresolved)
        return checkpoint_entry(
            target,
            run_id,
            pipeline_id,
            "review",
            started_at,
            attempts,
            result=best_result,
            error=reason,
        )
    return checkpoint_entry(
        target,
        run_id,
        pipeline_id,
        "error",
        started_at,
        attempts,
        error="all research tiers failed validation or API execution",
    )


def compact_facility_event(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "event": "facility_complete",
        "timestamp": entry["finished_at"],
        "run_id": entry["run_id"],
        "pipeline_id": entry["pipeline_id"],
        "facility_id": entry["facility_id"],
        "record_type": entry["record_type"],
        "status": entry["status"],
        "final_stage": entry.get("final_stage"),
        "metrics": entry["metrics"],
        "stages": [
            {
                "stage": attempt["stage"],
                "model": attempt["model"],
                "status": attempt["status"],
                "elapsed_seconds": attempt["elapsed_seconds"],
                "metrics": attempt["metrics"],
                "prior_search_count": len(attempt.get("prior_search_queries", [])),
                "error": attempt.get("error"),
                "requests": [
                    {
                        key: request.get(key)
                        for key in (
                            "kind",
                            "status_code",
                            "attempts",
                            "retry_count",
                            "retry_events",
                            "elapsed_seconds",
                            "request_id",
                            "response_id",
                            "fiber_status",
                            "error",
                        )
                        if request.get(key) is not None
                    }
                    for request in attempt.get("requests", [])
                ],
            }
            for attempt in entry["attempts"]
        ],
    }


def write_event(handle: Any, event: dict[str, Any]) -> None:
    with EVENT_WRITE_LOCK:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")
        handle.flush()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument(
        "--profile",
        choices=tuple(RESEARCH_PROFILES),
        default="maryland-infrastructure",
    )
    parser.add_argument(
        "--prompt-profile",
        choices=("auto", *PROMPT_PROFILES),
        default=os.getenv("KIMI_PROMPT_PROFILE", "auto"),
        help="system prompt to use; auto chooses from the requested facets",
    )
    parser.add_argument("--sources", type=Path, default=DEFAULT_SOURCES)
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--events", type=Path, default=DEFAULT_EVENTS)
    parser.add_argument(
        "--repair-queue",
        type=Path,
        help="research only facility facets listed by audit_kimi_research.py",
    )
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE)
    parser.add_argument(
        "--primary-model",
        default=os.getenv("KIMI_PRIMARY_MODEL", DEFAULT_PRIMARY_MODEL),
    )
    parser.add_argument(
        "--escalation-model",
        default=os.getenv("KIMI_ESCALATION_MODEL", DEFAULT_ESCALATION_MODEL),
    )
    parser.add_argument("--base-url", default=os.getenv("MOONSHOT_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--formula-uri", default=DEFAULT_FORMULA)
    parser.add_argument("--record-type", action="append", choices=("power_plant", "data_center"), default=[])
    parser.add_argument(
        "--state",
        action="append",
        type=str.upper,
        default=[],
        help="restrict research to these state abbreviations; repeatable",
    )
    parser.add_argument(
        "--country",
        action="append",
        type=str.upper,
        default=[],
        help="restrict research to ISO country codes; repeatable",
    )
    parser.add_argument(
        "--priority",
        action="append",
        type=int,
        default=[],
        help="restrict research to prepared priority values; repeatable",
    )
    parser.add_argument("--id", action="append", default=[], help="research only this facility ID; repeatable")
    parser.add_argument("--limit", type=int, help="maximum number of pending facilities")
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument(
        "--max-workers",
        type=int,
        default=16,
        help="executor capacity available to REST worker changes",
    )
    parser.add_argument("--progress-every", type=int, default=25)
    parser.add_argument("--heartbeat-seconds", type=float, default=30.0)
    parser.add_argument("--verbose", action="store_true", help="print every facility completion")
    parser.add_argument("--control-host", default="127.0.0.1")
    parser.add_argument(
        "--control-port",
        type=int,
        default=0,
        help="localhost REST control port; 0 disables the server",
    )
    parser.add_argument("--timeout", type=float, default=180)
    parser.add_argument("--retries", type=int, default=5)
    parser.add_argument("--max-tool-rounds", type=int, default=8)
    parser.add_argument("--max-searches", type=int, default=8)
    parser.add_argument("--primary-minimum-searches", type=int, default=1)
    parser.add_argument("--retry-minimum-searches", type=int, default=2)
    parser.add_argument("--escalation-minimum-searches", type=int, default=2)
    parser.add_argument(
        "--confidence-threshold",
        choices=("low", "medium", "high"),
        default="medium",
    )
    parser.add_argument(
        "--max-tier",
        choices=("primary", "retry", "escalation"),
        default="escalation",
        help="highest cost tier the pipeline may use",
    )
    parser.add_argument("--force", action="store_true", help="ignore successful matching checkpoints")
    parser.add_argument("--dry-run", action="store_true", help="show work without calling Kimi")
    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> None:
    numeric_options = (
        "workers",
        "max_workers",
        "progress_every",
        "retries",
        "max_tool_rounds",
        "max_searches",
        "primary_minimum_searches",
        "retry_minimum_searches",
        "escalation_minimum_searches",
    )
    for name in numeric_options:
        if getattr(args, name) < (0 if name == "retries" else 1):
            raise SystemExit(f"--{name.replace('_', '-')} has an invalid value")
    minimum_searches = (
        args.primary_minimum_searches,
        args.retry_minimum_searches,
        args.escalation_minimum_searches,
    )
    tier_count = {"primary": 1, "retry": 2, "escalation": 3}[args.max_tier]
    if any(value > args.max_searches for value in minimum_searches[:tier_count]):
        raise SystemExit("minimum searches cannot exceed --max-searches")
    if args.limit is not None and args.limit < 1:
        raise SystemExit("--limit must be at least 1")
    if args.heartbeat_seconds <= 0:
        raise SystemExit("--heartbeat-seconds must be greater than zero")
    if args.workers > args.max_workers:
        raise SystemExit("--workers cannot exceed --max-workers")
    if args.control_host not in {"127.0.0.1", "localhost", "::1"}:
        raise SystemExit("--control-host must be a loopback address")
    if not 0 <= args.control_port <= 65535:
        raise SystemExit("--control-port must be between 0 and 65535")
    if getattr(args, "prompt_profile", "auto") not in {"auto", *PROMPT_PROFILES}:
        raise SystemExit("--prompt-profile must be auto, maryland-infrastructure, or worldwide-datacenter-power")


def main() -> int:
    args = parse_args()
    validate_args(args)
    run_id = str(uuid.uuid4())
    stages = [
        Stage(
            name="primary",
            model=args.primary_model,
            thinking="disabled",
            minimum_searches=args.primary_minimum_searches,
        ),
        Stage(
            name="retry",
            model=args.primary_model,
            thinking="disabled",
            minimum_searches=args.retry_minimum_searches,
        ),
        Stage(
            name="escalation",
            model=args.escalation_model,
            reasoning_effort="low",
            minimum_searches=args.escalation_minimum_searches,
        ),
    ]
    tier_count = {"primary": 1, "retry": 2, "escalation": 3}[args.max_tier]
    stages = stages[:tier_count]
    pipeline_id = pipeline_identifier(
        stages,
        args.confidence_threshold,
        args.profile,
        args.prompt_profile,
    )
    records = json.loads(args.input.read_text())
    if not isinstance(records, list):
        raise SystemExit("Infrastructure input must be a JSON array")
    facet_overrides = None
    if args.repair_queue is not None:
        repair_queue = json.loads(args.repair_queue.read_text(encoding="utf-8"))
        facilities = repair_queue.get("facilities") if isinstance(repair_queue, dict) else None
        if not isinstance(facilities, list):
            raise SystemExit("Repair queue must contain a facilities array")
        facet_overrides = {}
        for item in facilities:
            if not isinstance(item, dict) or not isinstance(item.get("facility_id"), str):
                raise SystemExit("Every repair queue item must have a facility_id")
            unknown = set(item.get("facets") or []) - set(RESEARCHABLE_FIELDS)
            if unknown:
                raise SystemExit(
                    f"Repair queue {item['facility_id']} has unsupported facets: "
                    + ", ".join(sorted(unknown))
                )
            facet_overrides[item["facility_id"]] = item
    targets = find_targets(
        records,
        set(args.record_type),
        set(args.id),
        states=set(args.state),
        facet_overrides=facet_overrides,
    )
    allowed_facets = set(RESEARCH_PROFILES[args.profile])
    allowed_countries = set(args.country)
    allowed_priorities = set(args.priority)
    filtered_targets: list[Target] = []
    for target in targets:
        facets = tuple(facet for facet in target.facets if facet in allowed_facets)
        if not facets:
            continue
        if allowed_countries and str(target.record.get("country_code") or "").upper() not in allowed_countries:
            continue
        if allowed_priorities and target.record.get("research_priority") not in allowed_priorities:
            continue
        context = target_context(target.record, facets)
        filtered_targets.append(
            Target(
                record=target.record,
                facets=facets,
                fingerprint=hashlib.sha256(canonical_json(context).encode()).hexdigest(),
                repair_context=target.repair_context,
            )
        )
    targets = filtered_targets
    completed = (
        set()
        if args.force or args.repair_queue is not None
        else load_completed(args.checkpoint, pipeline_id)
    )
    pending = [target for target in targets if (target.record["id"], target.fingerprint) not in completed]
    if args.limit is not None:
        pending = pending[: args.limit]

    facet_counts = {field: sum(field in target.facets for target in pending) for field in RESEARCHABLE_FIELDS}
    print(f"Found {len(targets)} facilities with unresolved facets; {len(pending)} pending")
    print("Pending facets: " + ", ".join(f"{key}={value}" for key, value in facet_counts.items() if value))
    print(f"Minimum first-pass web searches: {len(pending) * stages[0].minimum_searches}")
    print(
        "Pipeline: "
        + " -> ".join(
            f"{stage.name}={stage.model}"
            + (f" (thinking {stage.thinking})" if stage.thinking else " (reasoning low)")
            for stage in stages
        )
    )
    if args.dry_run or not pending:
        for target in pending[:20]:
            print(f"- {target.record['id']}: {', '.join(target.facets)}")
        if len(pending) > 20:
            print(f"- ... and {len(pending) - 20} more")
        return 0

    api_key = os.getenv("MOONSHOT_API_KEY")
    credential_source = "environment"
    if not api_key:
        api_key = load_env_value(args.env_file, "MOONSHOT_API_KEY")
        credential_source = str(args.env_file)
    if not api_key:
        raise SystemExit(
            f"Set MOONSHOT_API_KEY in the environment or in {args.env_file}; "
            "alternatively use --dry-run"
        )
    if credential_source != "environment":
        mode = args.env_file.stat().st_mode & 0o777
        if mode & 0o077:
            print(
                f"Warning: {args.env_file} permissions are {mode:03o}; use chmod 600 {args.env_file}",
                file=sys.stderr,
            )
        print(f"Loaded MOONSHOT_API_KEY from {args.env_file}")
    args.checkpoint.parent.mkdir(parents=True, exist_ok=True)
    args.events.parent.mkdir(parents=True, exist_ok=True)
    run_started_at = datetime.now(timezone.utc).isoformat()
    run_started = time.monotonic()
    run_start_event = {
        "event": "run_start",
        "timestamp": run_started_at,
        "run_id": run_id,
        "pipeline_id": pipeline_id,
        "input": str(args.input),
        "checkpoint": str(args.checkpoint),
        "repair_queue": str(args.repair_queue) if args.repair_queue else None,
        "target_count": len(pending),
        "workers": args.workers,
        "max_workers": args.max_workers,
        "control_api": (
            f"http://{args.control_host}:{args.control_port}"
            if args.control_port
            else None
        ),
        "credential_source": credential_source,
        "confidence_threshold": args.confidence_threshold,
        "prompt_profile": args.prompt_profile,
        "stages": [stage.__dict__ for stage in stages],
        "pricing_snapshot": PRICING_SNAPSHOT,
    }
    with args.events.open("a", encoding="utf-8") as events:
        write_event(events, run_start_event)
    try:
        registry = load_known_sources(args.sources)
        client = KimiClient(
            api_key=api_key,
            base_url=args.base_url,
            formula_uri=args.formula_uri,
            timeout=args.timeout,
            retries=args.retries,
            max_tool_rounds=args.max_tool_rounds,
            max_searches=args.max_searches,
            prompt_profile=args.prompt_profile,
        )
    except Exception as exc:
        with args.events.open("a", encoding="utf-8") as events:
            write_event(
                events,
                {
                    "event": "run_initialization_error",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "run_id": run_id,
                    "pipeline_id": pipeline_id,
                    "error": str(exc),
                },
            )
        raise
    status_counts = {"ok": 0, "review": 0, "error": 0}
    aggregate_metrics = {
        "request_count": 0,
        "http_retry_count": 0,
        "search_count": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "cached_prompt_tokens": 0,
        "reasoning_tokens": 0,
        "estimated_cost_usd": 0.0,
    }
    control = ControlState(
        run_id,
        pipeline_id,
        len(pending),
        args.workers,
        args.verbose,
        max_workers=args.max_workers,
        event_path=args.events,
    )
    control_server: http.server.ThreadingHTTPServer | None = None
    if args.control_port:
        control_server, _control_thread = start_control_server(
            args.control_host, args.control_port, control
        )
        print(f"Control API: http://{args.control_host}:{args.control_port}")
    try:
        with (
            args.checkpoint.open("a", encoding="utf-8") as checkpoint,
            args.events.open("a", encoding="utf-8") as events,
        ):
            with concurrent.futures.ThreadPoolExecutor(max_workers=args.max_workers) as executor:
                future_targets: dict[concurrent.futures.Future[dict[str, Any]], Target] = {}
                next_target = 0
                index = 0
                while future_targets or (
                    next_target < len(pending) and not control.stop_requested
                ):
                    snapshot = control.snapshot()
                    while (
                        not snapshot["state"] == "paused"
                        and not control.stop_requested
                        and len(future_targets) < snapshot["workers"]
                        and next_target < len(pending)
                    ):
                        target = pending[next_target]
                        next_target += 1
                        control.mark_submitted(target.record["id"])
                        future = executor.submit(
                            research_one,
                            client,
                            target,
                            registry,
                            stages,
                            args.confidence_threshold,
                            run_id,
                            pipeline_id,
                            control,
                        )
                        future_targets[future] = target
                        snapshot = control.snapshot()

                    if not future_targets:
                        time.sleep(min(0.25, args.heartbeat_seconds))
                        continue
                    done, _ = concurrent.futures.wait(
                        future_targets,
                        timeout=args.heartbeat_seconds,
                        return_when=concurrent.futures.FIRST_COMPLETED,
                    )
                    if not done:
                        elapsed = time.monotonic() - run_started
                        print(
                            f"heartbeat processed={index}/{len(pending)} "
                            f"in_flight={len(future_targets)} "
                            f"elapsed={elapsed / 60:.1f}m searches={aggregate_metrics['search_count']} "
                            f"estimated_cost=${aggregate_metrics['estimated_cost_usd']:.2f}",
                            flush=True,
                        )
                        continue
                    for future in done:
                        future_targets.pop(future)
                        index += 1
                        entry = future.result()
                        checkpoint.write(json.dumps(entry, ensure_ascii=False) + "\n")
                        checkpoint.flush()
                        write_event(events, compact_facility_event(entry))
                        status_counts[entry["status"]] += 1
                        for key in aggregate_metrics:
                            value = entry["metrics"].get(key)
                            if isinstance(value, (int, float)):
                                aggregate_metrics[key] += value
                        control.mark_completed(entry)
                        if control.verbose:
                            print(
                                f"[{index}/{len(pending)}] {entry['status']}: {entry['facility_id']} "
                                f"stage={entry.get('final_stage', 'none')} "
                                f"searches={entry['metrics']['search_count']} "
                                f"cost=${entry['metrics'].get('estimated_cost_usd') or 0:.4f}",
                                flush=True,
                            )
                        if index % args.progress_every == 0 or index == len(pending):
                            elapsed = max(0.001, time.monotonic() - run_started)
                            rate = index / elapsed
                            eta_seconds = (len(pending) - index) / rate if rate else 0
                            print(
                                f"progress={index}/{len(pending)} rate={rate:.2f}/s "
                                f"eta={eta_seconds / 60:.1f}m accepted={status_counts['ok']} "
                                f"review={status_counts['review']} failed={status_counts['error']} "
                                f"searches={aggregate_metrics['search_count']} "
                                f"retries={aggregate_metrics['http_retry_count']} "
                                f"estimated_cost=${aggregate_metrics['estimated_cost_usd']:.2f}",
                                flush=True,
                            )
        run_finished_at = datetime.now(timezone.utc).isoformat()
        with args.events.open("a", encoding="utf-8") as events:
            write_event(
                events,
                {
                    "event": "run_complete",
                    "timestamp": run_finished_at,
                    "run_id": run_id,
                    "pipeline_id": pipeline_id,
                    "started_at": run_started_at,
                    "elapsed_seconds": round(time.monotonic() - run_started, 3),
                    "processed": index,
                    "unprocessed": len(pending) - index,
                    "stop_requested": control.stop_requested,
                    "status_counts": status_counts,
                    "metrics": {
                        **aggregate_metrics,
                        "estimated_cost_usd": round(aggregate_metrics["estimated_cost_usd"], 6),
                    },
                },
            )
    finally:
        if control_server is not None:
            control_server.shutdown()
            control_server.server_close()
    print(
        f"Checkpoint: {args.checkpoint} "
        f"({status_counts['ok']} accepted, {status_counts['review']} need review, "
        f"{status_counts['error']} failed)"
    )
    return 1 if status_counts["error"] else 0


if __name__ == "__main__":
    sys.exit(main())
