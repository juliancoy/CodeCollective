from dc.scrape_empowerdc import parse_events
from genCalendar import fetch_events_from_source


def test_event_cards_keep_rsvp_location_and_dst_offsets():
    html = """
    <div class="card-event">
      <h4>Ivy City Community Day</h4>
      <div class="py-1">Saturday 10 Oct 2026 at 02:00 PM</div>
      <div class="py-1"><p>Trinity Baptist Church in Washington, DC</p></div>
      <a href="/ivy_city_community_day_2026">RSVP</a>
    </div>
    <div class="card-event">
      <h4>Winter meeting</h4>
      <div class="py-1">Tuesday 10 Nov 2026 at 06:00 PM</div>
      <a href="/winter">RSVP</a>
    </div>
    <div class="card-event"><h4>Undated</h4><a href="/undated">RSVP</a></div>
    """
    events = parse_events(html)
    assert len(events) == 2
    assert events[0]["startDate"] == "2026-10-10T14:00:00-04:00"
    assert events[1]["startDate"] == "2026-11-10T18:00:00-05:00"
    assert events[0]["url"] == "https://www.empowerdc.org/ivy_city_community_day_2026"
    assert events[0]["location"]["name"] == "Trinity Baptist Church in Washington, DC"


def test_source_dispatch_attaches_calendar_metadata(monkeypatch):
    monkeypatch.setattr("genCalendar.scrape_empowerdc.scrape", lambda url: [{
        "name": "Community Day", "startDate": "2026-10-10T14:00:00-04:00",
    }])
    source = {
        "url": "https://www.empowerdc.org/events",
        "group_name": "Empower DC",
        "source_kind": "empowerdc_events",
        "tags": ["Shelter", "Community Organizing"],
    }
    events, unmatched, errors = fetch_events_from_source(source, "dc")
    assert not unmatched and not errors
    assert events[0]["source_group"] == "Empower DC"
    assert events[0]["source_url"] == source["url"]
    assert events[0]["tags"] == source["tags"]
