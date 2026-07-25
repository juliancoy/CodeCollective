import json
import sys
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import scrape_timely


def test_extracts_calendar_id_from_timely_metadata():
    data_info = quote(json.dumps({"id": 54748668, "title": "CA Events Calendar"}))
    page = f'<timely-calendar data-info="{data_info}"></timely-calendar>'

    assert scrape_timely._extract_calendar_id(page) == 54748668


def test_normalizes_grouped_timely_events():
    payload = {
        "data": {
            "items": {
                "2026-07-26": [
                    {
                        "id": 123,
                        "uid": "event-123",
                        "title": "Columbia Ice Rink Open House",
                        "description_short": "Free family fun.",
                        "start_utc_datetime": "2026-07-26 14:00:00",
                        "end_utc_datetime": "2026-07-26 18:00:00",
                        "event_status": "confirmed",
                        "canonical_url": "https://events.timely.fun/example/event/123",
                        "images": [
                            {
                                "full": {
                                    "url": "https://images.example/open-house.png"
                                }
                            }
                        ],
                        "taxonomies": {
                            "taxonomy_venue": [
                                {
                                    "title": "Columbia Ice Rink",
                                    "address": "5876 Thunder Hill Road",
                                    "city": "Columbia",
                                    "country_first_division": "Maryland",
                                    "postal_code": "21045",
                                    "country": "United States",
                                    "geo_location": "39.214,-76.846",
                                }
                            ]
                        },
                    }
                ]
            }
        }
    }

    events = scrape_timely._events_from_payload(
        payload, "https://events.timely.fun/example/month"
    )

    assert len(events) == 1
    event = events[0]
    assert event["name"] == "Columbia Ice Rink Open House"
    assert event["startDate"] == "2026-07-26T14:00:00+00:00"
    assert event["endTime"] == "2026-07-26T18:00:00+00:00"
    assert event["status"] == "ACTIVE"
    assert event["location"]["name"] == "Columbia Ice Rink"
    assert event["location"]["city"] == "Columbia"
    assert event["location"]["latitude"] == 39.214
    assert event["imageUrl"] == "https://images.example/open-house.png"


def test_skips_timely_events_without_a_valid_start():
    payload = {
        "data": {
            "items": {
                "unknown": [
                    {
                        "title": "Broken event",
                        "start_utc_datetime": "not-a-date",
                    }
                ]
            }
        }
    }

    assert scrape_timely._events_from_payload(payload, "https://example.com") == []
