from unittest.mock import Mock, patch

import scrape_tribe


def test_normalizes_tribe_events_api_payload():
    api_url = "https://example.com/wp-json/tribe/events/v1/events?per_page=50"
    payload = {
        "events": [
            {
                "id": 8217,
                "title": "Community LEAD Conversation: From Audit to Action",
                "description": "<p>Every Baltimore family deserves a safe home.</p>",
                "utc_start_date": "2026-07-30 22:00:00",
                "utc_end_date": "2026-07-31 00:00:00",
                "url": "https://example.com/event/community-lead-conversation/",
                "image": {"url": "https://example.com/community-lead.png"},
                "venue": {
                    "venue": "Baltimore Unity Hall",
                    "address": "1505 Eutaw Place",
                    "city": "Baltimore",
                    "province": "Maryland",
                    "zip": "21217",
                },
            }
        ]
    }

    events = scrape_tribe._events_from_payload(payload, api_url)

    assert len(events) == 1
    event = events[0]
    assert event["name"] == "Community LEAD Conversation: From Audit to Action"
    assert event["startDate"] == "2026-07-30T22:00:00+00:00"
    assert event["endTime"] == "2026-07-31T00:00:00+00:00"
    assert event["location"]["name"] == "Baltimore Unity Hall"
    assert event["location"]["address"] == "1505 Eutaw Place, Baltimore, Maryland 21217"
    assert event["imageUrl"] == "https://example.com/community-lead.png"


def test_skips_tribe_events_without_a_valid_start():
    payload = {"events": [{"title": "Broken event", "utc_start_date": "not-a-date"}]}

    assert scrape_tribe._events_from_payload(payload, "https://example.com") == []


@patch("scrape_tribe.polite_get")
@patch("scrape_tribe.build_session")
def test_scrape_uses_transparent_user_agent_for_tribe_api(build_session, polite_get):
    session = Mock()
    response = Mock()
    response.json.return_value = {"events": []}
    build_session.return_value = session
    polite_get.return_value = response
    api_url = "https://example.com/wp-json/tribe/events/v1/events?per_page=50"

    assert scrape_tribe.scrape(api_url) == []

    build_session.assert_called_once_with(user_agent=scrape_tribe.USER_AGENT)
    polite_get.assert_called_once_with(
        session,
        api_url,
        timeout=30,
        allow_redirects=True,
    )
    response.raise_for_status.assert_called_once_with()
