from unittest.mock import Mock, patch

import scrape_gbci
from genCalendar import fetch_events_from_source


def test_gbci_scraper_keeps_summit_and_webinars_only():
    extracted = [
        {"name": "2026 Greater Baltimore Climate Summit", "startDate": "2026-11-12T13:00:00.000Z"},
        {
            "name": "Greater Baltimore Climate Summit Web Series: Community Roundtable Edition",
            "startDate": "2026-07-15T16:00:00.000Z",
            "location": {"name": "Webinar"},
        },
        {
            "name": "Building Greater Baltimore Momentum for Equitable Climate Solutions",
            "startDate": "2026-05-20T16:00:00.000Z",
            "location": {"name": "Webinar"},
        },
        {
            "name": "Data Centers 101",
            "startDate": "2026-06-03T23:00:00.000Z",
            "location": {"name": "Webinar"},
        },
        {
            "name": "CCTF Summer 2026 Internship Closing",
            "startDate": "2026-08-21T16:00:00.000Z",
        },
    ]

    with patch("scrape_gbci.build_session"), patch("scrape_gbci.polite_get") as get, patch(
        "scrape_gbci._extract_events_from_page",
        return_value=extracted,
    ):
        get.return_value = Mock(text="<html></html>", raise_for_status=Mock())
        events = scrape_gbci.scrape("https://www.thecctfoundation.org/event")

    assert [event["name"] for event in events] == [
        "2026 Greater Baltimore Climate Summit",
        "Greater Baltimore Climate Summit Web Series: Community Roundtable Edition",
        "Building Greater Baltimore Momentum for Equitable Climate Solutions",
        "Data Centers 101",
    ]


@patch("genCalendar.scrape_gbci.scrape")
def test_gbci_source_dispatch_adds_baltimore_metadata(scrape):
    scrape.return_value = [
        {
            "name": "Greater Baltimore Climate Summit Web Series",
            "startDate": "2026-08-19T16:00:00.000Z",
        }
    ]
    source = {
        "name": "Greater Baltimore Climate Initiative",
        "url": "https://www.thecctfoundation.org/event",
        "source_kind": "gbci_events",
        "tags": ["Environment", "Climate", "Energy"],
    }

    events, unmatched, errors = fetch_events_from_source(source, "baltimore")

    scrape.assert_called_once_with(source["url"])
    assert unmatched == []
    assert errors == []
    assert events[0]["source_group"] == "Greater Baltimore Climate Initiative"
    assert events[0]["source_url"] == source["url"]
    assert events[0]["tags"] == ["Environment", "Climate", "Energy"]
