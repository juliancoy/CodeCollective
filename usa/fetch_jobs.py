#!/usr/bin/env python3
"""Fetch and normalize USAJOBS HistoricJoa data for local/static use."""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


API_URL = "https://data.usajobs.gov/api/historicjoa"
SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT = SCRIPT_DIR / "data" / "usajobs.json"
DEFAULT_RESULTS_PER_PAGE = 1000
DEFAULT_TIMEOUT = 90
DEFAULT_RETRIES = 5


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export USAJOBS HistoricJoa data to a local JSON file.")
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help=f"Output JSON path (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--input-json",
        help="Path to a previously downloaded raw HistoricJoa JSON response to normalize instead of calling the API.",
    )
    parser.add_argument(
        "--hiring-agency-code",
        action="append",
        default=[],
        help="HistoricJoa HiringAgencyCodes filter. Repeatable.",
    )
    parser.add_argument(
        "--hiring-department-code",
        action="append",
        default=[],
        help="HistoricJoa HiringDepartmentCodes filter. Repeatable.",
    )
    parser.add_argument(
        "--position-series",
        action="append",
        default=[],
        help="HistoricJoa PositionSeries filter. Repeatable.",
    )
    parser.add_argument(
        "--announcement-number",
        action="append",
        default=[],
        help="HistoricJoa AnnouncementNumbers filter. Repeatable.",
    )
    parser.add_argument(
        "--usajobs-control-number",
        action="append",
        default=[],
        help="HistoricJoa USAJOBSControlNumbers filter. Repeatable.",
    )
    parser.add_argument(
        "--start-position-open-date",
        help="HistoricJoa StartPositionOpenDate filter in YYYY-MM-DD format.",
    )
    parser.add_argument(
        "--end-position-open-date",
        help="HistoricJoa EndPositionOpenDate filter in YYYY-MM-DD format.",
    )
    parser.add_argument(
        "--start-position-close-date",
        help="HistoricJoa StartPositionCloseDate filter in YYYY-MM-DD format. Defaults to today unless --all-postings is set.",
    )
    parser.add_argument(
        "--end-position-close-date",
        help="HistoricJoa EndPositionCloseDate filter in YYYY-MM-DD format.",
    )
    parser.add_argument(
        "--all-postings",
        action="store_true",
        help="Do not default to current/future-closing postings; fetch the full matching HistoricJoa archive.",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=0,
        help="Maximum continuation pages to request. Use 0 for all pages (default: 0).",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help=f"HTTP timeout in seconds (default: {DEFAULT_TIMEOUT})",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=DEFAULT_RETRIES,
        help=f"Retry count for transient HTTP 5xx failures (default: {DEFAULT_RETRIES})",
    )
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


