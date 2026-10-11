import {
  createParser,
  parseAsInteger,
  parseAsString,
  parseAsStringLiteral,
  useQueryStates,
} from 'nuqs';
import { useCallback, useMemo } from 'react';
import { DEFAULT_CITY, isCityId } from '../data/cities';
import { EMPTY_FILTERS, chipForWindow, type FilterState } from '../data/filters';
import { LENSES, isLensId } from '../data/lenses';
import { RAIL_ORDER, isSectorId } from '../data/sectors';
import { TIME_OF_DAY_ORDER, TIME_OF_DAY_WINDOW } from '../data/time';
import type { CityId, DatePreset, LensId, SectorId, TimeOfDay } from '../data/types';

/**
 * The URL is the source of truth for everything a visitor might share, and
 * every parameter the current site uses keeps working. `lt`, `lm`, `near`,
 * `radius`, `from`, `to`, `start`, `end`, `lw` and `q` are read and written;
 * the old display switches `lx`, `lh`, `lc`, `li`, `ls` and `la` are carried
 * through untouched so an old link survives a round trip.
 */

const ALL_SECTOR_SLUGS = new Set<string>(RAIL_ORDER);

/** `lt=technology.education`, with `__none__` for an explicit empty set. */
const parseAsDotSectors = createParser({
  parse(value: string): SectorId[] | null {
    if (value === '') return null;
    if (value === '__none__') return [];
    const parts = value.split('.').filter((p) => p !== '');
    const ids = parts.filter(isSectorId);
    // The current site writes every sector when nothing is filtered. Treat a
    // full list as "All" so an old link does not look like 13 active chips.
    if (ids.length >= ALL_SECTOR_SLUGS.size) return [];
    return ids;
  },
  serialize(value: SectorId[]): string {
    if (value.length === 0) return '__none__';
    return value.join('.');
  },
  eq(a: SectorId[], b: SectorId[]): boolean {
    return a.length === b.length && a.every((v, i) => v === b[i]);
  },
});

/** Dot-joined lens category slugs, for a non-default lens. */
const parseAsDotStrings = createParser({
  parse(value: string): string[] | null {
    if (value === '') return null;
    return value.split('.').filter((p) => p !== '');
  },
  serialize(value: string[]): string {
    return value.join('.');
  },
  eq(a: string[], b: string[]): boolean {
    return a.length === b.length && a.every((v, i) => v === b[i]);
  },
});

/** `tod=morning.evening`. Expresses what a single start/end pair cannot. */
const parseAsTimesOfDay = createParser({
  parse(value: string): TimeOfDay[] | null {
    if (value === '') return null;
    const set = new Set(value.split('.'));
    return TIME_OF_DAY_ORDER.filter((t) => set.has(t));
  },
  serialize(value: TimeOfDay[]): string {
    return value.join('.');
  },
  eq(a: TimeOfDay[], b: TimeOfDay[]): boolean {
    return a.length === b.length && a.every((v, i) => v === b[i]);
  },
});

const DAY_KEY = /^\d{4}-\d{2}-\d{2}$/;
const parseAsDayKey = createParser({
  parse(value: string): string | null {
    return DAY_KEY.test(value) ? value : null;
  },
  serialize(value: string): string {
    return value;
  },
});

const HHMM = /^\d{1,2}:\d{2}$/;
const parseAsClock = createParser({
  parse(value: string): string | null {
    return HHMM.test(value) ? value : null;
  },
  serialize(value: string): string {
    return value;
  },
});

/**
 * The URL contract spells these flags `1` and `0`, both for the new `map`
 * parameter and for the site's existing `lw`. nuqs's `parseAsBoolean` only
 * recognises the literal strings "true" and "false", so `map=1` parsed as
 * `false` and switched the map off instead of on.
 */
const parseAsFlag = createParser({
  parse(value: string): boolean | null {
    const v = value.trim().toLowerCase();
    if (v === '1' || v === 'true' || v === 'yes') return true;
    if (v === '0' || v === 'false' || v === 'no') return false;
    return null;
  },
  serialize(value: boolean): string {
    return value ? '1' : '0';
  },
});

const parseAsCity = createParser({
  parse(value: string): CityId | null {
    return isCityId(value) ? value : null;
  },
  serialize(value: CityId): string {
    return value;
  },
});

const parseAsLens = createParser({
  parse(value: string): LensId | null {
    return isLensId(value) ? value : null;
  },
  serialize(value: LensId): string {
    return value;
  },
});

