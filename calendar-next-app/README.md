# Code Collective calendar, redesigned

**[Open the live site →](https://jayharwani.github.io/codecollective-calendar-redesign/?city=baltimore)**

A redesign of the [Code Collective](https://codecollective.us/calendar?city=baltimore)
events calendar as a calm, time-first agenda. It reads the same live public
event JSON the current site does, and changes nothing about the site itself.

The deployed page reads the real feed, not a fixture: the event count and the
"updated N hours ago" line move as the upstream calendar does.

The problem it solves: Baltimore runs 1,695 upcoming listings across 105
organizers, with 105 on the busiest Saturday alone. The current page shows them
in a month grid capped at three events per day, so most listings sit behind a
"+N" that a visitor has to go digging for. This version leads with time,
answers "what is on, when, and is it for me" in one screen, and never puts an
event somewhere you cannot reach it.

![The agenda at 1440px](shots/v2-agenda-1440-light.png)

<sub>More: [1280 dark](shots/v2-agenda-1280-dark.png) ·
[390 phone](shots/v2-agenda-390-light.png) ·
[event sheet](shots/v2-event-sheet-1440.png) ·
[a sector selected](shots/v2-sector-health-1440.png) ·
[month](shots/v2-month-1280.png)</sub>

---

## Running it

```bash
npm install
npm run dev
```

Then open <http://localhost:5173/?city=baltimore>.

| Command | What it does |
|---|---|
| `npm run dev` | Vite dev server |
| `npm run build` | Typecheck, then a production build into `dist/` |
| `npm run build:preview` | The hosted preview bundle, relative URLs plus a concept banner |
| `npm test` | 179 unit tests |
| `npm run test:e2e` | 86 Playwright tests, desktop and phone, including axe |
| `npm run typecheck` | TypeScript only |

Two environment variables, both optional:

- `VITE_DATA_SOURCE=live|snapshot` — `snapshot` reads the committed
  `public/snapshot/baltimore.json` so the app works with no network.
- `VITE_SNAPSHOT_FALLBACK=1` — try the live feed first, but fall back to the
  bundled snapshot rather than the error state when the origin is unreachable.
  The meta line says which source it got. Off by default.
- `VITE_BASE` — the mount point for the build. `/` by default, `./` for a
  static host that needs relative URLs.

---

## How it fits together

```
 codecollective.us/<city>/upcoming_events.json        the only input
                    │
                    ▼
  fetchEvents.ts    one cached promise per city, read with React use()
                    │                     sessionStorage copy for the offline state
                    ▼
  normalize.ts      RawEvent → CalEvent
                    │  • occurrence-stable key
                    │  • zone-explicit times
                    │  • HTML entities decoded
                    │  • finished events dropped
                    ▼
  sectors.ts        tags → sectors, via the site's own category map
                    │
                    ▼
  pipeline.ts       one pass per filter change, producing
                    │  • the agenda's day sections
                    │  • the tide line's per-day counts
                    │  • the filters sheet's per-sector counts
                    │  • the map's placeable subset
                    │  • the empty state's relaxations
                    ▼
  App.tsx           agenda │ month │ map, all driven from the URL
```

The URL is the state. Everything a visitor might share — city, search, sectors,
dates, time of day, distance, lens, view, the open event — lives in the query
string, so any view can be linked, and every link the current site has ever
produced still resolves.

### Where things live

| Path | Responsibility |
|---|---|
| `src/data/` | Everything that is not React. Pure, unit-tested. |
| `src/state/urlState.ts` | nuqs parsers, and the mapping for the legacy parameters |
| `src/app/useCalendar.ts` | Joins the feed, the URL and the pipeline |
| `src/components/` | One folder per surface |
| `src/styles/tokens.css` | The Harbor palette, type scale and geometry |
| `public/snapshot/` | A committed copy of the live feed, for offline work and tests |

### What is deliberately lazy

Only the agenda is on the critical path. The map, the detail sheet, the filters
sheet, the subscribe dialog, the phone search sheet and the markdown renderer
are all separate chunks, fetched when they are first needed. Initial JavaScript
is **152 KB gzipped** against a 170 KB budget; MapLibre alone is 286 KB and
never loads unless the map is shown.

---

## The design

Three layers, and only one is loud at a time. v1 stacked five full-width bands
before the first event and gave each of them equal weight; the first listing
started halfway down the screen and nothing led the eye.

| Layer | Job | Surface |
|---|---|---|
| Brand band | Identity, place, search | Collective Blue, scrolls away into a 64px bar |
| Control bar | What am I looking at | White, frosted when stuck, sticky |
| Content | The events | White list, a sticky date gutter, a context rail |

The navy band gives the page a rich top; the content below is calm and bright.
That contrast is where the energy comes from, rather than from decoration.

### Colour

Collective Blue, Sky Highlight and White come from Code Collective's own brand
page. The accent is the **Calvert gold of the Baltimore city flag**, and it has
exactly one job: *now*. It appears on today's coin in the date gutter, today's
coin in the tide line, and the "Happening now" chip. Three places, never more,
and only ever as a filled shape carrying navy text, because gold ink on white
measures 1.9:1.

Roughly 70% of the screen is calm neutral, 20% Collective Blue, 8% sector
colour, 2% gold.

### The tide line

Still the signature element, but no longer a band of its own: it is the list
column's header, beside the list it controls. Bar height is
`3 + 21 × √(count ÷ max)`; the square root is load-bearing, because a
105-event Saturday against a 15-event Tuesday flattens every other day on a
linear scale. Selecting a sector recolours every bar to that sector and springs
them to the new counts in one motion. That handoff is the page's main moment.

### The list

Day headers are gone as full-width bands. Each day is a two-column grid: a 96px
sticky gutter carrying the weekday, a 32px numeral, a relative label and a
count, then the rows beside it. The date stays legible while you read the day,
and the list is one continuous column instead of a stack of banded sections.

Rows dropped from three meta lines to one and from a 64px tile to a 44px
visual, which roughly doubled the density: **seven events now fit at 1440×900
where v1 fit three**. The visual falls back image → organizer logo → initials
avatar, and never to a generic sector icon: 32% of the feed has no image, so a
repeated placeholder would have defined the look of the page.

### The context rail

At 1280 and up, a sticky column holds the map as a card and "Where it's
happening" beneath it. The rail is never empty. When tiles cannot load the map
card collapses to a 72px note and the panel moves up, which matters because
only 47% of the feed carries coordinates and a map alone never tells the whole
location story. The collapse is driven by the first MapLibre error raised
before the style parses, so it happens in about 250ms rather than waiting out
the watchdog; a sandboxed frame is refused by the tile host on its very first
request, and twelve seconds of an empty card is its own kind of broken. Below
1280 the panel moves into the Filters sheet; on a phone the map takes over the
list behind the floating pill.

Type is one superfamily, Instrument Sans Variable, across two axes: condensed
widths carry dense date and time data, normal width carries reading text. In
each zone exactly one element is weight 600.

### The month grid

Four weeks, not a calendar month, so the heading names the actual span rather
than claiming "September 2026 to October 2026" for 28 days.

The first version filled every cell with a five-step blue wash for volume and
topped it with a row of five sector dots. Both marks were trying to say the
same two things, and neither landed: 28 tinted rectangles read as a decorated
table rather than as data, and because a Baltimore weekday carries events in
most sectors, the dot row came out nearly identical in every cell.

They are replaced by one mark per cell. A bar whose **length** is how full the
day is — square-rooted, on the same scale as the tide line, so the two views
agree about which days look busy — and whose **colour** is the sector the day
is mostly about. That one varies where the dots did not: weekdays run to
Government, weekends to Culture. Select a sector and every bar becomes that
sector, recoloured against the filtered counts.

Everything else recedes so the bars can carry the grid. Cells are white with a
hairline instead of a wash, spent days drop their surface entirely and keep
only a muted numeral, and today wears the same gold coin as the agenda gutter
and the tide line.

Below 640px a cell is about 48px wide, so the two event names are dropped
rather than shipped as "Bi…" and "Ho…". At that width the grid answers which
day to look at, and the names are one tap away in the list.

### Nothing was removed

The reorganization moved things; it did not delete them. Every element v1 put
on screen has a named home in v2.

| v1 element | v2 home |
|---|---|
| Wordmark | Brand band, row 1 left |
| Main nav | Brand band, row 1 centre; phone disclosure unchanged |
| Subscribe, Log in | Brand band, row 1 right |
| `What's on in <city>` | Brand band, row 2 |
| Meta line: count, organizers, updated, zone | Brand band, row 2, under the heading |
| Offline / saved-copy / stale banners, three full-width bands | One status chip at the end of the meta line; the full sentence opens in its popover |
| Search pill | Brand band, row 2 right; full-width field on a phone |
| Sector rail | Control bar, left |
| Filters button | Control bar |
| List / Month switch | Control bar |
| Map toggle | Control bar at 1280 and up; floating pill on a phone |
| Tide line, own full-width band | Header of the list column, directly above the first day |
| Featured strip | The "This weekend" interlude, which falls back to featured events when the weekend is empty |
| Full-width day header bands | 96px sticky date gutter |
| Event row, 64px tile and three meta lines | Compact row, 44px visual and one meta line |
| Month grid | Behind the Month segment, rebuilt — see below |
| Map panel, half the screen at 1280 and up | Context rail card, collapsing to a note |
| Organizer footer | Unchanged, page foot |
| Empty, error and loading states | Unchanged |
| Event sheet, filters sheet, subscribe dialog, phone search, toast | Unchanged |

Two v1 files are gone because their work moved wholesale: `Header.tsx` became
`BrandBand.tsx`, and `FeaturedStrip.tsx` became `Interlude.tsx`. Nine
components are new: the brand band, the harbor contours, the control bar, the
event visual, the context rail, the where panel, the interlude and the two
halves of the status chip.

## What the data actually looks like

Profiled from the live Baltimore feed on 25 September 2026, and re-asserted on
every test run in `src/data/snapshot.test.ts`.

| | |
|---|---|
| Upcoming events | 1,695 |
| Organizers | 105 |
| Busiest day | 105, Saturday 26 September |
| With coordinates | 798 (47%) |
| With an image | 1,159 (68%) |
| No end time | 387 |
| Cancelled | 3 |
| Tags mapping to Technology | 73 (4%) |

Five things in that feed are not obvious, and each one changed the code:

**`startDate` is almost always UTC.** 1,642 of 1,695 rows carry a `+00:00`
offset. Spot-checking rows against clock times written in their own
descriptions confirms the instants are right and the offset is real, so a
midnight-UTC row is an 8 p.m. show the evening before — 138 rows look like that.
Every date decision is therefore zone-explicit, and nothing reads the machine's
local zone.

**The upstream `id` is not per-occurrence.** Eighteen `time.ly` ids are reused
across every date of a recurring series, one of them across 23 dates. Keying on
the id alone silently merged 161 real events out of the calendar. The key now
always folds the start in.

**`scrapeTime` arrives in four shapes**, and 1,422 rows carry no UTC offset at
all. `new Date()` hands those to implementation-specific parsing, which resolves
them in the viewer's own zone, so "Updated 3 hours ago" would have read
differently in Denver than in Baltimore. They are parsed in the scrapers' zone.

**Plain text arrives HTML-encoded.** Fifteen titles and ten location fields
carry things like `&#038;` and `&#8217;`, which rendered literally.

**And sometimes percent-encoded instead**, which is how one event enters the
feed twice: "From Crisis to Connection: A First Thursday Online Lunch &#038;
Learn" and the same row with `%26`. Same title, same start, two strings — so
it rendered as "Lunch %26 Learn" and no title comparison could see the pair as
one event. A fixed table of escapes is decoded, rather than
`decodeURIComponent`, which throws on a lone `%` and would turn "Save 50% on
tickets" into mojibake.

On top of those, three display-only transforms. Shouted titles are recased,
either when a title opens with two or more all-caps words or when it is 60% or
more uppercase, against an allowlist that keeps AI, UX, UMBC and anything with
a digit intact. The two `Luma User <handle>` organizers become "Independent
organizer", and their avatars take initials from the venue instead. Seventy
events whose location names a screen rather than a place are chipped "Online"
and kept off the map, which is why the mappable count is 773 rather than the
798 that carry coordinates. Every raw value survives in "Copy event details".

Technology being 4% of the listings is why the sector rail is ordered
mission-first rather than by volume: it is why someone opens a calendar branded
for technologists, and sorting by count would bury it below Culture's 824.

One thing worth passing back upstream: twelve listings, about 0.7%, have a
title that is not a title. Three are raw ISO timestamps
(`2026-09-30T18:30:00`), three are street addresses, one is `3:00 pm`, and five
are scraper notices, including `There were no events found matching your search
criteria. Please search again.` They come from the Harford County Government
Calendar and Maryland Active Data Calendar sources.

Nothing here deletes them. Under 1% of the feed is not worth a filter that
could swallow a real event, and quietly dropping rows would invent a judgement
the data does not support. But the month grid names only two events per day,
and it used to name the first two in feed order — which is how a dozen broken
rows came to occupy a visibly large share of a 28-day grid, one cell reading
`2026-09-30T18:30:00` and another `Start Date and Time`. Those titles are now
ranked last when a cell chooses what to name, and named anyway when a day has
nothing better, because an honest bad title beats an empty cell implying an
empty day. Every one of them still appears in the list, and every one still
counts toward its day.

---

## Accessibility

Targets WCAG 2.2 AA, verified rather than asserted. `npm run test:e2e` runs axe
over the agenda, the month grid, the open detail sheet, the open filters sheet
and the map, in both themes, on desktop and phone, and fails the build on any
serious or critical violation. It builds against the committed snapshot, so it
is deterministic and does not pull 2.6 MB from a third party on every page
load. Lighthouse reports **100 for accessibility** on both profiles.

The list is the accessible equivalent of the map. Every event is a real anchor
with a visible focus ring, the tide line is a roving-tabindex toolbar with arrow
key support, the month grid is a real `role="grid"`, selection is announced, and
a focused row is never hidden under the sticky chrome — there is a test for that
specifically.

Three defects the audit caught that reading the code would not have:

- An unlayered `button { padding: 0 }` reset was silently beating every Tailwind
  `px-*` utility, collapsing the padding on **every button in the app**. The
  Filters control measured 16px wide. Resets now live in `@layer base`.
- Buttons whose labels are hidden on narrow screens had no accessible name at
  all.
- The cancelled-row treatment the brief describes, 60% opacity, takes muted ink
  to 3.3:1. Cancelled listings are struck through and badged instead.

---

## Performance

Lighthouse against a production build:

| | Desktop | Mobile |
|---|---|---|
| Performance | 96 | 79 |
| Accessibility | 100 | 100 |
| LCP | 0.5s | 4.5s |
| CLS | 0 | 0 |
| Total blocking time | 130ms | 100ms |

Initial JavaScript is **151.5 KB gzipped** against a 170 KB budget. Two things
had to be pushed off the critical path to keep it there: Base UI's popover,
which the status chip in the brand band would otherwise have loaded on every
visit for 33 KB, and the same library's Switch, replaced with a plain
`role="switch"` button for the map toggle.

Mobile LCP misses the 2.0s target, and the reason is structural rather than
fixable from here. Lighthouse's mobile profile applies a 4× CPU slowdown, and
the page has to fetch a 2.6 MB unpaginated feed (211 KB over the wire), parse
it, and normalize 1,695 events before it can say how many there are. The
heading and the meta line are painted from static markup in `index.html` so
something real is on screen at 1.8s, and the first agenda batch was cut from 14
days to 3, which took blocking time from 270ms to 60ms and the DOM from 5,036
elements to 1,911. The remaining 2.6s is the feed.

The fix is an endpoint that returns a bounded window — the next 30 days rather
than the next 30 months — or a pre-aggregated per-day count. Both are backend
changes, which the brief puts out of scope, so this is reported rather than
worked around.

---

## Compatibility with the current site

Every parameter the existing calendar emits keeps working, including this one:

```
?city=baltimore&lm=community_sectors&lt=technology.education.entrepreneurship.
economics.finance.health.politics.government.culture.faith.environment.
makerspace.other&lx=0&lh=1&lc=1&li=1&ls=0&lw=0&la=open_page
```

It loads with "All" active, because a list naming every sector means no filter,
and the six display switches the old tools panel wrote (`lx`, `lh`, `lc`, `li`,
`ls`, `la`) are carried through untouched so the link survives a round trip.
There is a test for that URL specifically.

`map` and `lw` are spelled `1` and `0`, as the contract says. This is worth
noting because nuqs's `parseAsBoolean` only recognises the literal strings
`true` and `false`, so `?map=1` initially parsed as *false* and switched the map
off.

---

## Deliberate departures from the brief

| Brief | What was built | Why |
|---|---|---|
| Key is the `id` when present | `<id>@<hash(startDate)>` | The id is not per-occurrence; following the rule lost 161 events |
| A temporary debug route for Phase 1 | `src/data/snapshot.test.ts` | Same job, keeps doing it, nothing to remember to delete |
| Tide line bars reflect the current filters | Every filter except the date range | Otherwise narrowing to one day empties the strip you navigate with |
| `start`/`end` carry the time-of-day chips | A new `tod` parameter, with `start`/`end` still read and written | One window cannot express "Morning and Evening" |
| Cancelled row at 60% opacity | Struck through and badged | 60% opacity fails AA |
| GitHub icon in the footer | A text link | lucide 1.48 dropped brand icons |
| v2: a gold dot on the "Happening now" group | A filled gold chip | A gold dot on white is 1.9:1, and the brief forbids gold dots outright |
| v2: initials in the sector colour on its tint | Ink on the tint | Sector-on-tint measures about 4.4:1, just under the threshold; the tint still carries the sector |
| v2: Map switch at every desktop width | Hidden below 1280 | There is no context rail to toggle below 1280, so the control did nothing |

---

## What is not built

Per the brief: no event editing or submission, no accounts, no organizer tools,
no changes to the scraping pipeline, no filtered ICS feeds (the backend offers
one feed per city), and no deployment. The subscribe links point at the existing
per-city ICS feed.

The map uses the public OpenFreeMap instance, which is provided as is. For
anything load-bearing, self-host Protomaps PMTiles instead.

---

## Credits

Event data and the category maps come from
[Code Collective](https://codecollective.us). Map tiles from OpenFreeMap and
OpenMapTiles, data © OpenStreetMap contributors.
