import json
import unittest
from datetime import datetime, timezone
from unittest.mock import Mock, patch

import scrape_startdmv
from genCalendar import apply_source_metadata, duplicate_match_score, infer_source_kind


def page(**changes):
    event = {
        "@type": "Event", "name": "Founder meetup",
        "startDate": "2026-11-03T09:00", "endDate": "2026-11-03T17:00",
        "organizer": {"name": "Actual organizer"},
        "offers": {"url": "https://www.meetup.com/founders/events/123/", "price": 0,
                   "availability": "https://schema.org/SoldOut"},
    }
    event.update(changes)
    return '<script type="application/ld+json">' + json.dumps(event) + '</script>'


class StartDMVTests(unittest.TestCase):
    def test_metadata_timezone_and_duplicate_identity(self):
        event = scrape_startdmv.parse_event_page(page(), "https://startdmv.org/event/test")[0]
        apply_source_metadata([event], {"url": "https://startdmv.org/events", "group_name": "StartDMV"})
        self.assertEqual(event["org_name"], "Actual organizer")
        self.assertEqual(event["source"], "https://startdmv.org/event/test")
        self.assertEqual(event["startDate"], "2026-11-03T09:00:00-05:00")
        self.assertEqual(event["endTime"], "2026-11-03T17:00:00-05:00")
        self.assertEqual(event["offers"][0]["price"], 0)
        self.assertTrue(event["offers"][0]["availability"].endswith("SoldOut"))
        self.assertIsNotNone(duplicate_match_score(event, dict(event, source="meetup")))
        self.assertEqual(infer_source_kind("https://startdmv.org/events"), "startdmv")

    def test_virtual_keeps_eastern_timezone_and_unknown_price(self):
        event = scrape_startdmv.parse_event_page(page(
            startDate="2026-10-31T19:00", offers={},
            eventAttendanceMode="https://schema.org/OnlineEventAttendanceMode",
        ), "https://startdmv.org/event/test")[0]
        self.assertEqual(event["startDate"], "2026-10-31T19:00:00-04:00")
        self.assertEqual(event["location"]["name"], "Online")
        self.assertNotIn("price", event)

    @patch("scrape_startdmv.polite_get")
    def test_sitemap_discovery_ignores_other_pages_and_past_events(self, get):
        urls = ["https://startdmv.org/event/old", "https://startdmv.org/directory/foo",
                "https://other.org/event/foo", "https://startdmv.org/event/new",
                "https://startdmv.org/event/new"]
        sitemap = '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + ''.join(
            '<url><loc>' + url + '</loc></url>' for url in urls) + '</urlset>'
        get.side_effect = [Mock(content=sitemap.encode()),
                           Mock(text=page(startDate="2024-11-03T09:00")), Mock(text=page())]
        events = scrape_startdmv.scrape(now=datetime(2026, 10, 31, tzinfo=timezone.utc))
        self.assertEqual(len(events), 1)
        self.assertEqual(get.call_count, 3)

    @patch("scrape_startdmv.polite_get", side_effect=PermissionError("blocked"))
    def test_fetch_errors_propagate(self, get):
        with self.assertRaises(PermissionError):
            scrape_startdmv.scrape()


if __name__ == "__main__":
    unittest.main()
