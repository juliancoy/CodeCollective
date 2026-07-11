from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from baltimore.scrape_blackthorn import _extract_events_from_payloads


def test_extract_events_filters_templates_and_normalizes_detail():
    future = (datetime.now(timezone.utc) + timedelta(days=10)).isoformat().replace("+00:00", "Z")
    past = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat().replace("+00:00", "Z")
    summaries = {
        "data": [
            {
                "id": "real1",
                "name": "Founder Meetup",
                "category": "Social/Networking",
                "startDateUTC": future,
                "endDateUTC": future,
                "venueName": "Towson StarTUp at the Armory",
                "venueGeocode": {"latitude": 39.3993212, "longitude": -76.6050048},
            },
            {
                "id": "template1",
                "name": "UpSurge Monthly (TEMPLATE)",
                "startDateUTC": future,
            },
            {
                "id": "past1",
                "name": "Past Meetup",
                "startDateUTC": past,
            },
        ]
    }
    details = {
        "real1": {
            "data": [
                {
                    "id": "real1",
                    "name": "Founder Meetup",
                    "description": "<p>Meet <strong>founders</strong>.</p>",
                    "startDateUTC": future,
                    "endDateUTC": future,
                    "category": "Social/Networking",
                    "imageUrl": "https://example.com/image.png",
                    "venue": {
                        "name": "Towson StarTUp at the Armory",
                        "street": "307 Washington Avenue",
                        "city": "Towson",
                        "state": "MD",
                        "zipcode": "21204",
                        "latitude": 39.3993212,
                        "longitude": -76.6050048,
                    },
                }
            ]
        }
    }

    events = _extract_events_from_payloads(summaries, details)

    assert len(events) == 1
    assert events[0]["name"] == "Founder Meetup"
    assert events[0]["description"] == "Meet founders."
    assert events[0]["url"].endswith("/real1")
    assert events[0]["location"]["name"] == "Towson StarTUp at the Armory"
    assert events[0]["location"]["address"] == "307 Washington Avenue, Towson, MD, 21204"
    assert events[0]["location"]["latitude"] == 39.3993212
    assert "Social/Networking" in events[0]["tags"]
