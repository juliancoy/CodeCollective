import { LENSES, lensCategoriesForTags } from './lenses';
import {
  TIME_OF_DAY_WINDOW,
  addDaysToKey,
  minutesInZoneCached,
  weekdayInZone,
  weekdayInZoneCached,
} from './time';
import type { CalEvent, DatePreset, LensId, SectorId, TimeOfDay } from './types';

export type Coords = { lat: number; lng: number };

export type FilterState = {
  datePreset: DatePreset;
  /** Inclusive custom range, YYYY-MM-DD. Only read when datePreset is 'custom'. */
  from: string | null;
  to: string | null;
  /** Time-of-day chips. */
  timesOfDay: TimeOfDay[];
  /** Raw HH:MM window from a legacy link, applied on top of the chips. */
  timeStart: string | null;
  timeEnd: string | null;
  outsideWorkHours: boolean;
  sectors: SectorId[];
  /** Non-default lens categories, when the lens is not community_sectors. */
  lens: LensId;
  lensCategories: string[];
  near: string | null;
  nearCoords: Coords | null;
  radiusMiles: number;
  query: string;
};

export const EMPTY_FILTERS: FilterState = {
  datePreset: 'any',
  from: null,
  to: null,
  timesOfDay: [],
  timeStart: null,
  timeEnd: null,
  outsideWorkHours: false,
  sectors: [],
  lens: 'community_sectors',
  lensCategories: [],
  near: null,
  nearCoords: null,
  radiusMiles: 10,
  query: '',
};

/* ---------------- date range ---------------- */

/** The inclusive day-key window a preset resolves to, or null for no bound. */
export function resolveDateRange(
  state: Pick<FilterState, 'datePreset' | 'from' | 'to'>,
  todayKey: string,
  todayWeekday: number,
): { from: string; to: string } | null {
  switch (state.datePreset) {
    case 'today':
      return { from: todayKey, to: todayKey };
    case 'tomorrow': {
      const t = addDaysToKey(todayKey, 1);
      return { from: t, to: t };
    }
    case 'weekend': {
      // Saturday and Sunday of the coming weekend. On Sat or Sun, this weekend.
      const toSaturday = todayWeekday === 0 ? -1 : 6 - todayWeekday;
      const satKey = addDaysToKey(todayKey, toSaturday);
      const sunKey = addDaysToKey(satKey, 1);
      // Never reach backwards past today.
      return { from: satKey < todayKey ? todayKey : satKey, to: sunKey };
    }
    case 'next7':
      return { from: todayKey, to: addDaysToKey(todayKey, 6) };
    case 'custom': {
      if (!state.from && !state.to) return null;
      const from = state.from ?? todayKey;
      const to = state.to ?? '9999-12-31';
      return from <= to ? { from, to } : { from: to, to: from };
    }
    case 'any':
    default:
      return null;
  }
}

/* ---------------- time of day ---------------- */

function parseHHMM(v: string | null): number | null {
  if (!v) return null;
  const m = /^(\d{1,2}):(\d{2})$/.exec(v.trim());
  if (!m) return null;
  const h = Number(m[1]);
  const min = Number(m[2]);
  if (h > 24 || min > 59) return null;
  return h * 60 + min;
}

/** True when `minutes` falls inside any selected chip window. */
function matchesTimesOfDay(minutes: number, chips: readonly TimeOfDay[]): boolean {
  if (chips.length === 0) return true;
  for (const chip of chips) {
    const w = TIME_OF_DAY_WINDOW[chip];
    if (chip === 'late') {
      // Late wraps midnight: 21:00-24:00 plus 00:00-06:00.
      if (minutes >= w.from || minutes < 6 * 60) return true;
    } else if (minutes >= w.from && minutes < w.to) {
      return true;
    }
  }
  return false;
}

/** The single chip a raw HH:MM window corresponds to, if any. */
export function chipForWindow(start: string | null, end: string | null): TimeOfDay | null {
  const s = parseHHMM(start);
  const e = parseHHMM(end);
  if (s === null || e === null) return null;
  for (const [chip, w] of Object.entries(TIME_OF_DAY_WINDOW) as Array<[TimeOfDay, { from: number; to: number }]>) {
    if (w.from === s && w.to === e) return chip;
  }
  return null;
}

/* ---------------- distance ---------------- */

const EARTH_MILES = 3958.7613;

export function haversineMiles(a: Coords, b: Coords): number {
  const toRad = (d: number) => (d * Math.PI) / 180;
  const dLat = toRad(b.lat - a.lat);
  const dLng = toRad(b.lng - a.lng);
  const lat1 = toRad(a.lat);
  const lat2 = toRad(b.lat);
  const h =
    Math.sin(dLat / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLng / 2) ** 2;
  return 2 * EARTH_MILES * Math.asin(Math.min(1, Math.sqrt(h)));
}

