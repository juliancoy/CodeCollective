"""Supplemental Baltimore event sources discovered outside the core source list.

Keep these broad institutional/venue calendars separate from hand-curated
community sources in event_sources.py. They are parsed through the generic
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
    {
        "name": "Morgan TechFest 2026",
        "url": "https://www.morgantechfest.com/",
        "source_kind": "web_events_page",
        "tags": ["Technology", "AI", "Business", "Tech Community"],
    },
    {
        "name": "2026 Data and Analytics Summit",
        "url": "https://achievingthedream.org/event/2026-data-and-analytics-summit/",
        "source_kind": "web_events_page",
        "tags": ["Data Science", "AI", "Education", "Economic Development"],
    },
    {
        "name": "AASHE 2026 Conference and Expo",
        "url": "https://www.aashe.org/conference/",
        "source_kind": "web_events_page",
        "tags": ["Environment", "Climate", "Energy", "Education"],
    },
    {
        "name": "Security Standardisation Research Conference 2026",
        "url": "https://ssresearch26.umbc.edu/",
        "source_kind": "web_events_page",
        "tags": ["Technology", "Cybersecurity", "AI", "Education"],
    },
    {
        "name": "2026 Annual Carey Finance Conference",
        "url": "https://carey.jhu.edu/events/2026-annual-carey-finance-conference",
        "source_kind": "web_events_page",
        "tags": ["Finance", "Business", "Education", "Professional Networking"],
    },
    {
        "name": "2026 Hopkins International Therapeutic Endoscopy Course",
        "url": "https://www.hitec-course.com/",
        "source_kind": "web_events_page",
        "tags": ["Health", "Education", "Science"],
    },
    {
        "name": "Johns Hopkins HCM Patient Symposium 2026",
        "url": "https://www.hopkinsmedicine.org/heart-vascular-institute/cardiology/hypertrophic-cardiomyopathy-hcm/hcm-patient-symposium",
        "source_kind": "web_events_page",
        "tags": ["Health", "Education", "Science"],
    },
    {
        "name": "COMPASS Conference 2026",
        "url": "https://compassinstitute4dei.com/events/EventDetails.aspx?id=2064586",
        "source_kind": "web_events_page",
        "tags": ["Business", "Economic Development", "Professional Networking"],
    },
]
