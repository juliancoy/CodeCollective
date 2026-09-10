from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Dict, Iterable, List, Tuple

import pytz
from bs4 import BeautifulSoup, Tag

from http_client import build_session, polite_get


SOURCE_URL = "https://www.bsfs.org/bsfscldr.htm"
DEFAULT_IMAGE = "https://www.google.com/s2/favicons?domain=www.bsfs.org&sz=256"
TIMEZONE = pytz.timezone("America/New_York")
DEFAULT_LOCATION = {
    "name": "Baltimore Science Fiction Society",
    "address": "3310 East Baltimore Street",
    "city": "Baltimore",
    "state": "MD",
    "postalCode": "21224",
    "country": "US",
}

MONTH_PATTERN = re.compile(r"^(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})$")


EVENT_PATTERNS: Tuple[Dict, ...] = (
    {
        "key": "library",
        "needle": "BSFS Library Committee work session",
        "name": "BSFS Library Committee Work Session",
        "start": (12, 0),
        "end": (16, 0),
        "description": "Help sort, add to the database, and shelve books in the BSFS lending library.",
        "recurrence": {"freq": "monthly", "interval": 1, "byweekday": ["SU"], "bysetpos": [1]},
    },
    {
        "key": "fiber",
        "needle": "Fiber Arts",
        "name": "BSFS Fiber Arts Creativity Circle",
        "start": (13, 0),
        "end": (17, 0),
        "description": "Recurring fiber arts meetup for sewing, knitting, crafting, cosplay building, and related creative work.",
        "recurrence": {"freq": "monthly", "interval": 1, "byweekday": ["SA"], "bysetpos": [1]},
    },
    {
        "key": "writing",
        "needle": "Writing Circle",
        "name": "BSFS Writing Circle",
        "start": (18, 30),
        "end": (20, 30),
        "description": "SF and fantasy focused writing group hosted by BSFS. Published as Zoom-only for the listed near-term meetings.",
        "location": {"name": "Online", "address": ""},
        "recurrence": {"freq": "monthly", "interval": 1, "byweekday": ["TH"], "bysetpos": [2, 4]},
    },
    {
        "key": "poetry",
        "needle": "Speculative Poetry Workshop",
        "name": "BSFS Speculative Poetry Workshop",
        "start": (19, 0),
        "end": (20, 30),
        "description": "Monthly Zoom workshop for science fiction, fantasy, and speculative poetry authors.",
        "location": {"name": "Online", "address": ""},
        "recurrence": {"freq": "monthly", "interval": 1, "byweekday": ["WE"], "bysetpos": [3]},
    },
    {
        "key": "balticon_planning",
        "needle": "Balticon Planning Meeting",
        "name": "BSFS Balticon Planning Meeting",
        "start": (19, 0),
        "end": (20, 30),
        "description": "Monthly Balticon planning meeting, in person and by Zoom unless otherwise noted.",
        "recurrence": {"freq": "monthly", "interval": 1, "byweekday": ["SA"], "bysetpos": [2]},
    },
    {
        "key": "business",
        "needle": "BSFS Business Meeting",
        "name": "BSFS Business Meeting",
        "start": (20, 30),
        "end": (21, 30),
        "description": "Monthly Baltimore Science Fiction Society business meeting, in person and by Zoom unless otherwise noted.",
        "recurrence": {"freq": "monthly", "interval": 1, "byweekday": ["SA"], "bysetpos": [2]},
    },
    {
        "key": "film",
        "needle": "Movie",
        "name": "BSFS Film Night",
        "start": (19, 0),
        "end": (22, 0),
        "description": "Free BSFS film screening under its MPLC license. Movie titles may be available by flyer rather than published online.",
        "recurrence": {"freq": "monthly", "interval": 1, "byweekday": ["SA"], "bysetpos": [3]},
    },
    {
        "key": "gaming",
        "needle": "Alphabet Soup",
        "name": "BSFS Alphabet Soup Board Gaming",
        "start": (13, 0),
        "end": (18, 0),
        "description": "Monthly board gaming day at the BSFS Building.",
        "recurrence": {"freq": "monthly", "interval": 1, "byweekday": ["SU"], "bysetpos": [3]},
    },
    {
        "key": "rpg",
        "needle": "Tabletop Role-Playing Game Event",
        "name": "BSFS Tabletop Role-Playing Game Event",
        "start": (13, 0),
        "end": (17, 0),
        "description": "Online tabletop role-playing event rotating through tabletop science-fiction RPGs.",
        "location": {"name": "Online", "address": ""},
        "recurrence": {"freq": "monthly", "interval": 1, "byweekday": ["SU"], "bysetpos": [-1]},
    },
    {
        "key": "anime",
        "needle": "Anime Afternoon",
        "name": "BSFS Anime Afternoon Social",
        "start": (14, 0),
        "end": (18, 0),
        "description": "Monthly BSFS anime afternoon social, sometimes also hosted as a Discord watch party.",
        "recurrence": {"freq": "monthly", "interval": 1, "byweekday": ["SA"], "bysetpos": [4]},
    },
    {
        "key": "book",
        "needle": "Book Discussion Group",
        "name": "BSFS Book Discussion Group",
        "start": (18, 30),
        "end": (20, 0),
        "description": "Monthly BSFS book discussion group, in person and by Zoom unless otherwise noted.",
        "recurrence": {"freq": "monthly", "interval": 1, "byweekday": ["SA"], "bysetpos": [4]},
    },
    {
        "key": "social",
        "needle": "BSFS Social Meeting",
        "name": "BSFS Social Meeting",
        "start": (20, 0),
        "end": (23, 0),
        "description": "Monthly informal BSFS social gathering for conversation and hanging out.",
        "recurrence": {"freq": "monthly", "interval": 1, "byweekday": ["SA"], "bysetpos": [4]},
    },
)

