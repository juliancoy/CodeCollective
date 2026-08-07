from unittest.mock import Mock, patch

import scrape_biotrac


CALENDAR_HTML = """
<table>
  <tr><th>ONSITE Workshop Title</th><th>Start</th><th>Span</th><th>Cost</th></tr>
  <tr>
    <td><a href="/rna_seq/">RNA-Seq: Principles, Methods &amp; Computational Analysis</a></td>
    <td>08/4/26</td><td>4 day</td><td>$995</td>
  </tr>
  <tr>
    <td>Spectral Flow Cytometry - NEW OFFERING</td>
    <td>10/21/26</td><td>2 day</td><td>$695</td>
  </tr>
</table>
"""

DETAIL_HTML = """
<h4>9:30am-5:15pm</h4>
<blockquote>
  This workshop combines lectures with hands-on computational laboratory experience.
</blockquote>
"""


def test_calendar_rows_control_dates_and_detail_pages_enrich_events():
    source_url = "https://biotrac.com/calendar/"
    detail_url = "https://biotrac.com/rna_seq/"
    details = {detail_url: scrape_biotrac._extract_detail(DETAIL_HTML)}

    events = scrape_biotrac._events_from_calendar_html(CALENDAR_HTML, source_url, details)

    assert len(events) == 2
    event = events[0]
    assert event["name"] == "RNA-Seq: Principles, Methods & Computational Analysis"
    assert event["startDate"] == "2026-08-04T09:30:00-04:00"
    assert event["endTime"] == "2026-08-07T17:15:00-04:00"
    assert event["url"] == detail_url
    assert "hands-on computational laboratory experience" in event["description"]
    assert "registration fee $995" in event["description"]
    assert event["location"]["address"] == "20200 Observation Drive, Germantown, MD 20876"

    unlinked = events[1]
    assert unlinked["url"] == source_url
    assert unlinked["startDate"] == "2026-10-21T09:00:00-04:00"
    assert unlinked["endTime"] == "2026-10-22T17:00:00-04:00"


@patch("scrape_biotrac.polite_get")
@patch("scrape_biotrac.build_session")
def test_scrape_falls_back_to_calendar_data_when_detail_fetch_fails(build_session, polite_get):
    session = Mock()
    calendar_response = Mock(text=CALENDAR_HTML)
    calendar_response.raise_for_status.return_value = None
    failed_detail_response = Mock()
    failed_detail_response.raise_for_status.side_effect = RuntimeError("detail unavailable")
    build_session.return_value = session
    polite_get.side_effect = [calendar_response, failed_detail_response]

    events = scrape_biotrac.scrape("https://biotrac.com/calendar/")

    assert len(events) == 2
    assert events[0]["description"] == "4-day Bio-Trac training workshop; registration fee $995."
    build_session.assert_called_once_with(user_agent=scrape_biotrac.USER_AGENT)
