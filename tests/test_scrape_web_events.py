import json
import sys
from pathlib import Path

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import scrape_web_events


def test_parses_timezone_aware_ics_event():
    payload = b'BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\nSUMMARY:Park walk\r\nDTSTART:20991010T140000Z\r\nDTEND:20991010T150000Z\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n'
    events = scrape_web_events._parse_ics_events(payload, 'https://example.org/calendar')
    assert len(events) == 1
    assert events[0]['startDate'] == '2099-10-10T14:00:00+00:00'


def test_parses_wild_apricot_event_in_park_timezone():
    soup = BeautifulSoup('''
        <h1 class="SystemPageTitle">Park walk</h1>
        <li class="eventInfoStartDate"><div class="eventInfoBoxValue">11 Oct 2026</div></li>
        <li class="eventInfoStartTime"><div client-tz-item="America/New_York">11:00 AM - 3:00 PM</div></li>
        <li class="eventInfoLocation"><div class="eventInfoBoxValue">1920 Eagle Dr</div></li>
    ''', 'html.parser')
    events = scrape_web_events._extract_events_from_page(soup, 'https://example.org/event-1')
    assert len(events) == 1
    assert events[0]['startDate'] == '2026-10-11T11:00:00-04:00'
    assert events[0]['endTime'] == '2026-10-11T15:00:00-04:00'
    assert events[0]['location']['address'] == '1920 Eagle Dr'


def test_discovers_tockify_feed_from_embedded_calendar():
    soup = BeautifulSoup(
        '<div data-tockify-calendar="pattersonpark"></div>'
        '<div data-tockify-calendar="pattersonpark"></div>'
        '<div data-tockify-calendar="../invalid"></div>',
        'html.parser',
    )
    _, feeds = scrape_web_events._extract_candidate_links(
        soup, 'https://pattersonpark.com/parkcalendar'
    )
    assert feeds == ['https://tockify.com/api/feeds/ics/pattersonpark']


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


def test_nava_utc_range_and_baltimore_scope():
    html = '''<meta property="og:title" content="Open Source Summit: AI Futures | Nava">
    <p>Event Date</p><p>October 14, 2026 at 3:30–11:30 PM UTC</p>
    <p>Location</p><div>Baltimore Museum of Art</div>'''
    events = scrape_web_events._extract_events_from_page(
        BeautifulSoup(html, 'html.parser'), 'https://www.navapbc.com/events/summit')
    assert len(events) == 1
    assert events[0]['startDate'] == '2026-10-14T15:30:00+00:00'
    assert events[0]['endTime'] == '2026-10-14T23:30:00+00:00'
    assert events[0]['name'] == 'Open Source Summit: AI Futures'
    assert scrape_web_events._extract_nava_event(
        BeautifulSoup(html.replace('Baltimore Museum of Art', 'New York'), 'html.parser'),
        'https://www.navapbc.com/events/summit') == []
    assert scrape_web_events._extract_nava_event(
        BeautifulSoup(html.replace('October 14, 2026', 'TBD'), 'html.parser'),
        'https://www.navapbc.com/events/summit') == []


def test_hub_microdata_preserves_explicit_timezone():
    soup = BeautifulSoup('''<article itemscope itemtype="https://schema.org/Event">
    <h1 itemprop="name">AI symposium</h1>
    <meta itemprop="startDate" content="2026-10-27T09:00:00-04:00">
    <meta itemprop="endDate" content="2026-10-27T20:00:00-04:00">
    <div itemprop="location">Bloomberg Student Center</div></article>''', 'html.parser')
    events = scrape_web_events._extract_events_from_page(soup, 'https://hub.jhu.edu/events/example/')
    assert len(events) == 1
    assert events[0]['startDate'] == '2026-10-27T09:00:00-04:00'
    assert events[0]['endTime'] == '2026-10-27T20:00:00-04:00'


def test_location_filter_excludes_other_cities(monkeypatch):
    class Response:
        text = '<script type="application/ld+json">'+json.dumps([
            {'@type':'Event','name':'Local','startDate':'2026-11-12T08:00:00-05:00','location':'Baltimore'},
            {'@type':'Event','name':'Elsewhere','startDate':'2026-11-12T08:00:00-05:00','location':'Washington, DC'},
        ])+'</script>'
        def raise_for_status(self):
            pass
    monkeypatch.setattr(scrape_web_events, 'polite_get', lambda *a, **k: Response())
    events = scrape_web_events.parse_web_events_page('https://example.org', location_pattern='Baltimore')
    assert [e['name'] for e in events] == ['Local']
    assert scrape_web_events.parse_web_events_page(
        'https://example.org', location_pattern='Baltimore', title_pattern='Cybersecurity'
    ) == []
