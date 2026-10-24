#!/usr/bin/env python3
"""Fetch and normalize USAJOBS Search API results using shard queries."""

from __future__ import annotations

import argparse
import gzip
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


SEARCH_API_URL = "https://data.usajobs.gov/api/search"
AGENCY_CODELIST_URL = "https://data.usajobs.gov/api/codelist/agencysubelements"
SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT = SCRIPT_DIR / "data" / "usajobs.json"
DEFAULT_FRONTEND_OUTPUT = SCRIPT_DIR / "data" / "usajobs-lite.json"
DEFAULT_RESULTS_PER_PAGE = 500
DEFAULT_TIMEOUT = 90
DEFAULT_RETRIES = 5
MAX_ROWS_PER_QUERY = 10_000
SCHEDULE_CODES = ("1", "2", "3", "4", "5", "6")
DEFAULT_MAX_AGE_DAYS = 7
LEAN_RECORD_KEYS = (
    "job_id",
    "position_id",
    "title",
    "organization_name",
    "department_name",
    "agency",
    "agencies",
    "status",
    "publication_date",
    "close_date",
    "location_display",
    "locations",
    "remote_indicator",
    "telework_eligible",
    "job_categories",
    "position_schedule",
    "position_offering_type",
    "hiring_paths",
    "categories",
    "summary",
    "salary_summary",
    "salary",
    "pay_plan",
    "grade_low",
    "grade_high",
    "travel_code",
    "relocation",
    "security_clearance",
    "drug_test_required",
    "total_openings",
    "who_may_apply",
    "apply_url",
    "detail_url",
    "position_uri",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export USAJOBS Search API data using sharded queries.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help=f"Output JSON path (default: {DEFAULT_OUTPUT})")
    parser.add_argument("--frontend-output", default=str(DEFAULT_FRONTEND_OUTPUT), help=f"Lean frontend JSON path (default: {DEFAULT_FRONTEND_OUTPUT})")
    parser.add_argument("--input-json", help="Path to a previously downloaded raw Search API JSON response to normalize.")
    parser.add_argument("--keyword", action="append", default=[], help="Keyword filter. Repeatable.")
    parser.add_argument("--location", action="append", default=[], help="LocationName filter. Repeatable.")
    parser.add_argument("--organization", action="append", default=[], help="Organization shard/code filter. Repeatable.")
    parser.add_argument("--job-category-code", action="append", default=[], help="JobCategoryCode filter. Repeatable.")
    parser.add_argument("--position-schedule-type-code", action="append", default=[], help="PositionScheduleTypeCode filter. Repeatable.")
    parser.add_argument("--hiring-path", action="append", default=[], help="HiringPath filter. Repeatable.")
    parser.add_argument("--remote-indicator", choices=["true", "false"], help="RemoteIndicator filter.")
    parser.add_argument("--who-may-apply", default="", help="Optional WhoMayApply filter.")
    parser.add_argument("--date-posted", type=int, help="DatePosted filter in days, 0-60.")
    parser.add_argument("--results-per-page", type=int, default=DEFAULT_RESULTS_PER_PAGE, help=f"Page size up to 500 (default: {DEFAULT_RESULTS_PER_PAGE})")
    parser.add_argument("--max-pages-per-query", type=int, default=0, help="Maximum pages per shard query. 0 means all available pages.")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help=f"HTTP timeout in seconds (default: {DEFAULT_TIMEOUT})")
    parser.add_argument("--retries", type=int, default=DEFAULT_RETRIES, help=f"Retry count for transient failures (default: {DEFAULT_RETRIES})")
    parser.add_argument("--no-auto-shard", action="store_true", help="Do not auto-shard by Organization code list.")
    parser.add_argument("--max-age-days", type=int, default=DEFAULT_MAX_AGE_DAYS, help=f"Skip network fetch when the full dump is newer than this many days (default: {DEFAULT_MAX_AGE_DAYS})")
    parser.add_argument("--force-refresh", action="store_true", help="Ignore local cache age and fetch fresh Search data.")
    return parser.parse_args()


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def ensure_output_path(value: str) -> Path:
    output_path = Path(value)
    if not output_path.is_absolute():
        output_path = (Path.cwd() / output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    return output_path


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def payload_timestamp(payload: dict[str, Any], path: Path) -> datetime | None:
    fetched_at = str(payload.get("fetched_at") or "").strip()
    if fetched_at:
        try:
            return datetime.fromisoformat(fetched_at.replace("Z", "+00:00")).astimezone(UTC)
        except ValueError:
            pass
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
    except FileNotFoundError:
        return None


def coerce_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def unique_strings(values: list[Any]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def parse_iso_date(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if text.endswith("Z"):
        return text
    try:
        return datetime.fromisoformat(text).astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    except ValueError:
        return text


def compensation_summary(remuneration: list[dict[str, Any]]) -> str:
    if not remuneration:
        return ""
    first = remuneration[0]
    minimum = str(first.get("MinimumRange", "")).strip()
    maximum = str(first.get("MaximumRange", "")).strip()
    interval = str(first.get("Description", "") or first.get("RateIntervalCode", "")).strip()
    if minimum and maximum:
        return f"${minimum} - ${maximum} {interval}".strip()
    return ""


def normalize_job(item: dict[str, Any]) -> dict[str, Any]:
    descriptor = item.get("MatchedObjectDescriptor") or {}
    details = ((descriptor.get("UserArea") or {}).get("Details") or {})
    job_grade = coerce_list(descriptor.get("JobGrade"))
    pay_plan = ""
    if job_grade and isinstance(job_grade[0], dict):
        pay_plan = str(job_grade[0].get("Code") or job_grade[0].get("Name") or "").strip().upper()

    job_categories = unique_strings([category.get("Name") for category in coerce_list(descriptor.get("JobCategory")) if isinstance(category, dict)])
    schedules = unique_strings([schedule.get("Name") for schedule in coerce_list(descriptor.get("PositionSchedule")) if isinstance(schedule, dict)])
    offering_types = unique_strings([offering.get("Name") for offering in coerce_list(descriptor.get("PositionOfferingType")) if isinstance(offering, dict)])
    locations = unique_strings([location.get("LocationName") for location in coerce_list(details.get("Locations")) if isinstance(location, dict)])
    if not locations:
        locations = unique_strings([location.get("LocationName") for location in coerce_list(descriptor.get("PositionLocation")) if isinstance(location, dict)])
    hiring_paths = unique_strings([value.get("Name") if isinstance(value, dict) else value for value in coerce_list(details.get("HiringPath"))])
    major_duties = unique_strings(coerce_list(details.get("MajorDuties")))
    organizations = unique_strings([descriptor.get("OrganizationName"), descriptor.get("DepartmentName")])
    categories = unique_strings(job_categories + schedules + offering_types + hiring_paths)
    summary_parts = unique_strings([details.get("JobSummary"), descriptor.get("QualificationSummary"), details.get("MajorDutiesSummary")])

    close_date = parse_iso_date(descriptor.get("ApplicationCloseDate", ""))
    is_open = False
    if close_date:
        try:
            is_open = datetime.fromisoformat(close_date.replace("Z", "+00:00")) >= datetime.now(UTC)
        except ValueError:
            is_open = False

    apply_uri = descriptor.get("ApplyURI")
    apply_url = ""
    if isinstance(apply_uri, list) and apply_uri:
      apply_url = str(apply_uri[0] or "").strip()
    elif isinstance(apply_uri, str):
      apply_url = apply_uri.strip()

    return {
        "job_id": str(item.get("MatchedObjectId", "")).strip(),
        "position_id": str(descriptor.get("PositionID", "")).strip(),
        "title": str(descriptor.get("PositionTitle", "")).strip(),
        "organization_name": str(descriptor.get("OrganizationName", "")).strip(),
        "department_name": str(descriptor.get("DepartmentName", "")).strip(),
        "agency": unique_strings([descriptor.get("OrganizationName"), descriptor.get("DepartmentName")])[0] if unique_strings([descriptor.get("OrganizationName"), descriptor.get("DepartmentName")]) else "Unknown agency",
        "agencies": organizations,
        "status": "Open" if is_open else "Closed",
        "publication_date": parse_iso_date(descriptor.get("PublicationStartDate", "")),
        "close_date": close_date,
        "location_display": str(descriptor.get("PositionLocationDisplay", "")).strip(),
        "locations": locations,
        "remote_indicator": bool(details.get("RemoteIndicator")),
        "telework_eligible": str(details.get("TeleworkEligible", "")).strip(),
        "job_categories": job_categories,
        "position_schedule": schedules,
        "position_offering_type": offering_types,
        "hiring_paths": hiring_paths,
        "categories": categories,
        "summary": "\n\n".join(summary_parts).strip(),
        "major_duties": major_duties,
        "qualification_summary": str(descriptor.get("QualificationSummary", "")).strip(),
        "salary_summary": compensation_summary(coerce_list(descriptor.get("PositionRemuneration"))),
        "salary": coerce_list(descriptor.get("PositionRemuneration")),
        "pay_plan": pay_plan,
        "grade_low": str(details.get("LowGrade", "")).strip(),
        "grade_high": str(details.get("HighGrade", "")).strip(),
        "travel_code": str(details.get("TravelCode", "")).strip(),
        "relocation": str(details.get("Relocation", "")).strip(),
        "security_clearance": str(details.get("SecurityClearance", "")).strip(),
        "drug_test_required": str(details.get("DrugTestRequired", "")).strip(),
        "total_openings": str(details.get("TotalOpenings", "")).strip(),
        "who_may_apply": str((details.get("WhoMayApply") or {}).get("Name", "")).strip(),
        "apply_url": apply_url,
        "detail_url": str(descriptor.get("PositionURI") or "").strip(),
        "position_uri": str(descriptor.get("PositionURI", "")).strip(),
        "requirements": str(details.get("Requirements", "")).strip(),
        "required_documents": str(details.get("RequiredDocuments", "")).strip(),
        "benefits": str(details.get("Benefits", "")).strip(),
        "how_to_apply": str(details.get("HowToApply", "")).strip(),
        "raw_descriptor": descriptor,
    }


def dedupe_jobs(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: dict[str, dict[str, Any]] = {}
    for record in records:
        key = record.get("job_id") or record.get("position_id") or record.get("detail_url") or record.get("title")
        if key and key not in deduped:
            deduped[str(key)] = record
    return list(deduped.values())


def normalize_payload(raw_payloads: list[dict[str, Any]], source_description: str) -> dict[str, Any]:
    raw_items: list[dict[str, Any]] = []
    search_summaries: list[dict[str, Any]] = []

    for payload in raw_payloads:
        result = payload.get("SearchResult") or {}
        items = coerce_list(result.get("SearchResultItems"))
        raw_items.extend(item for item in items if isinstance(item, dict))
        params = payload.get("SearchParameters") or {}
        if params.get("Page") in ("", 1, "1"):
            search_summaries.append({
                "search_result_count_all": result.get("SearchResultCountAll"),
                "organization": params.get("Organization", ""),
                "position_schedule_type_code": params.get("PositionScheduleTypeCode", ""),
            })

    records = dedupe_jobs([normalize_job(item) for item in raw_items])
    records.sort(key=lambda record: (record.get("close_date", ""), record.get("title", "")), reverse=True)

    return {
        "fetched_at": utc_now(),
        "source_url": source_description,
        "record_count": len(records),
        "searches": search_summaries,
        "records": records,
    }


def simplify_payload(payload: dict[str, Any]) -> dict[str, Any]:
    records = payload.get("records") or []
    lean_records = [
        {key: record.get(key) for key in LEAN_RECORD_KEYS if key in record}
        for record in records
        if isinstance(record, dict)
    ]
    return {
        "fetched_at": payload.get("fetched_at", ""),
        "source_url": payload.get("source_url", SEARCH_API_URL),
        "record_count": len(lean_records),
        "searches": payload.get("searches", []),
        "records": lean_records,
    }


def write_json_and_gzip(payload: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    compact_json = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    output_path.write_text(compact_json, encoding="utf-8")
    gzip_path = gzip_path_for(output_path)
    with gzip.open(gzip_path, "wt", encoding="utf-8") as handle:
        handle.write(compact_json)


def maybe_use_cached_full_payload(output_path: Path, max_age_days: int) -> dict[str, Any] | None:
    if not output_path.exists():
        return None
    payload = read_json(output_path)
    timestamp = payload_timestamp(payload, output_path)
    if timestamp is None:
        return None
    age_seconds = (datetime.now(UTC) - timestamp).total_seconds()
    if age_seconds > max_age_days * 86400:
        return None
    print(
        f"Skipping Search fetch; existing full dump is {age_seconds / 86400:.1f} days old which is below the {max_age_days}-day refresh threshold.",
        file=sys.stderr,
        flush=True,
    )
    return payload


def is_fresh_output(path: Path, max_age_days: int) -> bool:
    if not path.exists():
        return False
    try:
        age_seconds = (datetime.now(UTC) - datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)).total_seconds()
    except FileNotFoundError:
        return False
    return age_seconds <= max_age_days * 86400


def gzip_path_for(path: Path) -> Path:
    return path.with_suffix(path.suffix + ".gz")


def frontend_outputs_are_fresh(path: Path, max_age_days: int) -> bool:
    gzip_path = gzip_path_for(path)
    return is_fresh_output(path, max_age_days) and is_fresh_output(gzip_path, max_age_days)


def build_headers() -> dict[str, str]:
    api_key = os.environ.get("USAJOBS_API_KEY", "").strip()
    user_agent = os.environ.get("USAJOBS_USER_AGENT", "").strip() or os.environ.get("USAJOBS_EMAIL", "").strip()
    if not api_key or not user_agent:
        raise SystemExit("USAJOBS_API_KEY and USAJOBS_USER_AGENT (or USAJOBS_EMAIL) must be set to call the USAJOBS Search API.")
    return {"Host": "data.usajobs.gov", "User-Agent": user_agent, "Authorization-Key": api_key}


def fetch_json(url: str, headers: dict[str, str] | None = None, timeout: int = DEFAULT_TIMEOUT, retries: int = DEFAULT_RETRIES) -> dict[str, Any]:
    request = Request(url, headers=headers or {})
    attempt = 0
    while True:
        try:
            with urlopen(request, timeout=timeout) as response:  # noqa: S310
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            # Stop collection on throttling or an explicit server pause. Do not
            # retry early, switch credentials, or shard around access limits.
            if exc.code == 429 or exc.headers.get("Retry-After"):
                raise
            if exc.code not in {500, 502, 503, 504} or attempt >= retries:
                raise
            delay = min(30, 2 ** (attempt + 1))
            print(f"Retrying Search request after HTTP {exc.code} (attempt {attempt + 1}/{retries}, wait {delay}s)", file=sys.stderr, flush=True)
        except URLError:
            if attempt >= retries:
                raise
            delay = min(30, 2 ** (attempt + 1))
            print(f"Retrying Search request after network error (attempt {attempt + 1}/{retries}, wait {delay}s)", file=sys.stderr, flush=True)
        attempt += 1
        time.sleep(delay)


def fetch_search_payload(params: dict[str, Any], headers: dict[str, str], timeout: int, retries: int) -> dict[str, Any]:
    query = urlencode([(key, value) for key, values in params.items() for value in (values if isinstance(values, list) else [values]) if value not in ("", None)])
    return fetch_json(f"{SEARCH_API_URL}?{query}", headers=headers, timeout=timeout, retries=retries)


def fetch_agency_codes(timeout: int, retries: int) -> list[str]:
    payload = fetch_json(AGENCY_CODELIST_URL, timeout=timeout, retries=retries)
    code_lists = coerce_list(payload.get("CodeList"))
    valid_values = []
    for code_list in code_lists:
        if not isinstance(code_list, dict):
            continue
        valid_values = coerce_list(code_list.get("ValidValue"))
        if valid_values:
            break
    codes = [
        str(item.get("Code") or "").strip()
        for item in valid_values
        if isinstance(item, dict) and str(item.get("Code") or "").strip() and str(item.get("IsDisabled") or "No").lower() != "yes"
    ]
    return sorted(set(codes))


def split_large_shard(base_params: dict[str, Any], total_count: int) -> list[dict[str, Any]]:
    if total_count <= MAX_ROWS_PER_QUERY:
        return [base_params]
    current_schedule = str(base_params.get("PositionScheduleTypeCode") or "").strip()
    if current_schedule:
        print(
            f"Warning: shard still exceeds {MAX_ROWS_PER_QUERY} rows after schedule split: {base_params}",
            file=sys.stderr,
            flush=True,
        )
        return [base_params]
    return [{**base_params, "PositionScheduleTypeCode": code} for code in SCHEDULE_CODES]


def build_base_params(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "Keyword": args.keyword,
        "LocationName": args.location,
        "Organization": "",
        "JobCategoryCode": args.job_category_code,
        "PositionScheduleTypeCode": args.position_schedule_type_code,
        "HiringPath": args.hiring_path,
        "RemoteIndicator": args.remote_indicator,
        "WhoMayApply": args.who_may_apply,
        "DatePosted": args.date_posted,
        "Fields": "Full",
        "ResultsPerPage": max(1, min(args.results_per_page, 500)),
        "Page": 1,
    }


def build_shards(args: argparse.Namespace, timeout: int, retries: int) -> list[dict[str, Any]]:
    base = build_base_params(args)
    if args.no_auto_shard:
        organizations = args.organization or [""]
    else:
        organizations = args.organization or fetch_agency_codes(timeout, retries)
        if not organizations:
            print(
                "Agency codelist returned no shard codes; falling back to a single unsharded Search query.",
                file=sys.stderr,
                flush=True,
            )
            organizations = [""]
    return [{**base, "Organization": organization} for organization in organizations]


def fetch_all_pages_for_query(params: dict[str, Any], headers: dict[str, str], timeout: int, retries: int, max_pages_per_query: int) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    page = 1
    while True:
        request_params = dict(params)
        request_params["Page"] = page
        payload = fetch_search_payload(request_params, headers=headers, timeout=timeout, retries=retries)
        payloads.append(payload)
        result = payload.get("SearchResult") or {}
        total = int(result.get("SearchResultCountAll") or 0)
        count = int(result.get("SearchResultCount") or 0)
        if page == 1:
            print(
                f"Search shard organization={params.get('Organization') or 'ALL'} schedule={params.get('PositionScheduleTypeCode') or 'ALL'} total={total}",
                file=sys.stderr,
                flush=True,
            )
        if count == 0:
            break
        if max_pages_per_query and page >= max_pages_per_query:
            break
        if (page * int(request_params["ResultsPerPage"])) >= total:
            break
        page += 1
    return payloads


def shard_label(params: dict[str, Any]) -> str:
    return (
        f"organization={params.get('Organization') or 'ALL'} "
        f"schedule={params.get('PositionScheduleTypeCode') or 'ALL'} "
        f"keyword={','.join(params.get('Keyword') or []) or 'ALL'} "
        f"location={','.join(params.get('LocationName') or []) or 'ALL'}"
    )


def fetch_from_api(args: argparse.Namespace) -> tuple[list[dict[str, Any]], str]:
    headers = build_headers()
    initial_shards = build_shards(args, args.timeout, args.retries)
    payloads: list[dict[str, Any]] = []
    pending = list(initial_shards)
    source_description = SEARCH_API_URL
    completed_shards = 0
    total_shards_seen = len(initial_shards)

    while pending:
        shard = pending.pop(0)
        print(
            f"Starting shard {completed_shards + 1}/{total_shards_seen}: {shard_label(shard)}",
            file=sys.stderr,
            flush=True,
        )
        first_payload = fetch_search_payload(shard, headers=headers, timeout=args.timeout, retries=args.retries)
        result = first_payload.get("SearchResult") or {}
        total = int(result.get("SearchResultCountAll") or 0)
        refined_shards = split_large_shard(shard, total)
        if len(refined_shards) > 1:
            print(
                f"Splitting shard {shard_label(shard)} because total={total}",
                file=sys.stderr,
                flush=True,
            )
            pending = refined_shards + pending
            total_shards_seen += len(refined_shards) - 1
            continue
        print(
            f"Shard ready: {shard_label(shard)} total={total}",
            file=sys.stderr,
            flush=True,
        )
        payloads.append(first_payload)
        count = int(result.get("SearchResultCount") or 0)
        completed_shards += 1
        if count == 0:
            print(
                f"Shard empty: {shard_label(shard)}",
                file=sys.stderr,
                flush=True,
            )
            continue
        page = 2
        results_per_page = int(shard["ResultsPerPage"])
        while (page - 1) * results_per_page < total:
            if args.max_pages_per_query and page > args.max_pages_per_query:
                print(
                    f"Stopping shard early at page cap: {shard_label(shard)} page_cap={args.max_pages_per_query}",
                    file=sys.stderr,
                    flush=True,
                )
                break
            page_params = dict(shard)
            page_params["Page"] = page
            print(
                f"Fetching page {page} for {shard_label(shard)}",
                file=sys.stderr,
                flush=True,
            )
            payloads.append(fetch_search_payload(page_params, headers=headers, timeout=args.timeout, retries=args.retries))
            page += 1
        print(
            f"Completed shard: {shard_label(shard)}",
            file=sys.stderr,
            flush=True,
        )

    return payloads, source_description


def main() -> int:
    args = parse_args()
    output_path = ensure_output_path(args.output)
    frontend_output_path = ensure_output_path(args.frontend_output)

    try:
        if not args.force_refresh and not args.input_json:
            cached_full_payload = maybe_use_cached_full_payload(output_path, args.max_age_days)
            if cached_full_payload is not None:
                if frontend_outputs_are_fresh(frontend_output_path, args.max_age_days):
                    print(
                        f"Skipping lean rewrite; existing frontend dump and gzip are newer than {args.max_age_days} days.",
                        file=sys.stderr,
                        flush=True,
                    )
                    return 0
                lean_payload = simplify_payload(cached_full_payload)
                write_json_and_gzip(lean_payload, frontend_output_path)
                print(f"Wrote {lean_payload['record_count']} lean records to {frontend_output_path}")
                return 0
        if args.input_json:
            input_path = Path(args.input_json)
            if not input_path.is_absolute():
                input_path = (Path.cwd() / input_path).resolve()
            raw_payload = read_json(input_path)
            full_payload = normalize_payload([raw_payload], str(input_path))
        else:
            raw_payloads, source_description = fetch_from_api(args)
            full_payload = normalize_payload(raw_payloads, source_description)
    except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Failed to export USAJOBS Search data: {exc}") from exc

    lean_payload = simplify_payload(full_payload)
    write_json_and_gzip(full_payload, output_path)
    write_json_and_gzip(lean_payload, frontend_output_path)
    print(f"Wrote {full_payload['record_count']} full records to {output_path}")
    print(f"Wrote {lean_payload['record_count']} lean records to {frontend_output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
