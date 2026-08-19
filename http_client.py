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
    "0",
    "false",
    "no",
}

_host_registry_lock = threading.Lock()
_host_locks: dict[str, threading.Lock] = {}
_last_request_by_host: dict[str, float] = {}
_host_policy_cache: dict[str, object] | None = None
_robots_lock = threading.Lock()
_robots_cache: dict[str, tuple[float, urllib.robotparser.RobotFileParser | None]] = {}
_cache_lock = threading.Lock()


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
    _host_policy_cache = {
        "defaults": {"min_interval_seconds": DEFAULT_MIN_INTERVAL_SECONDS},
        "hosts": {},
    }
    return _host_policy_cache


def _match_host_policy(host: str) -> dict[str, object]:
    policy = _load_host_policy()
    defaults = policy.get("defaults") if isinstance(policy, dict) else {}
    hosts = policy.get("hosts") if isinstance(policy, dict) else {}
    if not isinstance(defaults, dict):
        defaults = {}
    if not isinstance(hosts, dict):
        hosts = {}

    matched = dict(defaults)
    if host in hosts and isinstance(hosts[host], dict):
        matched.update(hosts[host])
    else:
        for suffix, values in hosts.items():
            if not isinstance(values, dict):
                continue
            suffix = str(suffix).lstrip(".")
            if host == suffix or host.endswith(f".{suffix}"):
                matched.update(values)
                break
    return matched


def _lock_for_host(host: str) -> threading.Lock:
    with _host_registry_lock:
        return _host_locks.setdefault(host, threading.Lock())


def _pace_host(url: str, min_interval_seconds: float = DEFAULT_MIN_INTERVAL_SECONDS) -> None:
    """Serialize only requests to the same host, not requests to different hosts."""
    host = (urlsplit(url).hostname or "").lower()
    if not host:
        return

    with _lock_for_host(host):
        now = time.monotonic()
        last = _last_request_by_host.get(host)
        if last is not None:
            wait = min_interval_seconds - (now - last)
            if wait > 0:
                time.sleep(wait)
        _last_request_by_host[host] = time.monotonic()


def _cache_paths(url: str) -> tuple[Path, Path]:
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
    return HTTP_CACHE_DIR / f"{digest}.json", HTTP_CACHE_DIR / f"{digest}.body"


def _load_conditional_cache(url: str) -> tuple[dict[str, object], bytes] | None:
    if not HTTP_CACHE_ENABLED:
        return None
    metadata_path, body_path = _cache_paths(url)
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        body = body_path.read_bytes()
        if not isinstance(metadata, dict):
            return None
        return metadata, body
    except (OSError, ValueError, TypeError):
        return None


def _save_conditional_cache(url: str, response: requests.Response) -> None:
    if not HTTP_CACHE_ENABLED or response.status_code != 200:
        return
    if not (response.headers.get("ETag") or response.headers.get("Last-Modified")):
        return

    body = response.content
    if len(body) > DEFAULT_HTTP_CACHE_MAX_BYTES:
        return

    metadata = {
        "url": url,
        "etag": response.headers.get("ETag"),
        "last_modified": response.headers.get("Last-Modified"),
        "content_type": response.headers.get("Content-Type"),
        "encoding": response.encoding,
        "saved_at": time.time(),
    }
    metadata_path, body_path = _cache_paths(url)
    try:
        with _cache_lock:
            HTTP_CACHE_DIR.mkdir(parents=True, exist_ok=True)
            metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
            body_path.write_bytes(body)
    except OSError:
        pass


def _hydrate_not_modified_response(
    response: requests.Response,
    cached_metadata: dict[str, object],
    cached_body: bytes,
) -> requests.Response:
    response.status_code = 200
    response.reason = "OK (cached after 304)"
    response._content = cached_body
    response._content_consumed = True
    content_type = cached_metadata.get("content_type")
    if content_type and not response.headers.get("Content-Type"):
        response.headers["Content-Type"] = str(content_type)
    encoding = cached_metadata.get("encoding")
    if encoding:
        response.encoding = str(encoding)
    response.headers["X-CodeCollective-Cache"] = "revalidated"
    return response


