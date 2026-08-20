"""Supplemental Baltimore event sources discovered outside the core source list.

Keep these broad institutional/venue calendars separate from hand-curated
community sources in event_sources.py.  They are parsed through the generic
web-events scraper and deduplicated against all other sources downstream.
"""

sources = [
    {
        "name": "Visit Baltimore Events",
        "url": "https://baltimore.org/events/",
        "source_kind": "web_events_page",
        "tags": ["Community", "Culture", "Business"],
    },
    {
        "name": "Baltimore Convention Center Events",
        "url": "https://www.bccenter.org/events",
        "source_kind": "web_events_page",
        "tags": ["Business", "Community", "Professional Networking"],
    },
    {
        "name": "University of Maryland Medical Center Public Events",
        "url": "https://www.trumba.com/events-calendar/eastern-time/ummc",
        "source_kind": "web_events_page",
        "tags": ["Health", "Education"],
    },
    {
        "name": "Johns Hopkins Carey Business School Baltimore Events",
        "url": "https://carey.jhu.edu/events?location=Baltimore%2C+MD",
        "source_kind": "web_events_page",
        "tags": ["Business", "Professional Networking"],
    },
]
