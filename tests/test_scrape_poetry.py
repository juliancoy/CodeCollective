import json
from baltimore.scrape_poetry import parse_ticket_events, scrape_events


def page(start, end, next_session=None, city="Baltimore"):
    event = {"@type": "Event", "name": "Poetry", "startDate": start,
             "endDate": end, "location": {"name": "Venue", "address": city}}
    html = '<script type="application/ld+json">' + json.dumps(event) + '</script>'
    if next_session:
        html += '<script id="__NEXT_DATA__" type="application/json">' + json.dumps(
            {"props": {"highlights": {"nextAvailableSession": next_session}}}) + '</script>'
    return html


def test_local_time_and_date_only_end():
    for month, offset in [("10", "-04:00"), ("12", "-05:00")]:
        event = parse_ticket_events(page(f"2026-{month}-16T19:30:00", f"2026-{month}-16"), "https://example.com")[0]
        assert event["startDate"].endswith(offset)
        assert "endTime" not in event


def test_season_uses_next_explicit_session_without_inventing_end():
    html = page("2026-08-25T19:00:00-04:00", "2027-06-22T22:00:00-04:00", "2026-10-27T19:00:00-04")
    event = parse_ticket_events(html, "https://example.com")[0]
    assert event["startDate"] == "2026-10-27T19:00:00-04:00"
    assert "endTime" not in event
    assert parse_ticket_events(page("2026-08-25", "2027-06-22"), "https://example.com") == []


def test_preserves_real_end_and_excludes_other_cities():
    html = page("2026-11-11T19:00:00-05:00", "2026-11-11T22:00:00-05:00")
    assert parse_ticket_events(html, "https://example.com")[0]["endTime"] == "2026-11-11T22:00:00-05:00"
    assert not parse_ticket_events(page("2026-11-11", "", city="Boston"), "https://example.com")


def test_discovers_only_unique_eventbrite_event_links(monkeypatch):
    calls = []
    class Response:
        def __init__(self, text): self.text = text
        def raise_for_status(self): pass
    def get(session, url, **kwargs):
        calls.append(url)
        if url == "https://charmcityslam.com/":
            return Response('<a href="https://www.eventbrite.com/e/show-123?aff=x">Show</a>'
                            '<a href="https://www.eventbrite.com/e/show-123">Repeat</a>'
                            '<a href="https://eventbrite.com.evil.test/e/123">Other</a>')
        return Response(page("2026-11-11T19:00:00", "2026-11-11T22:00:00"))
    monkeypatch.setattr("baltimore.scrape_poetry.polite_get", get)
    assert len(scrape_events("https://charmcityslam.com/")) == 1
    assert calls == ["https://charmcityslam.com/", "https://www.eventbrite.com/e/show-123"]
