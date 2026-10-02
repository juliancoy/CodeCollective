from genCalendar import _route_multicity_events_to_city
from dc.event_sources import sources as dc_sources
from multicity.event_sources import sources as multicity_sources


def test_bill_calendar_is_collected_once_through_multicity():
    url = "https://luma.com/bill"
    assert not any(s["url"] == url for s in dc_sources)
    assert sum(s["url"] == url for s in multicity_sources) == 1


def test_routes_by_event_location_instead_of_calendar_location():
    events = [
        {"name": "DC gathering", "location": {"city": "Washington", "state": "DC"}},
        {"name": "Baltimore gathering", "location": {"city": "Baltimore", "state": "MD"}},
        {"name": "Biotech gathering", "location": {"address": "135 Mississippi St, San Francisco, CA 94107, USA"}},
        {"name": "CryptoMondays Zoom USA", "location": {"name": "https://us02web.zoom.us/j/123"}},
        {"name": "[VIRTUAL] Information Session", "location": {}},
        {"name": "Unannounced gathering", "location": {}},
    ]
    assert [e["name"] for e in _route_multicity_events_to_city(events, "dc")] == ["DC gathering"]
    assert [e["name"] for e in _route_multicity_events_to_city(events, "baltimore")] == ["Baltimore gathering"]
    assert [e["name"] for e in _route_multicity_events_to_city(events, "virtual")] == [
        "CryptoMondays Zoom USA", "[VIRTUAL] Information Session",
    ]
    assert all("city" not in e for e in events)
