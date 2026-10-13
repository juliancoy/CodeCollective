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
    {
        "name": "Baltimore Development Corporation Events",
        "url": "https://baltimoredevelopment.com/events/",
        "source_kind": "bdc_events",
        "tags": ["Business", "Economic Development", "Professional Networking"],
    },
    {
        "name": "Baltimore Science Fiction Society",
        "url": "https://www.bsfs.org/bsfscldr.htm",
        "source_kind": "bsfs_events",
        "tags": ["Culture", "Community", "Literature", "Gaming"],
    },
]

# October 2026 web-search coverage audit; retain detail URLs absent from indexes.
sources.extend([{'name': 'Nava Baltimore civic technology events',
  'url': 'https://www.navapbc.com/events',
  'location_pattern': 'Baltimore',
  'source_kind': 'web_events_page',
  'tags': ['Technology', 'Tech Community']},
 {'name': 'Nava Open Source Summit: AI Futures',
  'url': 'https://www.navapbc.com/events/open-source-summit-ai-futures',
  'source_kind': 'web_events_page',
  'tags': ['Technology', 'Tech Community']},
 {'name': 'Johns Hopkins Technology Ventures Baltimore events',
  'url': 'https://ventures.jhu.edu/events/',
  'location_pattern': 'Baltimore|1812 Ashland|R[. ]+House',
  'source_kind': 'web_events_page',
  'tags': ['Technology', 'Tech Community']},
 {'name': 'Maryland Tech Council member community calendar',
  'url': 'https://www.mdtechcouncil.com/membership/events/calendar/list/',
  'location_pattern': 'Baltimore|Columbia|WebEx|Virtual',
  'title_pattern': r'\bAI\b|artificial intelligence|cyber|software|tech|data|biopharma|innovation',
  'source_kind': 'web_events_page',
  'tags': ['Technology', 'Tech Community']},
 {'name': 'JHU AI and Human Learning symposium',
  'url': 'https://hub.jhu.edu/events/2026/10/27/johns-hopkins-data-science-and-ai-institute-fall-2026-symposium-artificial-intelligence-and-human-learning/',
  'source_kind': 'web_events_page',
  'tags': ['Technology', 'Tech Community']},
 {'name': 'WomenHack Baltimore',
  'url': 'https://www.eventbrite.com/e/womenhack-baltimore-employer-ticket-november-19-2026-tickets-1982054249616',
  'source_kind': 'eventbrite_event',
  'tags': ['Technology', 'Tech Community']},
 {'name': 'Lean Coffee AI Baltimore',
  'url': 'https://www.eventbrite.com/e/lean-coffee-ai-edition-baltimore-october-2026-tickets-2001571852291',
  'source_kind': 'eventbrite_event',
  'tags': ['AI', 'Tech Community']},
 {'name': 'CONNECTpreneur Baltimore November forum',
  'url': 'https://www.eventbrite.com/e/big-idea-connectpreneur-baltimore-forum-nov-12-in-person-tickets-1991799132824',
  'source_kind': 'eventbrite_event',
  'tags': ['Technology', 'Business']}])