/** `view=agenda|month`; the site's older `calendar` and `desktop` mean month. */
const parseAsView = createParser({
  parse(value: string): 'agenda' | 'month' | null {
    if (value === 'agenda') return 'agenda';
    if (value === 'month' || value === 'calendar' || value === 'desktop') return 'month';
    return null;
  },
  serialize(value: 'agenda' | 'month'): string {
    return value;
  },
});

const DATE_PRESETS = ['any', 'today', 'tomorrow', 'weekend', 'next7', 'custom'] as const;

const PARSERS = {
  city: parseAsCity.withDefault(DEFAULT_CITY),
  q: parseAsString.withDefault(''),
  lt: parseAsDotSectors.withDefault([]),
  lm: parseAsLens.withDefault('community_sectors'),
  lc2: parseAsDotStrings.withDefault([]),
  when: parseAsStringLiteral(DATE_PRESETS).withDefault('any'),
  from: parseAsDayKey,
  to: parseAsDayKey,
  tod: parseAsTimesOfDay.withDefault([]),
  start: parseAsClock,
  end: parseAsClock,
  lw: parseAsFlag.withDefault(false),
  near: parseAsString,
  radius: parseAsInteger.withDefault(10),
  view: parseAsView.withDefault('agenda'),
  map: parseAsFlag,
  event: parseAsString,
  day: parseAsDayKey,
  tz: parseAsString,
};

export type CalendarUrlState = {
  city: CityId;
  view: 'agenda' | 'month';
  mapParam: boolean | null;
  eventKey: string | null;
  dayAnchor: string | null;
  viewerTz: boolean;
  filters: FilterState;
};

export type CalendarUrlActions = {
  setCity: (city: CityId) => void;
  setView: (view: 'agenda' | 'month') => void;
  setMap: (on: boolean) => void;
  openEvent: (key: string | null) => void;
  setDayAnchor: (day: string | null) => void;
  setViewerTz: (on: boolean) => void;
  setQuery: (q: string) => void;
  setSectors: (ids: SectorId[]) => void;
  setLens: (lens: LensId, categories?: string[]) => void;
  setLensCategories: (ids: string[]) => void;
  applyFilters: (next: Partial<FilterState>) => void;
  clearAll: () => void;
};

