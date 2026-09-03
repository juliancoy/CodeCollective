#!/usr/bin/env python3
"""Evidence auditing primitives for Kimi infrastructure research."""

from __future__ import annotations

import hashlib
import io
import json
import logging
import re
import zipfile
from dataclasses import dataclass
from html import unescape
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests


NEGATIVE_PATTERNS = (
    re.compile(
        r"\bno\b.*\b(permits?|litigation|lawsuits?|appeals?|proceedings?|enforcement|"
        r"opposition|plants?|generators?|turbines?)\b",
        re.I,
    ),
    re.compile(r"\bnot (?:identified|required|applicable|found|included|researched)\b", re.I),
    re.compile(r"\bwithout (?:an? )?(?:air )?permit\b", re.I),
)
FACET_TERMS = {
    "permit_status": ("permit", "approved", "approval", "cpcn", "certificate", "license", "zoning"),
    "air_permit_status": ("air", "emission", "title v", "part 70", "permit"),
    "legal_status": ("court", "lawsuit", "litigation", "appeal", "docket", "petition", "case"),
    "public_opposition_status": ("opposition", "hearing", "comment", "protest", "testimony"),
    "on_site_natural_gas_power_plant": ("natural gas", "generator", "turbine", "engine", "power plant"),
    "power_profile": (
        "mw", "megawatt", "power", "capacity", "demand", "load", "utility",
        "substation", "critical load", "it load",
    ),
}
PRIMARY_TYPES = {"government", "court"}
MAX_SOURCE_BYTES = 15 * 1024 * 1024
USER_AGENT = "CodeCollectiveEvidenceAudit/1.0 (+local research validation)"
AUTHORITY_REGISTRY = Path(__file__).with_name("data") / "international-research-authorities.json"


