import json
import sys
from pathlib import Path

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import scrape_web_events


def test_extracts_wix_events_from_warmup_data():
    source_url = "https://www.blyssbaltimore.com/upcoming"
    payload = {
        "appsWarmupData": {
            "app": {
                "widget": {
                    "events": {
                        "events": [
                            {
                                "id": "event-1",
                                "title": "Park Social",
                                "description": "Come outside and play.",
                                "slug": "park-social-1",
                                "scheduling": {
                                    "config": {
                                        "startDate": "2026-06-27T21:00:00.000Z",
                                        "endDate": "2026-06-28T00:00:00.000Z",
                                    }
                                },
                                "location": {
                                    "name": "Latrobe Park",
                                    "address": "1627 E Fort Ave, Baltimore, MD 21230, USA",
                                    "fullAddress": {
                                        "city": "Baltimore",
                                        "subdivision": "MD",
                                        "postalCode": "21230",
                                        "country": "US",
                                        "geocode": {
                                            "latitude": 39.2669523,
                                            "longitude": -76.5933429,
                                        },
                                    },
                                },
                                "mainImage": {
                                    "url": "https://static.wixstatic.com/media/example.png"
                                },
                            }
                        ]
                    }
                }
            }
        }
    }
    html = (
        '<script type="application/json" id="wix-warmup-data">'
        f"{json.dumps(payload)}"
        "</script>"
    )

    soup = BeautifulSoup(html, "html.parser")
    events = scrape_web_events._extract_events_from_page(soup, source_url)

    assert len(events) == 1
    assert events[0]["name"] == "Park Social"
    assert events[0]["startDate"] == "2026-06-27T21:00:00.000Z"
    assert events[0]["endTime"] == "2026-06-28T00:00:00.000Z"
    assert events[0]["url"] == "https://www.blyssbaltimore.com/event-details/park-social-1"
    assert events[0]["location"]["name"] == "Latrobe Park"
    assert events[0]["location"]["city"] == "Baltimore"
    assert events[0]["imageUrl"] == "https://static.wixstatic.com/media/example.png"


def test_dated_text_does_not_turn_separators_or_buttons_into_events():
    html = """
    <div>October 31, 2026</div><span>|</span><span>10:00 am</span>
    <h1>ZooBOO! Presented by Fulton Bank</h1>
    <h2>LUNG FORCE Walk - New York</h2><div>May 15, 2027</div>
    <a>View Details</a>
    <h2>LUNG FORCE Walk - San Diego</h2><div>May 23, 2027</div>
    <a>View Details</a>
    """
    events = scrape_web_events._extract_events_from_page(
        BeautifulSoup(html, "html.parser"), "https://example.org/events"
    )
    assert all(event["name"] not in {"|", "View Details", "10:00 am"} for event in events)
    assert not any(event["startDate"].startswith("2026-10-31") for event in events)


def test_text_fallback_does_not_cross_into_next_dated_entry():
    soup = BeautifulSoup(
        "<p>May 15, 2027</p><a>View Details</a>"
        "<p>May 23, 2027</p><h2>Community Workshop</h2>",
        "html.parser",
    )
    events = scrape_web_events._extract_simple_dated_events(soup, "https://example.org")
    assert [(event["name"], event["startDate"]) for event in events] == [
        ("Community Workshop", "2027-05-23T00:00:00")
    ]


def test_structured_events_prevent_spurious_text_fallback_duplicates():
    payload = {"@type": "Event", "name": "Community Workshop", "startDate": "2027-05-23T10:00:00-04:00"}
    soup = BeautifulSoup(
        f'<script type="application/ld+json">{json.dumps(payload)}</script>'
        '<p>May 23, 2027</p><h2>Community Workshop</h2>',
        "html.parser",
    )
    events = scrape_web_events._extract_events_from_page(soup, "https://example.org")
    assert len(events) == 1
    assert events[0]["startDate"] == payload["startDate"]
