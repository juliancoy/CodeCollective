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