def _load_robots_parser(
    session: requests.Session,
    scheme: str,
    host: str,
    *,
    timeout: int,
    ttl_seconds: int,
) -> urllib.robotparser.RobotFileParser | None:
    now = time.time()
    with _robots_lock:
        cached = _robots_cache.get(host)
        if cached and (now - cached[0] < ttl_seconds):
            return cached[1]

    robots_url = f"{scheme}://{host}/robots.txt"
    parser = urllib.robotparser.RobotFileParser()
    parser.set_url(robots_url)
    try:
        policy = _match_host_policy(host)
        interval = float(policy.get("min_interval_seconds", DEFAULT_MIN_INTERVAL_SECONDS))
        _pace_host(robots_url, min_interval_seconds=interval)
        resp = session.get(robots_url, timeout=timeout)
        if resp.status_code >= 400:
            with _robots_lock:
                _robots_cache[host] = (now, None)
            return None
        parser.parse((resp.text or "").splitlines())
        with _robots_lock:
            _robots_cache[host] = (now, parser)
        return parser
    except Exception:
        with _robots_lock:
            _robots_cache[host] = (now, None)
        return None


def _enforce_robots(
    session: requests.Session,
    url: str,
    *,
    timeout: int,
    user_agent: str,
    robots_ttl_seconds: int = DEFAULT_ROBOTS_TTL_SECONDS,
) -> None:
    parsed = urlsplit(url)
    scheme = parsed.scheme or "https"
    host = (parsed.hostname or "").lower()
    if not host:
        return
    policy = _match_host_policy(host)
    robots_enabled = bool(policy.get("robots_preflight", True))
    if not robots_enabled:
        return

    parser = _load_robots_parser(
        session=session,
        scheme=scheme,
        host=host,
        timeout=min(timeout, 10),
        ttl_seconds=robots_ttl_seconds,
    )
    if parser is None:
        return
    if not parser.can_fetch(user_agent, url):
        raise PermissionError(f"Blocked by robots.txt policy: {url}")


def build_session(
    user_agent: str = DEFAULT_USER_AGENT,
    retries: int = 3,
    backoff_factor: float = 1.0,
) -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": user_agent,
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Connection": "keep-alive",
        }
    )
    retry = Retry(
        total=retries,
        backoff_factor=backoff_factor,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "HEAD"],
        respect_retry_after_header=True,
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=16, pool_maxsize=16)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def polite_get(
    session: requests.Session,
    url: str,
    *,
    timeout: int = DEFAULT_TIMEOUT,
    min_interval_seconds: float = DEFAULT_MIN_INTERVAL_SECONDS,
    respect_robots: bool = True,
    use_conditional_cache: bool = True,
    **kwargs,
) -> requests.Response:
    host = (urlsplit(url).hostname or "").lower()
    policy = _match_host_policy(host) if host else {}
    effective_interval = float(policy.get("min_interval_seconds", min_interval_seconds))
    if policy.get("disabled", False):
        raise PermissionError(f"Host disabled by scrape policy: {host}")

    if respect_robots:
        _enforce_robots(
            session,
            url,
            timeout=timeout,
            user_agent=str(session.headers.get("User-Agent") or DEFAULT_USER_AGENT),
        )

    request_kwargs = dict(kwargs)
    cached = None
    cache_eligible = (
        use_conditional_cache
        and HTTP_CACHE_ENABLED
        and not request_kwargs.get("stream", False)
        and not request_kwargs.get("params")
    )
    if cache_eligible:
        cached = _load_conditional_cache(url)
        if cached:
            metadata, _ = cached
            headers = dict(request_kwargs.get("headers") or {})
            if metadata.get("etag"):
                headers.setdefault("If-None-Match", str(metadata["etag"]))
            if metadata.get("last_modified"):
                headers.setdefault("If-Modified-Since", str(metadata["last_modified"]))
            if headers:
                request_kwargs["headers"] = headers

    _pace_host(url, min_interval_seconds=effective_interval)
    response = session.get(url, timeout=timeout, **request_kwargs)

    if response.status_code == 304 and cached:
        metadata, body = cached
        return _hydrate_not_modified_response(response, metadata, body)

    if cache_eligible:
        _save_conditional_cache(url, response)
    return response
