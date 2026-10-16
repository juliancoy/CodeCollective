import unittest
from unittest.mock import patch

from baltimore.scrape_openworks import parse_events
from baltimore.event_sources import sources
from genCalendar import fetch_events_from_source


def enrollment(name="Wood 1", dates="Oct 15 2026", times="6:00 PM - 9:00 PM", signup=True):
    return f'''<table><tr data-hc-mbo-class-id="5019">
      <td class="healcode-date-field">{dates}</td>
      <td class="healcode-time-field">{times}</td>
      <td class="healcode-days-field">Thu</td>
      <td class="mbo_class"><a data-url="https://widgets.mindbodyonline.com/class_description?id=1">{name}</a></td>
      <td class="trainer">Education Staff</td>
      <td>{'<a class="signup_now">Sign Up</a>' if signup else ''}</td>
    </tr></table>'''


class OpenWorksTests(unittest.TestCase):
    def test_local_time_and_daylight_saving(self):
        event = parse_events(enrollment())[0]
        self.assertEqual(event["startDate"], "2026-10-15T18:00:00-04:00")
        self.assertEqual(event["endTime"], "2026-10-15T21:00:00-04:00")
        winter = parse_events(enrollment(dates="Nov 12 2026"))[0]
        self.assertEqual(winter["startDate"], "2026-11-12T18:00:00-05:00")

    def test_multi_session_course_does_not_become_continuous_event(self):
        events = parse_events(enrollment(dates="Oct 15 2026 - Nov 12 2026", signup=False))
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["endTime"], "2026-10-15T21:00:00-04:00")
        self.assertIn("Nov 12 2026", events[0]["description"])
        self.assertIn("first session", events[0]["description"])
        self.assertIn("may be full", events[0]["description"])
        self.assertEqual(events[0]["status"], "ACTIVE")

    def test_offsite_venue_and_duplicate_rows(self):
        html = enrollment(name="3D Printing @ Village Learning Place")
        events = parse_events(html + html)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["location"], {"name": "Village Learning Place", "address": ""})

    def test_layout_failure_is_not_empty_success(self):
        with self.assertRaises(ValueError):
            parse_events("<html>Service unavailable</html>")

    def test_source_dispatch_preserves_public_identity(self):
        cases = [
            ("Open Works Class and Workshop Schedule", "baltimore.scrape_openworks.scrape_events"),
            ("4MLK Events", "genCalendar.scrape_luma_orgpage.fetch_and_parse_luma_events"),
        ]
        for name, target in cases:
            with self.subTest(name=name):
                source = next(s for s in sources if s["name"] == name)
                with patch(target, return_value=[{"name": "Class", "startDate": "2026-10-15T18:00:00-04:00"}]) as scrape:
                    events, unmatched, errors = fetch_events_from_source(source, "baltimore")
                scrape.assert_called_once_with(source["feed_url"])
                self.assertEqual(unmatched, [])
                self.assertEqual(errors, [])
                self.assertEqual(events[0]["source_url"], source["url"])


if __name__ == "__main__":
    unittest.main()