SPECIAL_EVENTS: Tuple[Dict, ...] = (
    {
        "needle": "One Maryland One Book",
        "name": "BSFS One Maryland One Book Discussion",
        "start": (19, 30),
        "end": (21, 0),
        "description": "Discussion of the One Maryland One Book Maryland Humanities selected title, with potluck snacks starting at 6:30 PM.",
        "url": "https://www.mdhumanities.org/tag/one-maryland-one-book/",
    },
    {
        "needle": "Haloween party",
        "name": "BSFS Halloween Party",
        "start": (19, 0),
        "end": (22, 0),
        "description": "Halloween party at the BSFS Building. Check the BSFS calendar for details closer to the event.",
    },
)


def _clean_text(value: str) -> str:
    value = value.replace("\xa0", " ")
    return re.sub(r"\s+", " ", value).strip()


def _month_title_for_table(table: Tag) -> Tuple[int, int] | None:
    node = table.previous_sibling
    while node:
        if isinstance(node, Tag):
            text = _clean_text(node.get_text(" ", strip=True))
            match = MONTH_PATTERN.match(text)
            if match:
                return datetime.strptime(match.group(1), "%B").month, int(match.group(2))
        node = node.previous_sibling
    return None


def _cell_day_and_text(cell: Tag) -> Tuple[int | None, str]:
    text = _clean_text(cell.get_text(" ", strip=True))
    match = re.match(r"^(\d{1,2})\b\s*(.*)$", text)
    if not match:
        return None, text
    day = int(match.group(1))
    remainder = match.group(2).strip()
    # Some cells contain a stray holiday number before the real bullet.
    remainder = re.sub(r"^\d{1,2}\s+(?=•)", "", remainder).strip()
    return day, remainder


def _local_dt(year: int, month: int, day: int, hour: int, minute: int) -> datetime:
    return TIMEZONE.localize(datetime(year, month, day, hour, minute))


def _event_datetime(year: int, month: int, day: int, spec: Dict) -> Tuple[datetime, datetime]:
    start = _local_dt(year, month, day, *spec["start"])
    end = _local_dt(year, month, day, *spec["end"])
    return start, end


def _normalize_location(spec: Dict, text: str) -> Dict:
    if "location" in spec:
        return dict(spec["location"])
    if "By Zoom only" in text or "Zoom-only" in text:
        return {"name": "Online", "address": ""}
    if "On Discord only" in text:
        return {"name": "Online", "address": ""}
    return dict(DEFAULT_LOCATION)


