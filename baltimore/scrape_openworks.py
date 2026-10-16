"""Read the public Mindbody enrollment widget embedded on Open Works' schedule."""

from datetime import datetime, timedelta
import re
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

from http_client import build_session, polite_get


SCHEDULE_URL = "https://www.openworksbmore.org/schedule/"
# Official desktop widget; the second widget on the page duplicates it for mobile.
FEED_URL = "https://widgets.mindbodyonline.com/widgets/enrollments/d678669584b/print"
TIMEZONE = ZoneInfo("America/New_York")


def parse_events(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    rows = soup.select("tr[data-hc-mbo-class-id]")
    if not rows:
        # A changed layout or an error page must not silently look like success.
        raise ValueError("Open Works Mindbody enrollment table was not found")

    events = []
    seen = set()
    for row in rows:
        def text(selector):
            element = row.select_one(selector)
            return element.get_text(" ", strip=True) if element else ""

        name = text(".mbo_class")
        dates = text(".healcode-date-field")
        times = text(".healcode-time-field")
        date_parts = re.split(r"\s+-\s+", dates)
        time_parts = re.split(r"\s+-\s+", times)
        if not name or len(time_parts) != 2:
            raise ValueError(f"Incomplete Open Works enrollment: {name!r}, {dates!r}, {times!r}")
        first_day = datetime.strptime(date_parts[0], "%b %d %Y").date()
        start = datetime.combine(first_day, datetime.strptime(time_parts[0], "%I:%M %p").time(), TIMEZONE)
        end = datetime.combine(first_day, datetime.strptime(time_parts[1], "%I:%M %p").time(), TIMEZONE)
        if end <= start:
            end += timedelta(days=1)
        key = (row["data-hc-mbo-class-id"], start.isoformat())
        if key in seen:
            continue
        seen.add(key)

        description = [f"Open Works class. Schedule: {dates}; {text('.healcode-days-field')}; {times}."]
        if len(date_parts) > 1:
            description.append("Multi-session course: this listing marks the first session. Check registration for all session dates and exceptions.")
        instructor = text(".trainer")
        if instructor:
            description.append(f"Instructor: {instructor}.")
        # Missing signup buttons indicate full courses, not cancellations.
        if not row.select_one(".signup_now"):
            description.append("No signup button is currently available; the course may be full or already underway.")
        description.append("Confirm the venue and registration details on the class page.")
        class_link = row.select_one(".mbo_class a[data-url]")
        events.append({
            "name": name,
            "description": " ".join(description),
            "startDate": start.isoformat(),
            "endTime": end.isoformat(),
            "url": class_link["data-url"] if class_link else SCHEDULE_URL,
            "status": "ACTIVE",
            # Some offerings are explicitly offsite (e.g. Village Learning Place).
            # Do not assign Open Works' street address to every class.
            "location": {"name": name.split("@", 1)[1].strip() if "@" in name else "Open Works", "address": ""},
            "source": SCHEDULE_URL,
        })
    return events


def scrape_events(feed_url: str = FEED_URL) -> list[dict]:
    response = polite_get(build_session(), feed_url, timeout=30)
    response.raise_for_status()
    return parse_events(response.text)
