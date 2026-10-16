import json
from unittest.mock import patch

import pytest

from baltimore.scrape_banner_events import parse_impact, parse_index
from baltimore.extra_event_sources import sources
from genCalendar import fetch_events_from_source


IMPACT_URL = "https://impactmaryland.thebaltimorebanner.com/"


def impact_html(year=2026):
    faq = f'The event will be held on October 14, {year} at The Talon at M&T Bank Stadium located at 1101 Russell St, Baltimore, MD 21230.'
    data = json.dumps([json.dumps([1, [4, "p", {}, [5, faq]]])])
    return f'''<meta property="og:description" content="Maryland ideas conference.">
        <h3>October 14, {year} BUY ONE, GET ONE.</h3>
        <h3>October 14, {year} BUY ONE, GET ONE.</h3>
        <h1>The leaders of today imagine the Maryland of tomorrow.</h1>
        <h3>8:00 a.m.</h3><h3>Registration and breakfast</h3>
        <h3>08:30 - 08:45 a.m.</h3>
        <h4>VIP reception will conclude at 7:30pm.</h4>
        <script id="__framer__handoverData">{data}</script>'''


def test_impact_uses_real_title_agenda_timezone_and_faq_venue():
    events = parse_impact(impact_html(), IMPACT_URL)
    assert len(events) == 1
    event = events[0]
    assert event["name"] == "Impact Maryland 2026"
    assert event["startDate"] == "2026-10-14T08:00:00-04:00"
    assert event["endTime"] == ""
    assert event["location"] == {"name": "The Talon at M&T Bank Stadium", "address": "1101 Russell St, Baltimore, MD 21230"}
    assert "Registration and breakfast" in event["description"]


def test_impact_follows_next_year_without_hardcoded_date():
    assert parse_impact(impact_html(2027), IMPACT_URL)[0]["startDate"].startswith("2027-10-14")


def test_impact_layout_failure_is_explicit():
    with pytest.raises(ValueError):
        parse_impact("<h1>Impact Maryland</h1>", IMPACT_URL)


def card(name, day, url="https://www.thebaltimorebannerevents.com/example"):
    return f'''<div class="article-section-body"><a class="main-headline" href="{url}">{name}</a>
        <div class="description">Event overview.</div>
        <span class="relative-timestamp__date">{day}</span></div>'''


def test_index_pairs_dates_with_their_own_card_and_skips_partial_dates():
    html = card("Kitchen Undisclosed", "Nov. 23, 2026")
    html += card("Kitchen Undisclosed", "Nov. 23, 2026")
    html += card("Unannounced summit", "October 2026")
    html += card("Inside the Legislative Session", "January 20, 2026", "https://www.thebaltimorebannerevents.com/legislative")
    html += card("Impact Maryland", "October 14, 2026", IMPACT_URL)
    events = parse_index(html, "https://www.thebanner.com/events/")
    assert [(e["name"], e["startDate"]) for e in events] == [
        ("Kitchen Undisclosed", "2026-11-23"), ("Inside the Legislative Session", "2026-01-20")]
    assert all("Time and venue are not specified" in e["description"] for e in events)


def test_banner_source_routes_through_dedicated_parser():
    source = next(s for s in sources if s["url"] == IMPACT_URL)
    with patch("baltimore.scrape_banner_events.scrape_events", return_value=parse_impact(impact_html(), IMPACT_URL)) as scrape:
        events, unmatched, errors = fetch_events_from_source(source, "baltimore")
    scrape.assert_called_once_with(IMPACT_URL)
    assert not errors and not unmatched
    assert events[0]["source_url"] == IMPACT_URL
    assert events[0]["tags"] == source["tags"]
