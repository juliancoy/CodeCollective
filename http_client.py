"""Shared polite HTTP client utilities for scrapers."""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
import urllib.robotparser
from pathlib import Path
from urllib.parse import urlsplit

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (compatible; CodeCollectiveBot/1.0; "
    "+https://github.com/juliancoy/CodeCollective)"
)
DEFAULT_TIMEOUT = 30
DEFAULT_MIN_INTERVAL_SECONDS = 1.0
DEFAULT_ROBOTS_TTL_SECONDS = 3600
DEFAULT_HTTP_CACHE_MAX_BYTES = 10 * 1024 * 1024
HOST_POLICY_PATH = Path(
    os.environ.get("CODECOLLECTIVE_HOST_POLICY_PATH", "data/scrape_host_policy.json")
)
HTTP_CACHE_DIR = Path(
    os.environ.get("CODECOLLECTIVE_HTTP_CACHE_DIR", ".cache/codecollective-http")
)
HTTP_CACHE_ENABLED = os.environ.get("CODECOLLECTIVE_HTTP_CACHE", "1").lower() not in {
    "0", "false", "no",
}

_host_registry_lock = threading.Lock()
_host_locks: dict[str, threading.Lock] = {}
_last_request_by_host: dict[str, float] = {}
_host_policy_cache: dict[str, object] | None = None
_robots_lock = threading.Lock()
_robots_cache: dict[str, tuple[float, urllib.robotparser.RobotFileParser | None]] = {}
_cache_lock = threading.Lock()
_telemetry_lock = threading.Lock()
_telemetry_started_at = time.time()
_telemetry: dict[str, dict[str, float | int]] = {}


def reset_telemetry() -> None:
    global _telemetry_started_at
    with _telemetry_lock:
        _telemetry.clear()
        _telemetry_started_at = time.time()


def _host_metrics(host: str) -> dict[str, float | int]:
    return _telemetry.setdefault(host or "unknown", {
        "requests": 0,
        "robots_requests": 0,
        "failures": 0,
        "http_429": 0,
        "http_5xx": 0,
        "retries": 0,
        "cache_revalidations": 0,
        "latency_ms_total": 0.0,
        "latency_ms_max": 0.0,
    })


def _record_request(
    host: str,
    *,
    elapsed_seconds: float,
    status_code: int | None = None,
    retries: int = 0,
    cache_revalidated: bool = False,
    failed: bool = False,
    robots: bool = False,
) -> None:
    with _telemetry_lock:
        metrics = _host_metrics(host)
        metrics["requests"] = int(metrics["requests"]) + 1
        if robots:
            metrics["robots_requests"] = int(metrics["robots_requests"]) + 1
        if failed:
            metrics["failures"] = int(metrics["failures"]) + 1
        if status_code == 429:
            metrics["http_429"] = int(metrics["http_429"]) + 1
        if status_code is not None and 500 <= status_code <= 599:
            metrics["http_5xx"] = int(metrics["http_5xx"]) + 1
        metrics["retries"] = int(metrics["retries"]) + max(0, int(retries))
        if cache_revalidated:
            metrics["cache_revalidations"] = int(metrics["cache_revalidations"]) + 1
        elapsed_ms = max(0.0, elapsed_seconds * 1000.0)
        metrics["latency_ms_total"] = float(metrics["latency_ms_total"]) + elapsed_ms
        metrics["latency_ms_max"] = max(float(metrics["latency_ms_max"]), elapsed_ms)


def telemetry_snapshot() -> dict[str, object]:
    with _telemetry_lock:
        hosts = {}
        totals = {
            "requests": 0, "robots_requests": 0, "failures": 0,
            "http_429": 0, "http_5xx": 0, "retries": 0,
            "cache_revalidations": 0,
        }
        for host, raw in sorted(_telemetry.items()):
            metrics = dict(raw)
            requests_count = int(metrics["requests"])
            total_latency = float(metrics.pop("latency_ms_total"))
            metrics["latency_ms_avg"] = round(total_latency / requests_count, 1) if requests_count else 0.0
            metrics["latency_ms_max"] = round(float(metrics["latency_ms_max"]), 1)
            hosts[host] = metrics
            for key in totals:
                totals[key] += int(metrics[key])
        return {
            "started_at_epoch": _telemetry_started_at,
            "duration_seconds": round(max(0.0, time.time() - _telemetry_started_at), 2),
            "totals": totals,
            "hosts": hosts,
        }


