import { use, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { cityZone, getCity } from '../data/cities';
import { eventsPromise, invalidateEvents } from '../data/fetchEvents';
import { activeFilterCount, type FilterState } from '../data/filters';
import { newestScrape, normalizeEvents, organizerCount } from '../data/normalize';
import { derive, type Derived } from '../data/pipeline';
import { EventSearch, buildSearchIndexWhenIdle } from '../data/search';
import { dayKeyOf, viewerZone, weekdayInZone } from '../data/time';
import type { CalEvent } from '../data/types';
import { useCalendarUrlState, type CalendarUrlActions, type CalendarUrlState } from '../state/urlState';

/** A clock that ticks on a coarse interval, for the live dot and status chips. */
function useNow(intervalMs = 60_000): Date {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), intervalMs);
    return () => clearInterval(id);
  }, [intervalMs]);
  return now;
}

/** A naive match, used only in the moment before the Fuse index is ready. */
function substringKeys(events: readonly CalEvent[], query: string): Set<string> {
  const q = query.trim().toLowerCase();
  const out = new Set<string>();
  for (const e of events) {
    if (
      e.title.toLowerCase().includes(q) ||
      e.orgName.toLowerCase().includes(q) ||
      (e.venue !== null && e.venue.toLowerCase().includes(q)) ||
      (e.locality !== null && e.locality.toLowerCase().includes(q))
    ) {
      out.add(e.key);
    }
  }
  return out;
}

export type Calendar = {
  url: CalendarUrlState;
  actions: CalendarUrlActions;
  /** The zone the calendar renders in. */
  tz: string;
  cityLabel: string;
  tzLabel: string;
  todayKey: string;
  /** 0 = Sunday, in the city's zone. */
  todayWeekday: number;
  now: Date;
  /** Every listed event, before filtering. */
  events: CalEvent[];
  organizers: number;
  newestScrapeAt: Date | null;
  fromCache: boolean;
  /** Where the rows came from: the live feed, a session copy, or a snapshot. */
  feedSource: 'live' | 'session' | 'snapshot';
  snapshotDate: string | null;
  derived: Derived;
  /** Changes only when a filter changes, so the agenda keeps its scroll depth. */
  resetToken: string;
  filtersActive: number;
  retry: () => void;
};

export function useCalendar(): Calendar {
  const [url, actions] = useCalendarUrlState();
  const city = getCity(url.city);
  const tz = url.viewerTz ? viewerZone() : cityZone(city);
  const now = useNow();

  const feed = use(eventsPromise(url.city));

  // Normalized once per payload. Using the live clock here would rebuild 1,695
  // objects every minute and break every downstream memo.
  const loadedAt = useMemo(() => new Date(feed.fetchedAt), [feed.fetchedAt]);
  const events = useMemo(
    () => normalizeEvents(feed.rows, { tz, now: loadedAt }),
    [feed.rows, tz, loadedAt],
  );

  const organizers = useMemo(() => organizerCount(events), [events]);
  const newestScrapeAt = useMemo(() => newestScrape(events), [events]);

  // The search index is built off the critical path.
  const [search, setSearch] = useState<EventSearch | null>(null);
  useEffect(() => {
    setSearch(null);
    return buildSearchIndexWhenIdle(events, setSearch);
  }, [events]);

  const query = url.filters.query;
  const searchKeys = useMemo(() => {
    if (query.trim() === '') return null;
    return search ? search.matchKeys(query) : substringKeys(events, query);
  }, [search, query, events]);

  const todayKey = useMemo(() => dayKeyOf(now, tz), [now, tz]);
  const todayWeekday = useMemo(() => weekdayInZone(now, tz), [now, tz]);

  const derived = useMemo(
    () => derive(events, url.filters, { tz, todayKey, todayWeekday, now, searchKeys }),
    [events, url.filters, tz, todayKey, todayWeekday, now, searchKeys],
  );

  // Refetch when the tab regains focus and the payload is over half an hour old.
  const cityRef = useRef(url.city);
  cityRef.current = url.city;
  useEffect(() => {
    const onFocus = () => {
      if (Date.now() - feed.fetchedAt > 30 * 60_000) {
        invalidateEvents(cityRef.current);
        // A fresh promise is picked up on the next render pass.
        window.dispatchEvent(new Event('cc-refresh'));
      }
    };
    window.addEventListener('focus', onFocus);
    return () => window.removeEventListener('focus', onFocus);
  }, [feed.fetchedAt]);

  const retry = useCallback(() => {
    invalidateEvents(url.city);
    window.location.reload();
  }, [url.city]);

  const f: FilterState = url.filters;
  const resetToken = useMemo(
    () =>
      [
        url.city,
        f.datePreset,
        f.from,
        f.to,
        f.timesOfDay.join('.'),
        f.timeStart,
        f.timeEnd,
        f.outsideWorkHours,
        f.sectors.join('.'),
        f.lens,
        f.lensCategories.join('.'),
        f.nearCoords ? `${f.nearCoords.lat},${f.nearCoords.lng},${f.radiusMiles}` : '',
        f.query,
      ].join('|'),
    [url.city, f],
  );

  return {
    url,
    actions,
    tz,
    cityLabel: city.label,
    tzLabel: url.viewerTz ? 'your time' : city.tzLabel,
    todayKey,
    todayWeekday,
    now,
    events,
    organizers,
    newestScrapeAt,
    fromCache: feed.source === 'session',
    feedSource: feed.source,
    snapshotDate: feed.snapshotDate,
    derived,
    resetToken,
    filtersActive: activeFilterCount(url.filters),
    retry,
  };
}