def parse_date(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def parse_date_iso(value: Any) -> str:
    parsed = parse_date(value)
    return parsed.isoformat() if parsed else str(value or "").strip()


def salary_summary(record: dict[str, Any]) -> str:
    minimum = record.get("minimumSalary")
    maximum = record.get("maximumSalary")
    salary_type = str(record.get("salaryType") or "").strip()
    if minimum in (None, "") and maximum in (None, ""):
        return ""
    if minimum == maximum:
        return f"${float(minimum):,.0f} {salary_type}".strip()
    try:
        return f"${float(minimum):,.0f} - ${float(maximum):,.0f} {salary_type}".strip()
    except (TypeError, ValueError):
        return ""


def build_locations(record: dict[str, Any]) -> tuple[list[str], str]:
    locations = unique_strings(
        [
            ", ".join(
                part for part in [
                    str(item.get("positionLocationCity") or "").strip(),
                    str(item.get("positionLocationState") or "").strip(),
                    str(item.get("positionLocationCountry") or "").strip(),
                ] if part
            )
            for item in coerce_list(record.get("positionLocations"))
            if isinstance(item, dict)
        ]
    )
    return locations, "; ".join(locations)


def is_open_record(record: dict[str, Any], today: date) -> bool:
    open_date = parse_date(record.get("positionOpenDate"))
    close_date = parse_date(record.get("positionExpireDate")) or parse_date(record.get("positionCloseDate"))
    status = str(record.get("positionOpeningStatus") or "").strip().lower()

    if open_date and open_date > today:
        return False
    if close_date and close_date < today:
        return False
    if "cancel" in status or "removed" in status:
        return False
    return True


def normalize_job(record: dict[str, Any], today: date) -> dict[str, Any]:
    locations, location_display = build_locations(record)
    hiring_paths = unique_strings(
        [
            item.get("hiringPath")
            for item in coerce_list(record.get("hiringPaths"))
            if isinstance(item, dict)
        ]
    )
    job_categories = unique_strings(
        [
            item.get("series")
            for item in coerce_list(record.get("jobCategories"))
            if isinstance(item, dict)
        ]
    )
    work_schedule = str(record.get("workSchedule") or "").strip()
    appointment_type = str(record.get("appointmentType") or "").strip()
    opening_status = str(record.get("positionOpeningStatus") or "").strip()
    status = "Open" if is_open_record(record, today) else (opening_status or "Closed")

    return {
        "job_id": str(record.get("usajobsControlNumber") or "").strip(),
        "position_id": str(record.get("announcementNumber") or "").strip(),
        "title": str(record.get("positionTitle") or "").strip(),
        "organization_name": str(record.get("hiringAgencyName") or "").strip(),
        "department_name": str(record.get("hiringDepartmentName") or "").strip(),
        "agency": str(record.get("hiringAgencyName") or record.get("hiringDepartmentName") or "Unknown agency").strip(),
        "agencies": unique_strings([record.get("hiringAgencyName"), record.get("hiringDepartmentName")]),
        "status": status,
        "opening_status": opening_status,
        "publication_date": parse_date_iso(record.get("positionOpenDate")),
        "close_date": parse_date_iso(record.get("positionExpireDate") or record.get("positionCloseDate")),
        "location_display": location_display,
        "locations": locations,
        "remote_indicator": str(record.get("teleworkEligible") or "").strip().upper() == "Y",
        "telework_eligible": "Yes" if str(record.get("teleworkEligible") or "").strip().upper() == "Y" else "No",
        "job_categories": job_categories,
        "position_schedule": unique_strings([work_schedule]),
        "position_offering_type": unique_strings([appointment_type]),
        "hiring_paths": hiring_paths,
        "categories": unique_strings(job_categories + [work_schedule, appointment_type] + hiring_paths),
        "summary": "",
        "major_duties": [],
        "qualification_summary": "",
        "salary_summary": salary_summary(record),
        "salary": [
            {
                "MinimumRange": record.get("minimumSalary"),
                "MaximumRange": record.get("maximumSalary"),
                "RateIntervalCode": record.get("salaryType"),
            }
        ],
        "grade_low": str(record.get("minimumGrade") or "").strip(),
        "grade_high": str(record.get("maximumGrade") or "").strip(),
        "travel_code": str(record.get("travelRequirement") or "").strip(),
        "relocation": "Yes" if str(record.get("relocationExpensesReimbursed") or "").strip().upper() == "Y" else "No",
        "security_clearance": str(record.get("securityClearance") or "").strip(),
        "drug_test_required": "Yes" if str(record.get("drugTestRequired") or "").strip().upper() == "Y" else "No",
        "total_openings": str(record.get("totalOpenings") or "").strip(),
        "who_may_apply": str(record.get("whoMayApply") or "").strip(),
        "apply_url": "",
        "detail_url": "",
        "position_uri": "",
        "requirements": "",
        "required_documents": "",
        "benefits": "",
        "how_to_apply": "",
        "raw_descriptor": record,
    }


def dedupe_jobs(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: dict[str, dict[str, Any]] = {}
    for record in records:
        key = record.get("job_id") or record.get("position_id") or record.get("title")
        if key and key not in deduped:
            deduped[str(key)] = record
    return list(deduped.values())


def normalize_payload(raw_payloads: list[dict[str, Any]], source_description: str) -> dict[str, Any]:
    today = date.today()
    raw_items: list[dict[str, Any]] = []
    search_summaries: list[dict[str, Any]] = []

    for payload in raw_payloads:
        paging = payload.get("paging") or {}
        metadata = paging.get("metadata") or {}
        items = coerce_list(payload.get("data"))
        raw_items.extend(item for item in items if isinstance(item, dict))
        search_summaries.append({
            "total_count": metadata.get("totalCount"),
            "page_size": metadata.get("pageSize"),
            "continuation_token": metadata.get("continuationToken") or "",
            "next": str(paging.get("next") or ""),
        })

    records = dedupe_jobs([normalize_job(item, today) for item in raw_items])
    records.sort(key=lambda record: (record.get("close_date", ""), record.get("title", "")), reverse=True)

    return {
        "fetched_at": utc_now(),
        "source_url": source_description,
        "record_count": len(records),
        "searches": search_summaries,
        "records": records,
    }


def fetch_api_payload(params: dict[str, Any], timeout: int = DEFAULT_TIMEOUT, retries: int = DEFAULT_RETRIES) -> dict[str, Any]:
    query = urlencode([(key, value) for key, values in params.items() for value in (values if isinstance(values, list) else [values]) if value not in ("", None)])
    request = Request(f"{API_URL}?{query}")
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
            print(
                f"Retrying HistoricJoa request after HTTP {exc.code} "
                f"(attempt {attempt + 1}/{retries}, wait {delay}s)",
                file=sys.stderr,
                flush=True,
            )
        except URLError:
            if attempt >= retries:
                raise
            delay = min(30, 2 ** (attempt + 1))
            print(
                f"Retrying HistoricJoa request after network error "
                f"(attempt {attempt + 1}/{retries}, wait {delay}s)",
                file=sys.stderr,
                flush=True,
            )
        attempt += 1
        time.sleep(delay)


def build_initial_params(args: argparse.Namespace) -> dict[str, Any]:
    start_close_date = args.start_position_close_date
    if not args.all_postings and not start_close_date:
        start_close_date = date.today().isoformat()

    return {
        "HiringAgencyCodes": args.hiring_agency_code,
        "HiringDepartmentCodes": args.hiring_department_code,
        "PositionSeries": args.position_series,
        "AnnouncementNumbers": args.announcement_number,
        "USAJOBSControlNumbers": args.usajobs_control_number,
        "StartPositionOpenDate": args.start_position_open_date,
        "EndPositionOpenDate": args.end_position_open_date,
        "StartPositionCloseDate": start_close_date,
        "EndPositionCloseDate": args.end_position_close_date,
    }


def fetch_from_api(args: argparse.Namespace) -> tuple[list[dict[str, Any]], str]:
    payloads: list[dict[str, Any]] = []
    params = build_initial_params(args)
    source_description = f"{API_URL}?{urlencode([(key, value) for key, values in params.items() for value in (values if isinstance(values, list) else [values]) if value not in ('', None)])}"
    continuation_token = ""
    page_count = 0

    while True:
        request_params = dict(params)
        if continuation_token:
            request_params["continuationtoken"] = continuation_token
        payload = fetch_api_payload(request_params, timeout=args.timeout, retries=args.retries)
        payloads.append(payload)
        page_count += 1
        if args.max_pages and page_count >= args.max_pages:
            break
        paging = payload.get("paging") or {}
        metadata = paging.get("metadata") or {}
        continuation_token = str(metadata.get("continuationToken") or "").strip()
        if not continuation_token:
            break

    return payloads, source_description


def main() -> int:
    args = parse_args()
    output_path = ensure_output_path(args.output)

    try:
        if args.input_json:
            input_path = Path(args.input_json)
            if not input_path.is_absolute():
                input_path = (Path.cwd() / input_path).resolve()
            raw_payload = read_json(input_path)
            payload = normalize_payload([raw_payload], str(input_path))
        else:
            raw_payloads, source_description = fetch_from_api(args)
            payload = normalize_payload(raw_payloads, source_description)
    except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Failed to export USAJOBS HistoricJoa data: {exc}") from exc

    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {payload['record_count']} records to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