def write_telemetry(path: str | os.PathLike[str]) -> dict[str, object]:
    snapshot = telemetry_snapshot()
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    return snapshot


def _load_host_policy() -> dict[str, object]:
    global _host_policy_cache
    if _host_policy_cache is not None:
        return _host_policy_cache
    try:
        payload = json.loads(HOST_POLICY_PATH.read_text())
        if isinstance(payload, dict):
            _host_policy_cache = payload
            return payload
    except Exception:
        pass
    _host_policy_cache = {"defaults": {"min_interval_seconds": DEFAULT_MIN_INTERVAL_SECONDS}, "hosts": {}}
    return _host_policy_cache


def _match_host_policy(host: str) -> dict[str, object]:
    policy = _load_host_policy()
    defaults = policy.get("defaults") if isinstance(policy, dict) else {}
    hosts = policy.get("hosts") if isinstance(policy, dict) else {}
    if not isinstance(defaults, dict): defaults = {}
    if not isinstance(hosts, dict): hosts = {}
    matched = dict(defaults)
    if host in hosts and isinstance(hosts[host], dict):
        matched.update(hosts[host])
    else:
        for suffix, values in hosts.items():
            if not isinstance(values, dict): continue
            suffix = str(suffix).lstrip(".")
            if host == suffix or host.endswith(f".{suffix}"):
                matched.update(values)
                break
    return matched


def _lock_for_host(host: str) -> threading.Lock:
    with _host_registry_lock:
        return _host_locks.setdefault(host, threading.Lock())


def _pace_host(url: str, min_interval_seconds: float = DEFAULT_MIN_INTERVAL_SECONDS) -> None:
    host = (urlsplit(url).hostname or "").lower()
    if not host: return
    with _lock_for_host(host):
        now = time.monotonic()
        last = _last_request_by_host.get(host)
        if last is not None:
            wait = min_interval_seconds - (now - last)
            if wait > 0: time.sleep(wait)
        _last_request_by_host[host] = time.monotonic()


def _cache_paths(url: str) -> tuple[Path, Path]:
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
    return HTTP_CACHE_DIR / f"{digest}.json", HTTP_CACHE_DIR / f"{digest}.body"


def _load_conditional_cache(url: str) -> tuple[dict[str, object], bytes] | None:
    if not HTTP_CACHE_ENABLED: return None
    metadata_path, body_path = _cache_paths(url)
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        body = body_path.read_bytes()
        return (metadata, body) if isinstance(metadata, dict) else None
    except (OSError, ValueError, TypeError):
        return None


def _save_conditional_cache(url: str, response: requests.Response) -> None:
    if not HTTP_CACHE_ENABLED or response.status_code != 200: return
    if not (response.headers.get("ETag") or response.headers.get("Last-Modified")): return
    body = response.content
    if len(body) > DEFAULT_HTTP_CACHE_MAX_BYTES: return
    metadata = {
        "url": url, "etag": response.headers.get("ETag"),
        "last_modified": response.headers.get("Last-Modified"),
        "content_type": response.headers.get("Content-Type"),
        "encoding": response.encoding, "saved_at": time.time(),
    }
    metadata_path, body_path = _cache_paths(url)
    try:
        with _cache_lock:
            HTTP_CACHE_DIR.mkdir(parents=True, exist_ok=True)
            metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
            body_path.write_bytes(body)
    except OSError:
        pass


def _hydrate_not_modified_response(response, cached_metadata, cached_body):
    response.status_code = 200
    response.reason = "OK (cached after 304)"
    response._content = cached_body
    response._content_consumed = True
    content_type = cached_metadata.get("content_type")
    if content_type and not response.headers.get("Content-Type"):
        response.headers["Content-Type"] = str(content_type)
    if cached_metadata.get("encoding"):
        response.encoding = str(cached_metadata["encoding"])
    response.headers["X-CodeCollective-Cache"] = "revalidated"
    return response


def _retry_count(response: requests.Response) -> int:
    try:
        return len(response.raw.retries.history)
    except Exception:
        return 0