/* ---------------- predicates ---------------- */

export type Predicates = {
  date: (e: CalEvent) => boolean;
  time: (e: CalEvent) => boolean;
  sector: (e: CalEvent) => boolean;
  distance: (e: CalEvent) => boolean;
};

export type PredicateContext = {
  tz: string;
  todayKey: string;
  todayWeekday: number;
};

const PASS = () => true;

export function buildPredicates(state: FilterState, ctx: PredicateContext): Predicates {
  const { tz } = ctx;

  const range = resolveDateRange(state, ctx.todayKey, ctx.todayWeekday);
  const date: Predicates['date'] = range
    ? (e) => {
        // A multi-day event counts as inside the range if it overlaps it.
        const last = e.endDayKey ?? e.dayKey;
        return e.dayKey <= range.to && last >= range.from;
      }
    : PASS;

  const rawFrom = parseHHMM(state.timeStart);
  const rawTo = parseHHMM(state.timeEnd);
  const hasChips = state.timesOfDay.length > 0;
  const hasRaw = rawFrom !== null && rawTo !== null;
  const needsTime = hasChips || hasRaw || state.outsideWorkHours;

  const time: Predicates['time'] = !needsTime
    ? PASS
    : (e) => {
        const minutes = minutesInZoneCached(e.start, tz);
        if (hasChips && !matchesTimesOfDay(minutes, state.timesOfDay)) return false;
        if (hasRaw) {
          if (rawFrom! <= rawTo!) {
            if (minutes < rawFrom! || minutes >= rawTo!) return false;
          } else if (minutes < rawFrom! && minutes >= rawTo!) {
            // A window that wraps midnight.
            return false;
          }
        }
        if (state.outsideWorkHours) {
          // Hide weekday events that start between 9am and 5pm.
          const wd = weekdayInZoneCached(e.start, tz);
          if (wd >= 1 && wd <= 5 && minutes >= 9 * 60 && minutes < 17 * 60) return false;
        }
        return true;
      };

  const lens = LENSES[state.lens];
  const usingLensCategories = state.lens !== 'community_sectors' && state.lensCategories.length > 0;
  const sectorSet = new Set(state.sectors);
  const lensSet = new Set(state.lensCategories);

  const sector: Predicates['sector'] = usingLensCategories
    ? (e) => lensCategoriesForTags(lens, e.tags).some((c) => lensSet.has(c))
    : sectorSet.size === 0
      ? PASS
      : (e) => e.sectors.some((s) => sectorSet.has(s));

  const origin = state.nearCoords;
  const distance: Predicates['distance'] =
    origin === null
      ? PASS
      : (e) => {
          // Events we cannot place are hidden while distance is on; the
          // filters sheet says so in its helper text.
          if (!e.coords) return false;
          return haversineMiles(origin, e.coords) <= state.radiusMiles;
        };

  return { date, time, sector, distance };
}

/** Whether any non-sector, non-search filter is narrowing the results. */
export function activeFilterCount(state: FilterState): number {
  let n = 0;
  if (state.datePreset !== 'any') n++;
  if (state.timesOfDay.length > 0 || (state.timeStart && state.timeEnd)) n++;
  if (state.outsideWorkHours) n++;
  if (state.nearCoords) n++;
  if (state.lens !== 'community_sectors') n++;
  return n;
}

export function isPristine(state: FilterState): boolean {
  return (
    activeFilterCount(state) === 0 && state.sectors.length === 0 && state.query.trim() === ''
  );
}

/* ---------------- day grouping ---------------- */

export type DayGroup = { dayKey: string; events: CalEvent[] };

/** Chronological events into day groups, in day order. */
export function groupByDay(events: readonly CalEvent[]): DayGroup[] {
  const groups: DayGroup[] = [];
  let current: DayGroup | null = null;
  for (const e of events) {
    if (!current || current.dayKey !== e.dayKey) {
      current = { dayKey: e.dayKey, events: [] };
      groups.push(current);
    }
    current.events.push(e);
  }
  return groups;
}

/** Event count per day key. */
export function countByDay(events: readonly CalEvent[]): Map<string, number> {
  const m = new Map<string, number>();
  for (const e of events) m.set(e.dayKey, (m.get(e.dayKey) ?? 0) + 1);
  return m;
}

/** Event count per sector, for the filters sheet. */
export function countBySector(events: readonly CalEvent[]): Map<SectorId, number> {
  const m = new Map<SectorId, number>();
  for (const e of events) for (const s of e.sectors) m.set(s, (m.get(s) ?? 0) + 1);
  return m;
}

/** How many of these events could be drawn on the map. */
export function countMappable(events: readonly CalEvent[]): number {
  let n = 0;
  for (const e of events) if (e.coords) n++;
  return n;
}

/** Weekday helper re-exported so callers need one import. */
export { weekdayInZone };