def _build_event(year: int, month: int, day: int, spec: Dict, cell_text: str) -> Dict:
    start, end = _event_datetime(year, month, day, spec)
    if spec["key"] == "film" and ("Special earlier time" in cell_text or "Movie Afternoon" in cell_text):
        start = _local_dt(year, month, day, 14, 0)
        end = _local_dt(year, month, day, 17, 0)

    event = {
        "id": f"bsfs_{spec['key']}_{year}_{month:02d}_{day:02d}",
        "name": spec["name"],
        "description": spec["description"],
        "startDate": start.isoformat(),
        "endTime": end.isoformat(),
        "url": SOURCE_URL,
        "status": "ACTIVE",
        "location": _normalize_location(spec, cell_text),
        "imageUrl": DEFAULT_IMAGE,
        "orgName": "Baltimore Science Fiction Society",
        "orgImageUrl": DEFAULT_IMAGE,
        "tags": ["Culture", "Community", "Literature", "Gaming"],
        "source": SOURCE_URL,
        "source_url": SOURCE_URL,
        "source_group": "Baltimore Science Fiction Society",
        "recurring": bool(spec.get("recurrence")),
        "scrapeTime": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
    }
    if spec.get("recurrence"):
        event["recurrence"] = dict(spec["recurrence"])
    return event


def _build_special_event(year: int, month: int, day: int, spec: Dict) -> Dict:
    start = _local_dt(year, month, day, *spec["start"])
    end = _local_dt(year, month, day, *spec["end"])
    return {
        "id": f"bsfs_special_{year}_{month:02d}_{day:02d}_{re.sub(r'[^a-z0-9]+', '_', spec['name'].lower()).strip('_')}",
        "name": spec["name"],
        "description": spec["description"],
        "startDate": start.isoformat(),
        "endTime": end.isoformat(),
        "url": spec.get("url") or SOURCE_URL,
        "status": "ACTIVE",
        "location": dict(DEFAULT_LOCATION),
        "imageUrl": DEFAULT_IMAGE,
        "orgName": "Baltimore Science Fiction Society",
        "orgImageUrl": DEFAULT_IMAGE,
        "tags": ["Culture", "Community", "Literature"],
        "source": SOURCE_URL,
        "source_url": SOURCE_URL,
        "source_group": "Baltimore Science Fiction Society",
        "recurring": False,
        "scrapeTime": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
    }


def _iter_calendar_cells(soup: BeautifulSoup) -> Iterable[Tuple[int, int, int, str]]:
    for table in soup.select("table.month"):
        month_year = _month_title_for_table(table)
        if not month_year:
            continue
        month, year = month_year
        for cell in table.find_all("td"):
            day, text = _cell_day_and_text(cell)
            if not day or not text:
                continue
            yield year, month, day, text


def scrape_events(url: str = SOURCE_URL) -> List[Dict]:
    session = build_session()
    response = polite_get(session, url, timeout=30, allow_redirects=True)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    events: List[Dict] = []
    seen: set[str] = set()
    now = datetime.now(TIMEZONE)

    for year, month, day, cell_text in _iter_calendar_cells(soup):
        for spec in EVENT_PATTERNS:
            if spec["needle"] not in cell_text:
                continue
            event = _build_event(year, month, day, spec, cell_text)
            start = datetime.fromisoformat(event["startDate"])
            if start + timedelta(minutes=30) < now:
                continue
            if event["id"] not in seen:
                seen.add(event["id"])
                events.append(event)

        for spec in SPECIAL_EVENTS:
            if spec["needle"] not in cell_text:
                continue
            event = _build_special_event(year, month, day, spec)
            start = datetime.fromisoformat(event["startDate"])
            if start + timedelta(minutes=30) < now:
                continue
            if event["id"] not in seen:
                seen.add(event["id"])
                events.append(event)

    return sorted(events, key=lambda event: event["startDate"])


if __name__ == "__main__":
    import json

    print(json.dumps(scrape_events(), indent=2))