def _load_robots_parser(session, scheme, host, *, timeout, ttl_seconds):
    now = time.time()
    with _robots_lock:
        cached = _robots_cache.get(host)
        if cached and (now - cached[0] < ttl_seconds): return cached[1]
    robots_url = f"{scheme}://{host}/robots.txt"
    parser = urllib.robotparser.RobotFileParser(); parser.set_url(robots_url)
    started = time.monotonic()
    try:
        policy = _match_host_policy(host)
        _pace_host(robots_url, float(policy.get("min_interval_seconds", DEFAULT_MIN_INTERVAL_SECONDS)))
        resp = session.get(robots_url, timeout=timeout)
        _record_request(host, elapsed_seconds=time.monotonic()-started, status_code=resp.status_code, retries=_retry_count(resp), robots=True)
        if resp.status_code >= 400:
            with _robots_lock: _robots_cache[host] = (now, None)
            return None
        parser.parse((resp.text or "").splitlines())
        with _robots_lock: _robots_cache[host] = (now, parser)
        return parser
    except Exception:
        _record_request(host, elapsed_seconds=time.monotonic()-started, failed=True, robots=True)
        with _robots_lock: _robots_cache[host] = (now, None)
        return None


def _enforce_robots(session, url, *, timeout, user_agent, robots_ttl_seconds=DEFAULT_ROBOTS_TTL_SECONDS):
    parsed = urlsplit(url); scheme = parsed.scheme or "https"; host = (parsed.hostname or "").lower()
    if not host: return
    policy = _match_host_policy(host)
    if not bool(policy.get("robots_preflight", True)): return
    parser = _load_robots_parser(session, scheme, host, timeout=min(timeout, 10), ttl_seconds=robots_ttl_seconds)
    if parser is not None and not parser.can_fetch(user_agent, url):
        raise PermissionError(f"Blocked by robots.txt policy: {url}")


def build_session(user_agent: str = DEFAULT_USER_AGENT, retries: int = 3, backoff_factor: float = 1.0) -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": user_agent, "Accept": "*/*", "Accept-Language": "en-US,en;q=0.9", "Connection": "keep-alive"})
    retry = Retry(total=retries, backoff_factor=backoff_factor, status_forcelist=[429,500,502,503,504], allowed_methods=["GET","HEAD"], respect_retry_after_header=True, raise_on_status=False)
    adapter = HTTPAdapter(max_retries=retry, pool_connections=16, pool_maxsize=16)
    session.mount("https://", adapter); session.mount("http://", adapter)
    return session


def polite_get(session, url, *, timeout=DEFAULT_TIMEOUT, min_interval_seconds=DEFAULT_MIN_INTERVAL_SECONDS, respect_robots=True, use_conditional_cache=True, **kwargs):
    host = (urlsplit(url).hostname or "").lower()
    policy = _match_host_policy(host) if host else {}
    effective_interval = float(policy.get("min_interval_seconds", min_interval_seconds))
    if policy.get("disabled", False): raise PermissionError(f"Host disabled by scrape policy: {host}")
    if respect_robots:
        _enforce_robots(session, url, timeout=timeout, user_agent=str(session.headers.get("User-Agent") or DEFAULT_USER_AGENT))

    request_kwargs = dict(kwargs); cached = None
    cache_eligible = use_conditional_cache and HTTP_CACHE_ENABLED and not request_kwargs.get("stream", False) and not request_kwargs.get("params")
    if cache_eligible:
        cached = _load_conditional_cache(url)
        if cached:
            metadata, _ = cached; headers = dict(request_kwargs.get("headers") or {})
            if metadata.get("etag"): headers.setdefault("If-None-Match", str(metadata["etag"]))
            if metadata.get("last_modified"): headers.setdefault("If-Modified-Since", str(metadata["last_modified"]))
            if headers: request_kwargs["headers"] = headers

    _pace_host(url, effective_interval)
    started = time.monotonic()
    try:
        response = session.get(url, timeout=timeout, **request_kwargs)
        original_status = response.status_code
        revalidated = original_status == 304 and cached is not None
        _record_request(host, elapsed_seconds=time.monotonic()-started, status_code=original_status, retries=_retry_count(response), cache_revalidated=revalidated)
        if revalidated:
            metadata, body = cached
            return _hydrate_not_modified_response(response, metadata, body)
        if cache_eligible: _save_conditional_cache(url, response)
        return response
    except Exception:
        _record_request(host, elapsed_seconds=time.monotonic()-started, failed=True)
        raise
