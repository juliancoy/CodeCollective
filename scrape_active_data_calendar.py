from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Any, Dict, List

import pytz
from bs4 import BeautifulSoup

from http_client import build_session, polite_get

USER_AGENT = (
    "Mozilla/5.0 (compatible; CodeCollectiveBot/1.0; "
    "+https://github.com/juliancoy/CodeCollective)"
)
EASTERN_TZ = pytz.timezone("America/New_York")
CONTENT_NS = {"content": "http://purl.org/rss/1.0/modules/content/"}
TITLE_DATE_SUFFIX_RE = re.compile(r"\s+\(\d{1,2}/\d{1,2}/\d{4}\)\s*$")


def _clean_title(title: str) -> str:
    return TITLE_DATE_SUFFIX_RE.sub("", (title or "").strip())


def _extract_field(fragment: BeautifulSoup, label: str) -> str:
    for strong in fragment.find_all(["b", "strong"]):
        text = strong.get_text(" ", strip=True).rstrip(":").strip().lower()
        if text != label.lower():
            continue
        cell = strong.find_parent("td")
        if cell is None:
            continue
        sibling = cell.find_next_sibling("td")
        if sibling is None:
            extracted = cell.get_text(" ", strip=True)
            extracted = re.sub(rf"^{re.escape(label)}\s*:?\s*", "", extracted, flags=re.I).strip()
            if extracted:
                return extracted
            continue
        extracted = sibling.get_text(" ", strip=True).strip()
        if extracted:
            return extracted
    return ""


def _extract_description(fragment: BeautifulSoup) -> str:
    text = fragment.get_text("\n", strip=True)
    text = html.unescape(text)
    text = re.sub(
        r"\b(Start|End) Date:\s*[^\n]+(\n|$)",
        "",
        text,
        flags=re.I,
    )
    text = re.sub(
        r"\b(Start|End) Time:\s*[^\n]+(\n|$)",
        "",
        text,
        flags=re.I,
    )
    text = re.sub(r"\bLocation:\s*[^\n]+(\n|$)", "", text, flags=re.I)
    text = re.sub(r"\n{2,}", "\n", text).strip()
    return text


def _to_iso(date_text: str, time_text: str) -> str:
    date_text = (date_text or "").strip()
    time_text = (time_text or "").strip()
    if not date_text:
        return ""
    parsed = datetime.strptime(
        f"{date_text} {time_text or '12:00 AM'}",
        "%m/%d/%Y %I:%M %p",
    )
    return EASTERN_TZ.localize(parsed).isoformat()


def _parse_item(item: ET.Element, source_url: str) -> Dict[str, Any] | None:
    raw_title = item.findtext("title") or ""
    title = _clean_title(raw_title)
    link = (item.findtext("link") or "").strip() or source_url
    content_html = item.findtext("content:encoded", "", CONTENT_NS) or ""
    description_html = item.findtext("description") or ""
    fragment = BeautifulSoup(content_html or description_html, "html.parser")

    start_date = _extract_field(fragment, "Start Date")
    start_time = _extract_field(fragment, "Start Time")
    end_date = _extract_field(fragment, "End Date")
    end_time = _extract_field(fragment, "End Time")
    location = _extract_field(fragment, "Location")

    if not title or not start_date:
        return None

    return {
        "name": title,
        "description": _extract_description(fragment),
        "startDate": _to_iso(start_date, start_time),
        "endTime": _to_iso(end_date or start_date, end_time or start_time),
        "url": link,
        "status": "ACTIVE",
        "location": {"name": location, "address": location},
        "imageUrl": "",
        "source": source_url,
    }


def _parse_feed(xml_text: str, source_url: str) -> List[Dict[str, Any]]:
    root = ET.fromstring(xml_text)
    events: List[Dict[str, Any]] = []
    for item in root.findall("./channel/item"):
        parsed = _parse_item(item, source_url)
        if parsed:
            events.append(parsed)
    return events


def scrape(source_url: str) -> List[Dict[str, Any]]:
    session = build_session(user_agent=USER_AGENT)
    response = polite_get(session, source_url, timeout=30, allow_redirects=True)
    response.raise_for_status()
    return _parse_feed(response.text, source_url)
