#!/usr/bin/env python3
"""Serve a local real-time dashboard for the Kimi inventory research API."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


DEFAULT_UPSTREAM = "http://127.0.0.1:8765"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8766
DEFAULT_CHECKPOINT = Path(__file__).with_name("research") / "kimi-research.jsonl"
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV_FILE = Path(__file__).resolve().parent.parent / ".env.kimi"
PILOT_COST_PER_RECORD = 0.320834 / 10
PILOT_SEARCHES_PER_RECORD = 36 / 10
PILOT_WEIGHT = 10
QUALITY_WEIGHTS = {
    "high": 1.0,
    "medium": 0.72,
    "low": 0.38,
    "insufficient": 0.0,
    "unknown": 0.0,
}
QUALITY_ORDER = ("high", "medium", "low", "insufficient", "unknown")
WORKFLOW_RECORD_TYPES = {"data_center", "power_plant"}
WORKFLOW_TIERS = {"primary", "retry", "escalation"}


class WorkflowRunner:
    def __init__(self, root: Path, env_file: Path, upstream: str):
        self.root = root
        self.env_file = env_file
        self.upstream = upstream
        self.lock = threading.Lock()
        self.thread: threading.Thread | None = None
        self.process: subprocess.Popen[str] | None = None
        self.stop_requested = False
        self.status: dict[str, Any] = self._idle_status()

    @staticmethod
    def _idle_status() -> dict[str, Any]:
        return {
            "state": "idle",
            "phase": "idle",
            "started_at": None,
            "finished_at": None,
            "returncode": None,
            "error": None,
            "commands": [],
            "log": [],
            "options": {},
        }

    def current(self) -> dict[str, Any]:
        with self.lock:
            return json.loads(json.dumps(self.status))

    def start(self, options: dict[str, Any]) -> dict[str, Any]:
        normalized = self._normalize_options(options)
        with self.lock:
            if self.thread and self.thread.is_alive():
                raise ValueError("workflow is already running")
            self.stop_requested = False
            self.status = {
                "state": "running",
                "phase": "starting",
                "started_at": time.time(),
                "finished_at": None,
                "returncode": None,
                "error": None,
                "commands": [],
                "log": [],
                "options": normalized,
            }
            self.thread = threading.Thread(
                target=self._run_workflow,
                args=(normalized,),
                name="kimi-workflow",
                daemon=True,
            )
            self.thread.start()
            return self.current()

    def stop(self) -> dict[str, Any]:
        with self.lock:
            self.stop_requested = True
            process = self.process
            self._append_log_locked("Stop requested; terminating active command after current cleanup.")
        if process and process.poll() is None:
            process.terminate()
        return self.current()

    def _normalize_options(self, options: dict[str, Any]) -> dict[str, Any]:
        record_type = str(options.get("record_type") or "data_center")
        if record_type not in WORKFLOW_RECORD_TYPES:
            raise ValueError("record_type must be data_center or power_plant")
        max_tier = str(options.get("max_tier") or "escalation")
        if max_tier not in WORKFLOW_TIERS:
            raise ValueError("max_tier must be primary, retry, or escalation")
        workers = bounded_int(options.get("workers", 4), 1, 16, "workers")
        max_searches = bounded_int(options.get("max_searches", 5), 1, 20, "max_searches")
        audit_workers = bounded_int(options.get("audit_workers", 8), 1, 32, "audit_workers")
        judge_workers = bounded_int(options.get("judge_workers", 4), 1, 16, "judge_workers")
        return {
            "record_type": record_type,
            "workers": workers,
            "max_searches": max_searches,
            "max_tier": max_tier,
            "audit_workers": audit_workers,
            "judge_workers": judge_workers,
            "run_research": bounded_bool(options.get("run_research", True), "run_research"),
            "run_audit": bounded_bool(options.get("run_audit", True), "run_audit"),
            "run_promote": bounded_bool(options.get("run_promote", True), "run_promote"),
            "apply_promotion": bounded_bool(options.get("apply_promotion", False), "apply_promotion"),
            "reuse_source_audit": bounded_bool(
                options.get("reuse_source_audit", True),
                "reuse_source_audit",
            ),
        }

    def _run_workflow(self, options: dict[str, Any]) -> None:
        try:
            commands = self._commands(options)
            for phase, command in commands:
                self._set_phase(phase)
                self._run_command(command)
                if self.stop_requested:
                    raise RuntimeError("workflow stopped")
            self._finish("succeeded", None, 0)
        except Exception as exc:
            returncode = self.process.returncode if self.process else 1
            self._finish("failed", str(exc), returncode if returncode is not None else 1)
        finally:
            with self.lock:
                self.process = None

    def _commands(self, options: dict[str, Any]) -> list[tuple[str, list[str]]]:
        host, port = upstream_host_port(self.upstream)
        commands: list[tuple[str, list[str]]] = []
        if options["run_research"]:
            commands.append(
                (
                    "research",
                    [
                        sys.executable,
                        "datacenters/research_inventory_with_kimi.py",
                        "--record-type",
                        options["record_type"],
                        "--env-file",
                        str(self.env_file),
                        "--workers",
                        str(options["workers"]),
                        "--max-searches",
                        str(options["max_searches"]),
                        "--max-tier",
                        options["max_tier"],
                        "--control-host",
                        host,
                        "--control-port",
                        str(port),
                        "--verbose",
                    ],
                )
            )
        audit_path = self.root / "datacenters" / "research" / "kimi-evidence-audit.jsonl"
        if options["run_audit"]:
            audit_command = [
                sys.executable,
                "datacenters/audit_kimi_research.py",
                "--judge",
                "--workers",
                str(options["audit_workers"]),
                "--judge-workers",
                str(options["judge_workers"]),
                "--env-file",
                str(self.env_file),
            ]
            if options["reuse_source_audit"] and audit_path.exists():
                audit_command.extend(["--reuse-source-audit", str(audit_path)])
            commands.append(("audit", audit_command))
        if options["run_promote"]:
            promote_command = [sys.executable, "datacenters/promote_kimi_research.py"]
            if options["apply_promotion"]:
                promote_command.append("--apply")
            commands.append(("promote", promote_command))
        if not commands:
            raise ValueError("at least one workflow stage must be enabled")
        return commands

    def _run_command(self, command: list[str]) -> None:
        self._append_command(command)
        process = subprocess.Popen(
            command,
            cwd=self.root,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        with self.lock:
            self.process = process
        assert process.stdout
        for line in process.stdout:
            self._append_log(line.rstrip())
        returncode = process.wait()
        with self.lock:
            self.process = None
        if returncode != 0:
            raise RuntimeError(f"command failed with exit code {returncode}: {command[1]}")
        if self.stop_requested:
            raise RuntimeError("workflow stopped")

    def _append_command(self, command: list[str]) -> None:
        with self.lock:
            self.status["commands"].append(command)
            self._append_log_locked("$ " + " ".join(command))

    def _append_log(self, message: str) -> None:
        with self.lock:
            self._append_log_locked(message)

    def _append_log_locked(self, message: str) -> None:
        self.status["log"].append({"timestamp": time.time(), "message": message})
        self.status["log"] = self.status["log"][-250:]

    def _set_phase(self, phase: str) -> None:
        with self.lock:
            self.status["phase"] = phase
            self._append_log_locked(f"Starting {phase} stage.")

    def _finish(self, state: str, error: str | None, returncode: int) -> None:
        with self.lock:
            self.status["state"] = state
            self.status["phase"] = "complete" if state == "succeeded" else "failed"
            self.status["finished_at"] = time.time()
            self.status["error"] = error
            self.status["returncode"] = returncode
            self._append_log_locked(
                "Workflow completed successfully."
                if state == "succeeded"
                else f"Workflow failed: {error}"
            )


class ResearchRecords:
    def __init__(self, path: Path):
        self.path = path
        self.rows: list[dict[str, Any]] = []
        self.signature: tuple[int, int] | None = None
        self.lock = threading.Lock()

    def refresh(self) -> None:
        try:
            stat = self.path.stat()
        except FileNotFoundError:
            return
        signature = (stat.st_mtime_ns, stat.st_size)
        with self.lock:
            if signature == self.signature:
                return
            rows = []
            for line in self.path.read_text(encoding="utf-8").splitlines():
                try:
                    value = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(value, dict):
                    rows.append(value)
            self.rows = rows
            self.signature = signature

    def current(self, run_id: str | None) -> list[dict[str, Any]]:
        self.refresh()
        with self.lock:
            return [row for row in self.rows if not run_id or row.get("run_id") == run_id]

    def latest_run_id(self) -> str | None:
        self.refresh()
        with self.lock:
            return next(
                (row.get("run_id") for row in reversed(self.rows) if row.get("run_id")),
                None,
            )

    @staticmethod
    def summarize(row: dict[str, Any]) -> dict[str, Any]:
        facets = (row.get("final_result") or {}).get("facets") or {}
        confidences = {
            name: value.get("confidence", "unknown")
            for name, value in facets.items()
            if isinstance(value, dict)
        }
        source_count = sum(
            len(value.get("sources") or [])
            for value in facets.values()
            if isinstance(value, dict)
        )
        quality = summarize_quality(confidences.values())
        return {
            "run_id": row.get("run_id"),
            "pipeline_id": row.get("pipeline_id"),
            "facility_id": row.get("facility_id"),
            "facility_name": row.get("facility_name"),
            "record_type": row.get("record_type"),
            "status": row.get("status"),
            "final_stage": row.get("final_stage"),
            "requested_facets": row.get("requested_facets") or [],
            "confidences": confidences,
            "quality_counts": quality["counts"],
            "quality_score": quality["score"],
            "quality_label": quality["label"],
            "source_count": source_count,
            "search_count": row.get("metrics", {}).get("search_count", 0),
            "estimated_cost_usd": row.get("metrics", {}).get("estimated_cost_usd", 0),
            "finished_at": row.get("finished_at"),
            "error": row.get("error"),
        }

    def summaries(self, run_id: str | None) -> list[dict[str, Any]]:
        rows = self.current(run_id)
        return [self.summarize(row) for row in reversed(rows)]

    def detail(self, run_id: str | None, facility_id: str) -> dict[str, Any] | None:
        return next(
            (
                row
                for row in reversed(self.current(run_id))
                if row.get("facility_id") == facility_id
            ),
            None,
        )

    def detail_for_run(self, run_id: str, facility_id: str) -> dict[str, Any] | None:
        return next(
            (
                row
                for row in reversed(self.current(None))
                if row.get("run_id") == run_id and row.get("facility_id") == facility_id
            ),
            None,
        )

    def aggregate(self, run_id: str | None) -> dict[str, Any]:
        rows = self.current(run_id)
        counts: dict[str, dict[str, int]] = {
            "record_types": {},
            "statuses": {},
            "confidences": {},
            "facets": {},
            "source_types": {},
        }
        total_sources = 0
        for row in rows:
            increment(counts["record_types"], str(row.get("record_type", "unknown")))
            increment(counts["statuses"], str(row.get("status", "unknown")))
            facets = (row.get("final_result") or {}).get("facets") or {}
            for name, facet in facets.items():
                increment(counts["facets"], name)
                if not isinstance(facet, dict):
                    continue
                increment(counts["confidences"], str(facet.get("confidence", "unknown")))
                for source in facet.get("sources") or []:
                    if isinstance(source, dict):
                        total_sources += 1
                        increment(
                            counts["source_types"],
                            str(source.get("source_type", "unknown")),
                        )
        return {"records": len(rows), "sources": total_sources, **counts}


def increment(values: dict[str, int], key: str) -> None:
    values[key] = values.get(key, 0) + 1


def bounded_int(value: Any, minimum: int, maximum: int, name: str) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if not minimum <= result <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return result


def bounded_bool(value: Any, name: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "on"}:
            return True
        if lowered in {"false", "0", "no", "off"}:
            return False
    raise ValueError(f"{name} must be a boolean")


def upstream_host_port(upstream: str) -> tuple[str, int]:
    parsed = urllib.parse.urlparse(upstream)
    host = parsed.hostname or "127.0.0.1"
    if host == "localhost":
        host = "127.0.0.1"
    if host not in {"127.0.0.1", "::1"}:
        raise ValueError("workflow control upstream must be loopback")
    return host, parsed.port or 8765


def env_value(path: Path, key: str) -> str | None:
    if not path.exists():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        name, value = stripped.split("=", 1)
        if name.strip() != key:
            continue
        return value.strip().strip("'\"")
    return None


def write_env_value(path: Path, key: str, value: str) -> None:
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    updated = False
    output = []
    for line in lines:
        if line.strip().startswith(f"{key}="):
            output.append(f"{key}={value}")
            updated = True
        else:
            output.append(line)
    if not updated:
        output.append(f"{key}={value}")
    path.write_text("\n".join(output).rstrip() + "\n", encoding="utf-8")
    os.chmod(path, 0o600)


def summarize_quality(values: Any) -> dict[str, Any]:
    counts = dict.fromkeys(QUALITY_ORDER, 0)
    total = 0
    weighted = 0.0
    for value in values:
        key = str(value or "unknown").lower()
        if key not in counts:
            key = "unknown"
        counts[key] += 1
        total += 1
        weighted += QUALITY_WEIGHTS[key]
    if not total:
        return {"counts": counts, "score": 0, "label": "unknown"}
    score = round(weighted / total * 100)
    if score >= 85:
        label = "high"
    elif score >= 58:
        label = "medium"
    elif score >= 25:
        label = "low"
    else:
        label = "insufficient"
    return {"counts": counts, "score": score, "label": label}


class DashboardState:
    def __init__(
        self,
        upstream: str,
        interval: float,
        checkpoint: Path = DEFAULT_CHECKPOINT,
        max_samples: int = 7200,
    ):
        self.upstream = upstream.rstrip("/")
        self.interval = interval
        self.samples: deque[dict[str, Any]] = deque(maxlen=max_samples)
        self.activity: deque[dict[str, Any]] = deque(maxlen=250)
        self.last_status: dict[str, Any] | None = None
        self.last_error: str | None = None
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.records = ResearchRecords(checkpoint)
        self.env_file = DEFAULT_ENV_FILE
        self.workflow = WorkflowRunner(ROOT, self.env_file, self.upstream)

    def request(self, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(
            self.upstream + path,
            data=data,
            headers={"Content-Type": "application/json"} if data is not None else {},
            method="POST" if data is not None else "GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=3) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            try:
                detail = json.load(exc).get("error", str(exc))
            except (ValueError, AttributeError):
                detail = str(exc)
            raise ValueError(detail) from exc

    def add_activity(self, message: str, level: str = "info") -> None:
        self.activity.appendleft(
            {"timestamp": time.time(), "level": level, "message": message}
        )

    def record(self, status: dict[str, Any], sampled_at: float | None = None) -> None:
        sampled_at = sampled_at or time.time()
        sample = {
            "timestamp": sampled_at,
            "elapsed_seconds": status.get("elapsed_seconds", 0),
            "processed": status.get("processed", 0),
            "submitted": status.get("submitted", 0),
            "queued": status.get("queued", 0),
            "search_count": status.get("metrics", {}).get("search_count", 0),
            "estimated_cost_usd": status.get("metrics", {}).get("estimated_cost_usd", 0),
            "state": status.get("state", "unknown"),
        }
        with self.lock:
            previous = self.last_status
            if previous is None:
                self.add_activity(
                    f"Connected to run {status.get('run_id', 'unknown')[:8]} with "
                    f"{status.get('total', 0)} facilities"
                )
            else:
                self._record_transitions(previous, status)
            self.samples.append(sample)
            self.last_status = status
            self.last_error = None

    def _record_transitions(
        self, previous: dict[str, Any], current: dict[str, Any]
    ) -> None:
        if current.get("state") != previous.get("state"):
            self.add_activity(f"Run state changed to {current.get('state')}", "control")
        if current.get("workers") != previous.get("workers"):
            self.add_activity(f"Worker limit changed to {current.get('workers')}", "control")
        completed = current.get("processed", 0) - previous.get("processed", 0)
        if completed > 0:
            counts = current.get("status_counts", {})
            self.add_activity(
                f"Completed {completed} facilit{'y' if completed == 1 else 'ies'}; "
                f"accepted {counts.get('ok', 0)}, review {counts.get('review', 0)}, "
                f"failed {counts.get('error', 0)}"
            )
        old_flight = previous.get("in_flight", {})
        for facility, stage in current.get("in_flight", {}).items():
            if old_flight.get(facility) != stage:
                self.add_activity(f"{facility} entered {stage}", "stage")

    def poll(self) -> None:
        while not self.stop_event.is_set():
            try:
                self.record(self.request("/status"))
            except (OSError, ValueError) as exc:
                with self.lock:
                    message = str(exc)
                    if message != self.last_error:
                        self.add_activity(f"Control API unavailable: {message}", "error")
                    self.last_error = message
            self.stop_event.wait(self.interval)

    def metrics(self, records_scope: str = "current") -> dict[str, Any]:
        with self.lock:
            status = dict(self.last_status or {})
            samples = list(self.samples)
            activity = list(self.activity)
            error = self.last_error
        processed = status.get("processed", 0)
        total = status.get("total", 0)
        cost = status.get("metrics", {}).get("estimated_cost_usd", 0.0)
        searches = status.get("metrics", {}).get("search_count", 0)
        blended_cost = (cost + PILOT_COST_PER_RECORD * PILOT_WEIGHT) / (
            processed + PILOT_WEIGHT
        )
        blended_searches = (searches + PILOT_SEARCHES_PER_RECORD * PILOT_WEIGHT) / (
            processed + PILOT_WEIGHT
        )
        rate = rolling_rate(samples, "processed", 300)
        if rate <= 0 and processed:
            elapsed = max(float(status.get("elapsed_seconds", 0)), 1)
            rate = processed / elapsed
        remaining = max(total - processed, 0)
        run_id = status.get("run_id") or self.records.latest_run_id()
        records_run_id = None if records_scope == "all" else run_id
        return {
            "connected": bool(status) and error is None,
            "error": error,
            "status": status,
            "forecast": {
                "cost_per_record_usd": round(blended_cost, 6),
                "projected_total_cost_usd": round(cost + remaining * blended_cost, 4),
                "projected_remaining_cost_usd": round(remaining * blended_cost, 4),
                "searches_per_record": round(blended_searches, 3),
                "projected_total_searches": round(searches + remaining * blended_searches),
                "records_per_minute": round(rate * 60, 3),
                "eta_seconds": round(remaining / rate) if rate > 0 else None,
                "basis": f"live results blended with {PILOT_WEIGHT}-record pilot",
            },
            "history": downsample(samples, 600),
            "activity": activity[:80],
            "received_run_id": records_run_id,
            "received_scope": "all" if records_scope == "all" else "current",
            "received": self.records.aggregate(records_run_id),
        }

    def current_run_id(self) -> str | None:
        with self.lock:
            run_id = (self.last_status or {}).get("run_id")
        return run_id or self.records.latest_run_id()

    def records_run_id(self, scope: str) -> str | None:
        return None if scope == "all" else self.current_run_id()

    def service_settings(self) -> dict[str, Any]:
        return {
            "kimi_key_configured": bool(env_value(self.env_file, "MOONSHOT_API_KEY")),
            "env_file": str(self.env_file),
            "github_mode": "browser-local",
        }

    def update_service_settings(self, values: dict[str, Any]) -> dict[str, Any]:
        api_key = str(values.get("moonshot_api_key") or "").strip()
        if not api_key:
            raise ValueError("moonshot_api_key is required")
        if len(api_key) < 12 or any(char.isspace() for char in api_key):
            raise ValueError("moonshot_api_key does not look valid")
        write_env_value(self.env_file, "MOONSHOT_API_KEY", api_key)
        self.workflow.env_file = self.env_file
        return self.service_settings()


def rolling_rate(
    samples: list[dict[str, Any]], field: str, window_seconds: float
) -> float:
    if len(samples) < 2:
        return 0.0
    latest = samples[-1]
    cutoff = latest["timestamp"] - window_seconds
    oldest = next((sample for sample in samples if sample["timestamp"] >= cutoff), samples[0])
    elapsed = latest["timestamp"] - oldest["timestamp"]
    return (latest[field] - oldest[field]) / elapsed if elapsed > 0 else 0.0


def downsample(samples: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    if len(samples) <= limit:
        return samples
    step = len(samples) / limit
    return [samples[int(index * step)] for index in range(limit - 1)] + [samples[-1]]


def make_handler(state: DashboardState, html: bytes) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def send_value(self, status: int, value: Any, content_type: str) -> None:
            body = value if isinstance(value, bytes) else json.dumps(value).encode()
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.end_headers()
            self.wfile.write(body)

        def do_OPTIONS(self) -> None:
            self.send_value(204, b"", "text/plain")

        def do_GET(self) -> None:
            parsed = urllib.parse.urlparse(self.path)
            query = urllib.parse.parse_qs(parsed.query)
            records_scope = query.get("scope", ["current"])[0]
            if records_scope not in {"current", "all"}:
                records_scope = "current"
            if parsed.path == "/":
                self.send_value(200, html, "text/html; charset=utf-8")
            elif parsed.path == "/api/snapshot":
                self.send_value(
                    200, state.metrics(records_scope), "application/json"
                )
            elif parsed.path == "/api/records":
                run_id = state.records_run_id(records_scope)
                self.send_value(
                    200, state.records.summaries(run_id), "application/json"
                )
            elif parsed.path == "/api/service-settings":
                self.send_value(200, state.service_settings(), "application/json")
            elif parsed.path == "/api/workflow":
                self.send_value(200, state.workflow.current(), "application/json")
            elif parsed.path == "/api/record":
                facility_id = query.get("id", [""])[0]
                exact_run_id = query.get("run_id", [""])[0]
                run_id = state.records_run_id(records_scope)
                record = (
                    state.records.detail_for_run(exact_run_id, facility_id)
                    if exact_run_id
                    else state.records.detail(run_id, facility_id)
                )
                self.send_value(
                    200 if record else 404,
                    record or {"error": "record not found"},
                    "application/json",
                )
            else:
                self.send_value(404, {"error": "not found"}, "application/json")

        def do_POST(self) -> None:
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path not in {"/api/control", "/api/service-settings", "/api/workflow"}:
                self.send_value(404, {"error": "not found"}, "application/json")
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length > 65536:
                    raise ValueError("request body is too large")
                body = json.loads(self.rfile.read(length))
                if not isinstance(body, dict):
                    raise ValueError("request body must be a JSON object")
                if parsed.path == "/api/service-settings":
                    result = state.update_service_settings(body)
                elif parsed.path == "/api/workflow":
                    action = str(body.get("action") or "start")
                    if action == "start":
                        result = state.workflow.start(body)
                    elif action == "stop":
                        result = state.workflow.stop()
                    else:
                        raise ValueError("workflow action must be start or stop")
                else:
                    result = state.request("/control", body)
                    state.record(result)
                self.send_value(200, result, "application/json")
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                self.send_value(400, {"error": str(exc)}, "application/json")

        def log_message(self, _format: str, *_args: Any) -> None:
            return

    return Handler


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream", default=DEFAULT_UPSTREAM)
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--interval", type=float, default=2.0)
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.host not in {"127.0.0.1", "localhost", "::1"}:
        raise SystemExit("--host must be a loopback address")
    if not 1 <= args.port <= 65535:
        raise SystemExit("--port must be between 1 and 65535")
    if args.interval <= 0:
        raise SystemExit("--interval must be greater than zero")
    html = Path(__file__).with_name("kimi_research_dashboard.html").read_bytes()
    state = DashboardState(args.upstream, args.interval, args.checkpoint)
    state.env_file = args.env_file
    state.workflow.env_file = args.env_file
    poller = threading.Thread(target=state.poll, name="kimi-dashboard-poller", daemon=True)
    poller.start()
    server = ThreadingHTTPServer((args.host, args.port), make_handler(state, html))
    print(f"Dashboard: http://{args.host}:{args.port}")
    print(f"Upstream:  {args.upstream}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        state.stop_event.set()
        server.server_close()
        poller.join(timeout=args.interval + 1)
    return 0



if __name__ == "__main__":
    raise SystemExit(main())
