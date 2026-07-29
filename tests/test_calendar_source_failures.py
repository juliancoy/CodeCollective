import unittest
from unittest.mock import Mock, patch

from genCalendar import collect_west_virginia_events, fetch_events_from_source


class CalendarSourceFailureTests(unittest.TestCase):
    @patch("genCalendar.scrape_ics.fetch_calendar_events")
    def test_ics_source_uses_feed_and_public_event_page(self, fetch_events):
        fetch_events.return_value = [
            {
                "name": "Community LEAD Conversation",
                "startDate": "2026-07-30T18:00:00-04:00",
            }
        ]
        source = {
            "name": "Young, Gifted & Green Events",
            "url": "https://www.younggiftedgreen.org/events/",
            "feed_url": "https://www.younggiftedgreen.org/events/?ical=1",
            "source_kind": "ics",
            "orgImageUrl": "https://www.younggiftedgreen.org/favicon.png",
            "tags": ["Environment", "Safety"],
        }

        events, unmatched, errors = fetch_events_from_source(source, "baltimore")

        fetch_events.assert_called_once_with(
            ICS_URL=source["feed_url"],
            city="baltimore",
            imageURL=source["orgImageUrl"],
            eventUrl=source["url"],
            recurring=True,
            preface="",
        )
        self.assertEqual(unmatched, [])
        self.assertEqual(errors, [])
        self.assertEqual(events[0]["source_url"], source["url"])
        self.assertEqual(events[0]["source_group"], source["name"])
        self.assertEqual(events[0]["tags"], source["tags"])

    @patch("genCalendar.scrape_ics.fetch_calendar_events", side_effect=RuntimeError("blocked"))
    def test_west_virginia_ics_failure_is_logged_without_aborting(self, _fetch_events):
        error_logger = Mock()

        events = collect_west_virginia_events(error_logger=error_logger)

        self.assertEqual(events, [])
        error_logger.assert_called_once()
        self.assertEqual(error_logger.call_args.args[0], "city_collect")
        self.assertIsInstance(error_logger.call_args.args[1], RuntimeError)
        self.assertEqual(
            error_logger.call_args.kwargs["scraper"],
            "scrape_ics.fetch_calendar_events",
        )


if __name__ == "__main__":
    unittest.main()
