# Plan

Redesign of the Code Collective events calendar as a standalone Vite + React + TypeScript
app that reads the live public event JSON. Nothing in the existing site is touched.

## Phase 0 findings

The live Baltimore feed was pulled on 25 September 2026 and committed to
`public/snapshot/baltimore.json`. Re-running the brief's data profile against it
confirms the numbers, with small drift from the morning's scrape:

| Metric | Brief | Measured | Note |
|---|---|---|---|
| Upcoming events | 1,695 | 1,695 | |
| Organizers | 105 | 105 | |
| Busiest day, next two weeks | 106 (Sat 26 Sep) | 105 (Sat 26 Sep) | one listing dropped between scrapes |
| Typical day, next two weeks | 17 to 47 | 15 to 43 | |
| 7d / 8-30d / 31-90d / 90d+ | 347 / 447 / 467 / 434 | 333 / 457 / 470 / 435 | |
| With an image | 1,159 | 1,159 | |
| With an organizer logo | 1,664 | 1,664 | |
| With coordinates | 798 (47%) | 798 (47%) | |
| No end time | 387 | 387 | |
| Cancelled | 3 | 3 | |
| Tags mapping to Technology | 73 (4%) | 73 (4%) | |
| Culture / Economics / Politics / Faith / Government | 824 / 273 / 265 / 265 / 233 | identical | |

The sector counts reproduce exactly, which confirms the slug rules in
`src/data/sectors.ts` match the ones the current site uses.

### Things the profile turned up that the brief does not mention

1. **`startDate` is almost always expressed in UTC.** 1,642 of 1,695 rows carry a
   `+00:00` offset and only 53 carry `-04:00`. Spot-checking a dozen rows against
   clock times written in their own descriptions confirms that converting the
   instant into `America/New_York` yields the right wall clock: `12:00:00+00:00`
   is the 8 a.m. golf tournament, and `00:00:00+00:00` is an 8 p.m. show the
   evening before. 138 rows sit at exactly midnight UTC and belong to the
   *previous* Eastern day. Every date decision therefore has to be zone-explicit;
   nothing may use the machine's local zone.

2. **The upstream `id` is not per-occurrence.** 18 `time.ly` ids are reused across
   every date of a recurring series, one of them across 23 dates. Following the
   brief's key rule literally (`id` when present) silently merged 161 real events
   out of the calendar. `eventKey` now always folds the start into the key, which
   gives 1,695 distinct keys for 1,695 rows. See §13.4 deviation below.

3. **`scrapeTime` arrives in four different shapes**, and 1,422 of 1,695 rows use
   `YYYY-MM-DD HH:MM:SS.ffffff` with no offset at all. `new Date()` hands those to
   implementation-specific parsing, which in V8 means the *viewer's* zone, so the
   freshness line would have read differently in Denver than in Baltimore. They
   are now read in the scrapers' zone.

4. **The sector palette in the live category map is exactly as diagnosed**: Faith
   is `#000000`, Economics is `#ffffff`, Technology `#2563eb` and Education
   `#1d4ed8` are near-identical blues, Politics is a saturated red and Finance a
   saturated yellow. The OKLCH-levelled palette in §8.2 replaces all of it.

5. **No Code Collective events fall in range**, so the "From Code Collective"
   module must render nothing rather than an empty shell.

6. **`data/category_maps/*.json` is genuinely not CORS-readable**, so all three
   lenses are vendored into `src/data/lenses/`.

## Deviations from the brief

Each is deliberate; anything that changes visible behaviour is listed here.

- **§13.4 event key.** The brief says "`id` when present". Doing that loses 161
  events, so the key is `"<id>@<fnv1a(startDate)>"` for rows with an id and the
  brief's `fnv1a(name|startDate|source)` for rows without. Keys stay stable and
  URL-safe, which is all `?event=` needs.
- **§14 Phase 1 debug route.** Replaced with `src/data/snapshot.test.ts`, which
  asserts the per-day counts, sector distribution, organizer count, mappable
  share and freshness stamp against the committed snapshot. It does the same job,
  keeps doing it, and there is nothing to remember to delete.
- **§7.3 tide line under a date filter.** Bars are computed with every filter
  applied *except* the date range, so the strip stays navigable when the visitor
  has narrowed to one day. Clicking a day that the date filter excludes clears
  the date filter and then scrolls, rather than dead-ending.
- **§13.6 time-of-day state.** A single `start`/`end` pair cannot express
  "Morning and Evening". The chips write a new `tod` parameter; `start`/`end` stay
  supported for inbound legacy links and are still written when exactly one chip
  is active, so old links keep working in both directions.
- **§7.14 GitHub icon.** lucide 1.48 has no brand icons, so the footer link is
  text.

## Component list

| Area | Files |
|---|---|
| Data | `types.ts` `cities.ts` `sectors.ts` `lenses.ts` `time.ts` `normalize.ts` `filters.ts` `search.ts` `calendarLinks.ts` `fetchEvents.ts` |
| State | `state/urlState.ts` |
| Shell | `app/App.tsx` `app/providers.tsx` `app/theme.ts` |
| Chrome | `Header` `SearchPill` `SectorRail` `TideLine` |
| Content | `Agenda` (`DaySection` `TimeGroup` `EventRow`) `MonthGrid` `FeaturedStrip` |
| Surfaces | `EventSheet` `FiltersSheet` `SubscribePopover` |
| Map | `MapPanel` (lazy) |
| States | `Skeletons` `EmptyState` `ErrorState` `StaleBanner` |

## Risks

- **1,695 events in one list.** Handled with day-section progressive rendering and
  `content-visibility: auto` rather than virtualization, so the accessible list
  keeps full parity with the map. If INP measures over budget, virtualize.
- **MapLibre 6 is ESM-only** and the basemap is a public community instance with
  no uptime guarantee. It is a lazy chunk, so a failure there cannot take the
  agenda down.
- **Only 47% of events can be placed.** The map is genuinely a partial view, so
  the list stays primary and the map note carries the count of what is missing.
- **Sector colour is decorative only.** Sector names appear as text in rows and
  the sheet, so nothing depends on hue.
