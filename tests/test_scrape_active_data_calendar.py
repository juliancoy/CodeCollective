import textwrap
from unittest.mock import Mock, patch

import scrape_active_data_calendar


SAMPLE_FEED = textwrap.dedent(
    """\
    <?xml version="1.0" encoding="utf-8"?>
    <rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/">
      <channel>
        <title>Environment Events Calendar for Maryland</title>
        <item>
          <title><![CDATA[Food Recovery: Strategies for Success, virtual (9/30/2026)]]></title>
          <link>https://www.doit.state.md.us/ActiveDataCalendar/EventList.aspx?view=EventDetails&amp;eventidn=123</link>
          <description><![CDATA[Short summary]]></description>
          <content:encoded><![CDATA[
            <table cellpadding="0" cellspacing="0" border="0">
              <tr>
                <td><b>Start Date:</b>&nbsp;</td><td>9/30/2026</td>
                <td>&nbsp;<b>Start Time:</b>&nbsp;</td><td>12:00 PM</td>
              </tr>
              <tr>
                <td><b>End Date:</b>&nbsp;</td><td>9/30/2026</td>
                <td>&nbsp;<b>End Time:</b>&nbsp;</td><td>1:00 PM</td>
              </tr>
              <tr>
                <td><b>Location:</b>&nbsp;</td><td>Virtual</td>
              </tr>
            </table>
            Learn how Maryland food recovery programs are scaling.
          ]]></content:encoded>
        </item>
      </channel>
    </rss>
    """
)


def test_parse_feed_extracts_calendar_event_fields():
    source_url = "https://www.doit.state.md.us/ActiveDataCalendar/RSSSyndicator.aspx?category=76-0"

    events = scrape_active_data_calendar._parse_feed(SAMPLE_FEED, source_url)

    assert len(events) == 1
    event = events[0]
    assert event["name"] == "Food Recovery: Strategies for Success, virtual"
    assert event["startDate"] == "2026-09-30T12:00:00-04:00"
    assert event["endTime"] == "2026-09-30T13:00:00-04:00"
    assert event["url"] == "https://www.doit.state.md.us/ActiveDataCalendar/EventList.aspx?view=EventDetails&eventidn=123"
    assert event["location"]["name"] == "Virtual"
    assert "Maryland food recovery programs" in event["description"]


@patch("scrape_active_data_calendar.polite_get")
@patch("scrape_active_data_calendar.build_session")
def test_scrape_uses_transparent_user_agent(build_session, polite_get):
    session = Mock()
    response = Mock(text=SAMPLE_FEED)
    response.raise_for_status.return_value = None
    build_session.return_value = session
    polite_get.return_value = response

    events = scrape_active_data_calendar.scrape("https://example.com/feed")

    assert len(events) == 1
    build_session.assert_called_once_with(user_agent=scrape_active_data_calendar.USER_AGENT)
