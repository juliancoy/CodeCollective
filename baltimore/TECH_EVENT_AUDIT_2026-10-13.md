# Baltimore technology calendar coverage audit — 2026-10-13

Scope: public web search for upcoming Baltimore city and metro technology, AI, software, cybersecurity, startup, and research events through December 2026. Relevant locally hosted virtual events are labeled online. Compared against the live 1,761-event JSON feed on 2026-10-13; this is a best-effort audit, not proof that every event on the web has been discovered.

## Verified additions

| Date (Eastern) | Event | Organizer evidence |
|---|---|---|
| 2026-10-13 16:30 | Open Source Summit: AI Futures — optional welcome happy hour | [Source](https://www.navapbc.com/events/open-source-summit-ai-futures) |
| 2026-10-14 11:30 | Open Source Summit: AI Futures | [Source](https://www.navapbc.com/events/open-source-summit-ai-futures) |
| 2026-10-17 10:00 | From Prompts to Agents: Designing Intelligent AI Systems | [Source](https://www.mdtechcouncil.com/membership/events/calendar/list/) |
| 2026-10-22 11:30 | Lean Coffee AI Edition: Baltimore (October 2026) | [Source](https://www.eventbrite.com/e/lean-coffee-ai-edition-baltimore-october-2026-tickets-2001571852291) |
| 2026-10-27 08:00 | TEDCO 2026 Entrepreneur Expo | [Source](https://ventures.jhu.edu/event/tedco-2026-entrepreneur-expo/) |
| 2026-10-27 09:00 | Johns Hopkins Data Science and AI Institute Fall 2026 Symposium: Artificial Intelligence and Human Learning | [Source](https://hub.jhu.edu/events/2026/10/27/johns-hopkins-data-science-and-ai-institute-fall-2026-symposium-artificial-intelligence-and-human-learning/) |
| 2026-10-28 08:00 | The AI Journey Workshop | [Source](https://www.mdtechcouncil.com/membership/events/calendar/the-ai-journey-workshop/) |
| 2026-10-29 16:00 | Anchor Ventures / From Curious to Confident: Putting AI to Work | [Source](https://ventures.jhu.edu/event/anchor-ventures-from-curious-to-confident-putting-ai-to-work/) |
| 2026-11-04 12:00 | AI and Authorship: How AI Affects Creation, Publication, and Contracts | [Source](https://guides.lndlibrary.org/c.php?g=1479381&p=11062167) |
| 2026-11-07 10:00 | Archive Fever & AI | [Source](https://www.lizflyntz.net/archivefeverandai) |
| 2026-11-10 16:00 | Fast 50 and Fire Awards 2026 | [Source](https://www.bizjournals.com/baltimore/event/172579/2026/fast-50-and-fire-awards-2026) |
| 2026-11-12 08:00 | Big Idea CONNECTpreneur Baltimore Forum | [Source](https://www.eventbrite.com/e/big-idea-connectpreneur-baltimore-forum-nov-12-in-person-tickets-1991799132824) |
| 2026-11-12 08:30 | EO Baltimore AI Hackathon | [Source](https://www.prnewswire.com/news-releases/eo-baltimore-to-host-hands-on-ai-hackathon-for-business-owners-on-november-12-302881430.html) |
| 2026-11-12 18:00 | Hot Topic Discussion: Cybersecurity and AI Governance | [Source](https://www.mdtechcouncil.com/membership/events/calendar/list/) |
| 2026-11-19 18:00 | WomenHack - Baltimore | [Source](https://womenhack.com/events/united-states/baltimore/) |

## Coverage changes

- Nava: parse its labeled UTC date range and Baltimore location. Pin the AI Futures URL because the organizer index did not link to it during this audit. Keep the optional welcome gathering separate.
- Hopkins Hub: support schema.org Event microdata, including explicit timezone offsets. Its event page says 9 AM; a secondary guide said 9:30 AM. Prefer the university event metadata.
- Add Hopkins Technology Ventures and the separate Maryland Tech Council member calendar. Filter new broad feeds by location to avoid DC and unrelated statewide events.
- Pin the two verified Eventbrite listings for refresh through the existing Eventbrite parser.
- Manual entries retain verified facts if a source fails. Existing deduplication prevents the same scraped occurrence from appearing again. Manual entries take precedence, so date changes require reviewing/updating the corresponding manual record.

## Already present / excluded / unresolved

- Already present: The Ball Is in Your Court (November 4), Quantum AI and Cyber Hub roadshow (November 12), and SSR/Post-Quantum Cryptography workshop listings in December.
- Excluded past events: Baltimore Official Cybersecurity Summit was April 28; AI NEXTGEN was October 10.
- Game Your Future (November 6–8) has a cancellation signal; do not add as active without organizer confirmation.
- IEEE Baltimore Technical and Professional Development Colloquium (November 7): IEEE listings confirm a date, but primary detail access was blocked; time, venue, and attendance conditions still need verification.
- UMBC Cyber Defense Lab November 6 talk: schedule lead only; validate talk detail and public access before adding.
- Future of Health Care (October 29) and Neurotech BioChallenge (October 29) remain leads; direct event detail verification was incomplete.
- Archive Fever has a confirmed 10 AM start but no confirmed finish; leave endTime empty. WomenHack venue is not published; label it as organizer-provided, never invent an address.
- EO hackathon is restricted to members/eligible business owners and requires a paid Claude subscription; preserve those conditions.

## Repeating discovery

The existing daily Update Calendar workflow refreshes registered sources and deploys generated changes. Web search is a separate audit layer: search Baltimore plus AI, open source, software, cybersecurity, technology, startup, biotech, and university event terms; review organizer pages, compare canonical URL and title/date against upcoming_events.json, exclude past/cancelled/out-of-area events, and add a tested recurring source where feasible. Do not assume an indexed calendar contains every organizer detail page.

## Validation

- Generic scraper regression tests include Nava UTC conversion, Baltimore scope, malformed dates, Hopkins microdata, and location filtering.
- Actual downloaded Nava, Hopkins Hub, and JHTV pages each produced the correct event and start timestamp.
- JSON/ICS counts and unique audit IDs checked; existing ICS entries and UIDs preserved.

Live source checks: JHTV returned the three local upcoming events (via both its feed and detail-page representations); MTC's separate member calendar returned the three verified AI/security events plus an unrelated student webinar. A title filter excludes the latter. WomenHack's generic page generated invalid heuristic titles, so it is deliberately NOT registered as a generic page; its dated Eventbrite listing is used instead.