/** Everything the app reads from, and the writers that keep the URL in step. */
export function useCalendarUrlState(): [CalendarUrlState, CalendarUrlActions] {
  const [raw, setRaw] = useQueryStates(PARSERS, { history: 'replace' });

  const state = useMemo<CalendarUrlState>(() => {
    // A legacy link may carry only start/end. Show the matching chip so the
    // filters sheet and the results agree about what is active.
    const legacyChip = raw.tod.length === 0 ? chipForWindow(raw.start, raw.end) : null;
    const timesOfDay = raw.tod.length > 0 ? raw.tod : legacyChip ? [legacyChip] : [];

    // When a chip covers the raw window, the chip already enforces it.
    const chipCoversWindow = legacyChip !== null;

    const filters: FilterState = {
      ...EMPTY_FILTERS,
      datePreset: (raw.from || raw.to) && raw.when === 'any' ? 'custom' : (raw.when as DatePreset),
      from: raw.from,
      to: raw.to,
      timesOfDay,
      timeStart: chipCoversWindow ? null : raw.start,
      timeEnd: chipCoversWindow ? null : raw.end,
      outsideWorkHours: raw.lw,
      sectors: raw.lt,
      lens: raw.lm,
      lensCategories: raw.lm === 'community_sectors' ? [] : raw.lc2,
      near: raw.near,
      nearCoords: null, // resolved by the filters sheet, never trusted from the URL
      radiusMiles: Math.min(50, Math.max(1, raw.radius)),
      query: raw.q,
    };

    return {
      city: raw.city,
      view: raw.view,
      mapParam: raw.map,
      eventKey: raw.event && raw.event !== '' ? raw.event : null,
      dayAnchor: raw.day,
      viewerTz: raw.tz === 'local',
      filters,
    };
  }, [raw]);

  const setCity = useCallback(
    (city: CityId) => {
      // A different city invalidates every place-bound choice.
      void setRaw({ city, event: null, day: null, near: null });
    },
    [setRaw],
  );

  const setView = useCallback((view: 'agenda' | 'month') => void setRaw({ view }), [setRaw]);
  const setMap = useCallback((on: boolean) => void setRaw({ map: on }), [setRaw]);

  const openEvent = useCallback(
    (key: string | null) => {
      // Pushed, not replaced, so the back button closes the sheet.
      void setRaw({ event: key }, { history: 'push' });
    },
    [setRaw],
  );

  const setDayAnchor = useCallback((day: string | null) => void setRaw({ day }), [setRaw]);
  const setViewerTz = useCallback((on: boolean) => void setRaw({ tz: on ? 'local' : null }), [setRaw]);
  const setQuery = useCallback((q: string) => void setRaw({ q: q === '' ? null : q }), [setRaw]);

  const setSectors = useCallback(
    (ids: SectorId[]) => {
      void setRaw({ lt: ids.length === 0 ? null : ids });
    },
    [setRaw],
  );

  const setLens = useCallback(
    (lens: LensId, categories: string[] = []) => {
      void setRaw({
        lm: lens === 'community_sectors' ? null : lens,
        lc2: categories.length === 0 ? null : categories,
        // Sector ids do not survive a lens change.
        lt: null,
      });
    },
    [setRaw],
  );

  const setLensCategories = useCallback(
    (ids: string[]) => void setRaw({ lc2: ids.length === 0 ? null : ids }),
    [setRaw],
  );

  const applyFilters = useCallback(
    (next: Partial<FilterState>) => {
      const patch: Partial<Record<keyof typeof PARSERS, unknown>> = {};

      if ('datePreset' in next) {
        const preset = next.datePreset ?? 'any';
        patch.when = preset === 'any' ? null : preset;
        if (preset !== 'custom') {
          patch.from = null;
          patch.to = null;
        }
      }
      if ('from' in next) patch.from = next.from ?? null;
      if ('to' in next) patch.to = next.to ?? null;

      if ('timesOfDay' in next) {
        const chips = next.timesOfDay ?? [];
        patch.tod = chips.length === 0 ? null : chips;
        // Keep start/end meaningful for old consumers when one chip is active,
        // and drop them otherwise rather than write a misleading envelope.
        if (chips.length === 1) {
          const w = TIME_OF_DAY_WINDOW[chips[0]!];
          patch.start = `${String(Math.floor(w.from / 60)).padStart(2, '0')}:00`;
          patch.end = `${String(Math.floor(w.to / 60) % 24).padStart(2, '0')}:00`;
        } else {
          patch.start = null;
          patch.end = null;
        }
      }

      if ('outsideWorkHours' in next) patch.lw = next.outsideWorkHours ? true : null;
      if ('sectors' in next) patch.lt = (next.sectors ?? []).length === 0 ? null : next.sectors;
      if ('near' in next) patch.near = next.near === '' ? null : next.near;
      if ('radiusMiles' in next) patch.radius = next.radiusMiles ?? null;
      if ('query' in next) patch.q = next.query === '' ? null : next.query;
      if ('lens' in next) {
        patch.lm = next.lens === 'community_sectors' ? null : next.lens;
        if (next.lens === 'community_sectors') patch.lc2 = null;
      }
      if ('lensCategories' in next) {
        patch.lc2 = (next.lensCategories ?? []).length === 0 ? null : next.lensCategories;
      }

      void setRaw(patch as Parameters<typeof setRaw>[0]);
    },
    [setRaw],
  );

  const clearAll = useCallback(() => {
    void setRaw({
      q: null,
      lt: null,
      lm: null,
      lc2: null,
      when: null,
      from: null,
      to: null,
      tod: null,
      start: null,
      end: null,
      lw: null,
      near: null,
      radius: null,
    });
  }, [setRaw]);

  const actions = useMemo<CalendarUrlActions>(
    () => ({
      setCity,
      setView,
      setMap,
      openEvent,
      setDayAnchor,
      setViewerTz,
      setQuery,
      setSectors,
      setLens,
      setLensCategories,
      applyFilters,
      clearAll,
    }),
    [
      setCity,
      setView,
      setMap,
      openEvent,
      setDayAnchor,
      setViewerTz,
      setQuery,
      setSectors,
      setLens,
      setLensCategories,
      applyFilters,
      clearAll,
    ],
  );

  return [state, actions];
}

/** The rail items for the active lens: sectors, or that lens's categories. */
export function railItemsFor(lens: LensId): Array<{ id: string; label: string; color?: string }> {
  if (lens === 'community_sectors') return [];
  return LENSES[lens].categories.map((c) => ({ id: c.id, label: c.label, color: c.color }));
}