def authority_registry(path: Path = AUTHORITY_REGISTRY) -> list[dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    authorities = payload.get("authorities") if isinstance(payload, dict) else None
    return authorities if isinstance(authorities, list) else []


@dataclass(frozen=True)
class FetchResult:
    url: str
    final_url: str
    status_code: int | None
    content_type: str | None
    content_sha256: str | None
    text: str
    error: str | None


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def normalize_url(url: str) -> str:
    parsed = urlparse(url.strip())
    scheme = parsed.scheme.lower()
    host = (parsed.hostname or "").lower()
    port = f":{parsed.port}" if parsed.port and parsed.port not in {80, 443} else ""
    path = re.sub(r"/{2,}", "/", parsed.path or "/")
    if path != "/":
        path = path.rstrip("/")
    query = parsed.query
    return f"{scheme}://{host}{port}{path}" + (f"?{query}" if query else "")


def source_class(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    if host.endswith("mdcourts.gov") or host.endswith("uscourts.gov"):
        return "court"
    if host.endswith(".gov") or host.endswith(".mil"):
        return "government"
    if host.endswith(".md.us") or host.endswith("maryland.gov"):
        return "government"
    for authority in authority_registry():
        suffix = str(authority.get("domain_suffix") or "").lower().lstrip(".")
        if suffix and (host == suffix or host.endswith("." + suffix)):
            return str(authority.get("authority_class") or "government")
    return "other"


def is_negative_claim(value: str) -> bool:
    return any(pattern.search(value) for pattern in NEGATIVE_PATTERNS)


def identity_terms(record: dict[str, Any]) -> list[str]:
    values = [
        record.get("name"),
        record.get("id"),
        record.get("operator"),
        record.get("owner"),
        record.get("street_address"),
    ]
    if record.get("eia_plant_code") is not None:
        values.append(str(record["eia_plant_code"]))
    terms: list[str] = []
    for value in values:
        if not isinstance(value, str) or not value.strip():
            continue
        normalized = normalize_text(value)
        if len(normalized) >= 4:
            terms.append(normalized)
    return list(dict.fromkeys(terms))


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", value.lower())).strip()


def identity_matches(text: str, record: dict[str, Any]) -> bool:
    normalized = normalize_text(text)
    terms = identity_terms(record)
    if any(term in normalized for term in terms):
        return True
    name_tokens = [token for token in normalize_text(str(record.get("name", ""))).split() if len(token) >= 4]
    return len(name_tokens) >= 2 and sum(token in normalized for token in name_tokens) >= 2


def facet_matches(text: str, facet: str) -> bool:
    normalized = normalize_text(text)
    return any(normalize_text(term) in normalized for term in FACET_TERMS.get(facet, (facet,)))


def _html_text(content: bytes) -> str:
    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(content, "html.parser")
        for element in soup(["script", "style", "noscript", "svg"]):
            element.decompose()
        return soup.get_text(" ", strip=True)
    except ImportError:
        text = re.sub(rb"<script\b.*?</script>", b" ", content, flags=re.I | re.S)
        text = re.sub(rb"<style\b.*?</style>", b" ", text, flags=re.I | re.S)
        return unescape(re.sub(r"<[^>]+>", " ", text.decode("utf-8", "ignore")))


def _pdf_text(content: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        return ""
    try:
        logging.getLogger("pypdf").setLevel(logging.ERROR)
        reader = PdfReader(io.BytesIO(content))
        return " ".join((page.extract_text() or "") for page in reader.pages[:200])
    except Exception:
        return ""


def _docx_text(content: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            document = archive.read("word/document.xml").decode("utf-8", "ignore")
    except (KeyError, OSError, zipfile.BadZipFile):
        return ""
    return unescape(re.sub(r"<[^>]+>", " ", document))


def extract_text(content: bytes, content_type: str, url: str) -> str:
    kind = content_type.lower()
    path = urlparse(url).path.lower()
    if "pdf" in kind or path.endswith(".pdf"):
        text = _pdf_text(content)
    elif "wordprocessingml" in kind or path.endswith(".docx"):
        text = _docx_text(content)
    elif "html" in kind or path.endswith((".htm", ".html")) or not kind:
        text = _html_text(content)
    elif kind.startswith("text/") or "json" in kind or "xml" in kind:
        text = content.decode("utf-8", "ignore")
    else:
        text = ""
    return re.sub(r"\s+", " ", text).strip()


def fetch_source(url: str, timeout: float = 20.0) -> FetchResult:
    try:
        response = requests.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=timeout,
            allow_redirects=True,
        )
        content = response.content[:MAX_SOURCE_BYTES]
        content_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip()
        text = extract_text(content, content_type, response.url) if response.ok else ""
        return FetchResult(
            url=url,
            final_url=response.url,
            status_code=response.status_code,
            content_type=content_type or None,
            content_sha256=hashlib.sha256(content).hexdigest() if content else None,
            text=text,
            error=None if response.ok else f"HTTP {response.status_code}",
        )
    except requests.RequestException as exc:
        return FetchResult(url, url, None, None, None, "", str(exc))


def _positions(text: str, needle: str, maximum: int = 30) -> list[int]:
    positions: list[int] = []
    start = 0
    while needle and len(positions) < maximum:
        position = text.find(needle, start)
        if position < 0:
            break
        positions.append(position)
        start = position + max(1, len(needle))
    return positions


def evidence_excerpt(text: str, record: dict[str, Any], facet: str, limit: int = 1500) -> str | None:
    if not text:
        return None
    normalized = normalize_text(text)
    identity_positions = [
        position
        for needle in identity_terms(record)
        for position in _positions(normalized, needle)
    ]
    facet_positions = [
        position
        for term in FACET_TERMS.get(facet, ())
        for position in _positions(normalized, normalize_text(term))
    ]
    if not identity_positions and not facet_positions:
        return None
    centers: list[int] = []
    if identity_positions and facet_positions:
        pairs = sorted(
            (
                (abs(identity - topic), identity, topic)
                for identity in identity_positions
                for topic in facet_positions
            ),
            key=lambda item: item[0],
        )
        for _distance, identity, topic in pairs:
            center = (identity + topic) // 2
            if all(abs(center - existing) > 350 for existing in centers):
                centers.append(center)
            if len(centers) == 3:
                break
    else:
        centers = (identity_positions or facet_positions)[:3]
    window_size = max(300, limit // max(1, len(centers)))
    windows = []
    for center in centers:
        start = max(0, center - window_size // 2)
        windows.append(normalized[start : start + window_size])
    return " ... ".join(windows)[:limit]


def audit_source(
    source: dict[str, Any],
    record: dict[str, Any],
    facet: str,
    fetched: FetchResult | dict[str, Any] | None,
) -> dict[str, Any]:
    url = str(source.get("url", ""))
    if isinstance(fetched, FetchResult):
        fetched_data = fetched.__dict__
    else:
        fetched_data = fetched or {}
    text = str(fetched_data.get("text", ""))
    result = {
        "url": url,
        "title": source.get("title"),
        "publisher": source.get("publisher"),
        "document_date": source.get("document_date"),
        "supports": source.get("supports"),
        "normalized_url": normalize_url(url) if url else url,
        "source_class": source_class(url),
        "reported_source_type": source.get("source_type"),
        "http_status": fetched_data.get("status_code"),
        "final_url": fetched_data.get("final_url", url),
        "content_type": fetched_data.get("content_type"),
        "content_sha256": fetched_data.get("content_sha256"),
        "fetch_error": fetched_data.get("error"),
        "identity_match": identity_matches(text, record) if text else False,
        "facet_match": facet_matches(text, facet) if text else False,
        "excerpt": evidence_excerpt(text, record, facet),
    }
    result["reachable"] = isinstance(result["http_status"], int) and 200 <= result["http_status"] < 400
    result["usable"] = bool(
        result["reachable"]
        and result["content_sha256"]
        and result["identity_match"]
        and result["facet_match"]
    )
    return result


def audit_facet(
    facet_name: str,
    facet: dict[str, Any] | None,
    record: dict[str, Any],
    fetched_by_url: dict[str, FetchResult | dict[str, Any]],
) -> dict[str, Any]:
    if not isinstance(facet, dict):
        return {
            "state": "missing",
            "recommended_action": "research",
            "schema_valid": False,
            "evidence_valid": False,
            "promotion_ready": False,
            "reasons": ["facet is missing from the final result"],
            "sources": [],
        }
    confidence = facet.get("confidence")
    value = str(facet.get("value", ""))
    sources = facet.get("sources") if isinstance(facet.get("sources"), list) else []
    source_audits = [
        audit_source(source, record, facet_name, fetched_by_url.get(normalize_url(str(source.get("url", "")))))
        for source in sources
        if isinstance(source, dict)
    ]
    return evaluate_facet(facet_name, facet, source_audits)


def evaluate_facet(
    facet_name: str,
    facet: dict[str, Any],
    source_audits: list[dict[str, Any]],
) -> dict[str, Any]:
    reasons: list[str] = []
    confidence = facet.get("confidence")
    value = str(facet.get("value", ""))
    sources = facet.get("sources") if isinstance(facet.get("sources"), list) else []
    schema_valid = bool(value.strip() and confidence in {"high", "medium", "low", "insufficient"} and sources)
    if not schema_valid:
        reasons.append("facet does not satisfy the structured output contract")
    if confidence not in {"high", "medium"}:
        reasons.append(f"confidence {confidence or 'missing'} is below the promotion threshold")
    negative = is_negative_claim(value)
    out_of_scope = bool(
        facet_name in {"permit_status", "air_permit_status"}
        and re.search(r"\b(?:PILOT|payment in lieu of taxes|tax (?:agreement|credit|incentive))\b", value, re.I)
    )
    if out_of_scope:
        reasons.append("permit facet contains an out-of-scope financing or tax claim")
    if negative:
        if facet_name == "legal_status":
            reasons.append("negative legal findings require human review")
        elif facet_name == "air_permit_status":
            reasons.append("air-permit non-applicability requires a reviewed regulatory rule")
        else:
            reasons.append("negative or absence finding requires human review")
    usable_primary = [
        source for source in source_audits if source["usable"] and source["source_class"] in PRIMARY_TYPES
    ]
    if not usable_primary:
        reasons.append("no reachable facility-specific primary source text supports the facet")
    evidence_valid = (
        schema_valid
        and confidence in {"high", "medium"}
        and bool(usable_primary)
        and not negative
        and not out_of_scope
    )
    promotion_ready = evidence_valid and not reasons
    if promotion_ready:
        recommended_action = "promote"
    elif negative and facet_name == "air_permit_status":
        recommended_action = "regulatory_rule"
    elif negative:
        recommended_action = "human_review"
    elif out_of_scope:
        recommended_action = "human_review"
    else:
        recommended_action = "research"
    return {
        "state": "promotion_ready" if promotion_ready else "review",
        "recommended_action": recommended_action,
        "schema_valid": schema_valid,
        "evidence_valid": evidence_valid,
        "promotion_ready": promotion_ready,
        "confidence": confidence,
        "negative_claim": negative,
        "out_of_scope": out_of_scope,
        "reasons": list(dict.fromkeys(reasons)),
        "value": value,
        "basis": facet.get("basis"),
        "fields": facet.get("fields"),
        "field_evidence": facet.get("field_evidence"),
        "sources": source_audits,
    }


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSONL in {path} line {line_number}: {exc}") from exc
        if not isinstance(value, dict):
            raise ValueError(f"expected object in {path} line {line_number}")
        rows.append(value)
    return rows


def atomic_write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def atomic_write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    content = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)
