import unittest

from baltimore.scrape_sjbc import _parse_events_payload


class SjbcScraperTests(unittest.TestCase):
    def test_parses_long_event_as_single_event_with_end_time(self):
        payload = {
            "json": [
                {
                    "ID": 13523,
                    "event_id": 13523,
                    "event_start_unix": 1782720000,
                    "event_end_unix": 1786719600,
                    "event_title": "Summer STEM Camp",
                    "event_pmv": {
                        "_start_hour": ["8"],
                        "_start_minute": ["00"],
                        "_start_ampm": ["am"],
                        "_end_hour": ["3"],
                        "_end_minute": ["00"],
                        "_end_ampm": ["pm"],
                        "evcal_repeat": ["no"],
                        "evcal_exlink": ["https://sjbc.org/Concerts/summer-stem-camp/"],
                        "evcal_lmlink": ["https://www.eventbrite.com/e/summer-stem-camp-tickets-1987523894471"],
                    },
                }
            ],
            "html": """
                <div class="eventon_list_event" data-event_id="13523">
                  <div class="evo_event_schema" style="display:none">
                    <script type="application/ld+json">
                    {
                      "@context": "http://schema.org",
                      "@type": "Event",
                      "@id": "event_13523_0",
                      "name": "Summer STEM Camp",
                      "url": "https://sjbc.org/Concerts/summer-stem-camp/",
                      "image": "https://sjbc.org/wp-content/uploads/2026/06/STEM_EventBrite.webp",
                      "description": "<div>A fun, hands-on STEM camp for K-7 students.</div>"
                    }
                    </script>
                  </div>
                  <span class="event_location_attrs"
                    data-location_name="St John Baptist Church"
                    data-location_address="9055 Tamar Dr"></span>
                </div>
            """,
        }

        events = _parse_events_payload(payload)

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["name"], "Summer STEM Camp")
        self.assertEqual(events[0]["startDate"], "2026-06-29T08:00:00-04:00")
        self.assertEqual(events[0]["endTime"], "2026-08-14T15:00:00-04:00")
        self.assertFalse(events[0]["recurring"])
        self.assertEqual(events[0]["location"]["address"], "9055 Tamar Dr")
        self.assertEqual(
            events[0]["registrationUrl"],
            "https://www.eventbrite.com/e/summer-stem-camp-tickets-1987523894471",
        )


if __name__ == "__main__":
    unittest.main()
