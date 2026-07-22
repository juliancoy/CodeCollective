import unittest
from unittest.mock import Mock, patch

from genCalendar import collect_west_virginia_events


class CalendarSourceFailureTests(unittest.TestCase):
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
