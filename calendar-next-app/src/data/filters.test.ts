import { describe, expect, it } from 'vitest';
import {
  EMPTY_FILTERS,
  buildPredicates,
  chipForWindow,
  countByDay,
  countBySector,
  countMappable,
  groupByDay,
  haversineMiles,
  resolveDateRange,
  type FilterState,
} from './filters';
import { normalizeEvent } from './normalize';
import type { CalEvent, RawEvent } from './types';

const ET = 'America/New_York';
const NOW = new Date('2026-09-25T16:00:00Z'); // Friday noon Eastern
const TODAY = '2026-09-25';
const TODAY_WEEKDAY = 5; // Friday

/** Build a CalEvent through the real normalizer so tests track production. */
function ev(over: {
  start: string;
  end?: string;
  tags?: string[];
  coords?: { lat: number; lng: number } | null;
  title?: string;
}): CalEvent {
  const row: RawEvent = {
    name: over.title ?? 'Event',
    description: '',
    startDate: over.start,
    endTime: over.end,
    url: 'https://example.com/e',
    status: 'ACTIVE',
    location:
      over.coords === null
        ? { name: 'Somewhere' }
        : { name: 'Somewhere', latitude: over.coords?.lat ?? 39.29, longitude: over.coords?.lng ?? -76.61 },
    scrapeTime: '2026-09-25T04:00:00-04:00',
    tags: over.tags ?? ['Community'],
    source: 'https://example.com',
    source_url: 'https://example.com',
    source_group: 'Example',
    org_name: 'Example',
    orgName: 'Example',
  };
  const out = normalizeEvent(row, { tz: ET, now: NOW });
  if (!out) throw new Error('fixture did not normalize');
  return out;
}

const ctx = { tz: ET, todayKey: TODAY, todayWeekday: TODAY_WEEKDAY };

function state(over: Partial<FilterState> = {}): FilterState {
  return { ...EMPTY_FILTERS, ...over };
}

/** Eastern wall clock to an ISO instant, so fixtures read naturally. */
function et(day: string, hhmm: string): string {
  return `${day}T${hhmm}:00-04:00`;
}

describe('resolveDateRange', () => {
  it('returns no bound for any date', () => {
    expect(resolveDateRange(state(), TODAY, TODAY_WEEKDAY)).toBeNull();
  });

  it('pins today and tomorrow', () => {
    expect(resolveDateRange(state({ datePreset: 'today' }), TODAY, TODAY_WEEKDAY)).toEqual({
      from: '2026-09-25',
      to: '2026-09-25',
    });
    expect(resolveDateRange(state({ datePreset: 'tomorrow' }), TODAY, TODAY_WEEKDAY)).toEqual({
      from: '2026-09-26',
      to: '2026-09-26',
    });
  });

  it('finds the coming weekend from a Friday', () => {
    expect(resolveDateRange(state({ datePreset: 'weekend' }), TODAY, 5)).toEqual({
      from: '2026-09-26',
      to: '2026-09-27',
    });
  });

  it('keeps this weekend when asked on a Saturday', () => {
    expect(resolveDateRange(state({ datePreset: 'weekend' }), '2026-09-26', 6)).toEqual({
      from: '2026-09-26',
      to: '2026-09-27',
    });
  });

  it('keeps this weekend when asked on a Sunday, without reaching backwards', () => {
    expect(resolveDateRange(state({ datePreset: 'weekend' }), '2026-09-27', 0)).toEqual({
      from: '2026-09-27',
      to: '2026-09-27',
    });
  });

  it('spans seven days including today for next7', () => {
    expect(resolveDateRange(state({ datePreset: 'next7' }), TODAY, TODAY_WEEKDAY)).toEqual({
      from: '2026-09-25',
      to: '2026-10-01',
    });
  });

  it('swaps a reversed custom range', () => {
    const r = resolveDateRange(
      state({ datePreset: 'custom', from: '2026-10-10', to: '2026-10-01' }),
      TODAY,
      TODAY_WEEKDAY,
    );
    expect(r).toEqual({ from: '2026-10-01', to: '2026-10-10' });
  });
});

describe('date predicate', () => {
  it('keeps a multi-day event that overlaps the range', () => {
    const e = ev({ start: et('2026-09-24', '10:00'), end: et('2026-09-28', '10:00') });
    const p = buildPredicates(state({ datePreset: 'today' }), ctx);
    expect(p.date(e)).toBe(true);
  });

  it('excludes a day outside the range', () => {
    const e = ev({ start: et('2026-10-05', '10:00') });
    expect(buildPredicates(state({ datePreset: 'next7' }), ctx).date(e)).toBe(false);
  });
});

describe('time of day', () => {
  const at = (hhmm: string) => ev({ start: et('2026-09-26', hhmm) });

  it('passes everything when no chip is selected', () => {
    const p = buildPredicates(state(), ctx);
    expect(p.time(at('03:00'))).toBe(true);
    expect(p.time(at('14:00'))).toBe(true);
  });

  it('matches a single chip window', () => {
    const p = buildPredicates(state({ timesOfDay: ['morning'] }), ctx);
    expect(p.time(at('06:00'))).toBe(true);
    expect(p.time(at('11:59'))).toBe(true);
    expect(p.time(at('12:00'))).toBe(false);
    expect(p.time(at('05:59'))).toBe(false);
  });

  it('unions several chips', () => {
    const p = buildPredicates(state({ timesOfDay: ['morning', 'evening'] }), ctx);
    expect(p.time(at('08:00'))).toBe(true);
    expect(p.time(at('14:00'))).toBe(false);
    expect(p.time(at('19:00'))).toBe(true);
  });

  it('wraps late past midnight', () => {
    const p = buildPredicates(state({ timesOfDay: ['late'] }), ctx);
    expect(p.time(at('21:00'))).toBe(true);
    expect(p.time(at('23:59'))).toBe(true);
    expect(p.time(at('00:30'))).toBe(true);
    expect(p.time(at('05:59'))).toBe(true);
    expect(p.time(at('06:00'))).toBe(false);
    expect(p.time(at('20:59'))).toBe(false);
  });

  it('applies a raw legacy HH:MM window', () => {
    const p = buildPredicates(state({ timeStart: '17:00', timeEnd: '21:00' }), ctx);
    expect(p.time(at('18:00'))).toBe(true);
    expect(p.time(at('16:59'))).toBe(false);
    expect(p.time(at('21:00'))).toBe(false);
  });

  it('maps a raw window back to its chip', () => {
    expect(chipForWindow('06:00', '12:00')).toBe('morning');
    expect(chipForWindow('17:00', '21:00')).toBe('evening');
    expect(chipForWindow('09:00', '17:00')).toBeNull();
    expect(chipForWindow(null, null)).toBeNull();
  });
});

describe('outside work hours', () => {
  const p = buildPredicates(state({ outsideWorkHours: true }), ctx);

  it('hides a weekday event inside 9 to 5', () => {
    expect(p.time(ev({ start: et('2026-09-28', '10:00') }))).toBe(false); // Monday
    expect(p.time(ev({ start: et('2026-09-28', '16:59') }))).toBe(false);
  });

  it('keeps a weekday event outside 9 to 5', () => {
    expect(p.time(ev({ start: et('2026-09-28', '08:59') }))).toBe(true);
    expect(p.time(ev({ start: et('2026-09-28', '17:00') }))).toBe(true);
  });

  it('keeps a weekend event at any hour', () => {
    expect(p.time(ev({ start: et('2026-09-26', '12:00') }))).toBe(true); // Saturday
    expect(p.time(ev({ start: et('2026-09-27', '12:00') }))).toBe(true); // Sunday
  });

  it('judges the weekday in Eastern, not UTC', () => {
    // 2026-09-26T00:30Z is Friday 8:30 PM Eastern, outside work hours either way.
    expect(p.time(ev({ start: '2026-09-26T00:30:00+00:00' }))).toBe(true);
    // 2026-09-28T16:00Z is Monday noon Eastern and must be hidden.
    expect(p.time(ev({ start: '2026-09-28T16:00:00+00:00' }))).toBe(false);
  });
});

describe('sectors', () => {
  const tagged = (tags: string[]) => ev({ start: et('2026-09-26', '10:00'), tags });

  it('passes everything when nothing is selected', () => {
    const p = buildPredicates(state(), ctx);
    expect(p.sector(tagged(['Community']))).toBe(true);
  });

  it('matches any selected sector', () => {
    const p = buildPredicates(state({ sectors: ['technology'] }), ctx);
    expect(p.sector(tagged(['Python']))).toBe(true);
    expect(p.sector(tagged(['Religion']))).toBe(false);
  });

  it('treats a multi-sector event as matching either', () => {
    const p = buildPredicates(state({ sectors: ['faith'] }), ctx);
    expect(p.sector(tagged(['Python', 'Religion']))).toBe(true);
  });

  it('switches to lens categories for a non-default lens', () => {
    const p = buildPredicates(
      state({ lens: 'tech_only', lensCategories: ['software-development'] }),
      ctx,
    );
    expect(p.sector(tagged(['Python']))).toBe(true);
    expect(p.sector(tagged(['AI']))).toBe(false);
  });
});

describe('distance', () => {
  it('measures real-world distances', () => {
    const innerHarbor = { lat: 39.2854, lng: -76.6103 };
    const towson = { lat: 39.4015, lng: -76.6019 };
    expect(haversineMiles(innerHarbor, towson)).toBeGreaterThan(7);
    expect(haversineMiles(innerHarbor, towson)).toBeLessThan(9);
    expect(haversineMiles(innerHarbor, innerHarbor)).toBeCloseTo(0, 6);
  });

  it('passes everything when no origin is set', () => {
    expect(buildPredicates(state(), ctx).distance(ev({ start: et('2026-09-26', '10:00'), coords: null }))).toBe(true);
  });

  it('keeps what is inside the radius and drops what is outside', () => {
    const p = buildPredicates(
      state({ nearCoords: { lat: 39.2854, lng: -76.6103 }, radiusMiles: 5 }),
      ctx,
    );
    expect(p.distance(ev({ start: et('2026-09-26', '10:00'), coords: { lat: 39.29, lng: -76.61 } }))).toBe(true);
    expect(p.distance(ev({ start: et('2026-09-26', '10:00'), coords: { lat: 39.4015, lng: -76.6019 } }))).toBe(false);
  });

  it('hides events with no coordinates while distance is on', () => {
    const p = buildPredicates(
      state({ nearCoords: { lat: 39.2854, lng: -76.6103 }, radiusMiles: 50 }),
      ctx,
    );
    expect(p.distance(ev({ start: et('2026-09-26', '10:00'), coords: null }))).toBe(false);
  });
});

describe('grouping and counting', () => {
  const events = [
    ev({ start: et('2026-09-26', '10:00'), tags: ['Python'] }),
    ev({ start: et('2026-09-26', '18:00'), tags: ['Religion'] }),
    ev({ start: et('2026-09-27', '09:00'), tags: ['Python', 'Religion'], coords: null }),
  ];

  it('groups chronological events into day sections', () => {
    const groups = groupByDay(events);
    expect(groups.map((g) => g.dayKey)).toEqual(['2026-09-26', '2026-09-27']);
    expect(groups[0]!.events).toHaveLength(2);
  });

  it('counts per day', () => {
    expect(countByDay(events).get('2026-09-26')).toBe(2);
    expect(countByDay(events).get('2026-09-27')).toBe(1);
  });

  it('counts per sector, allowing an event in two', () => {
    const c = countBySector(events);
    expect(c.get('technology')).toBe(2);
    expect(c.get('faith')).toBe(2);
  });

  it('counts what the map can place', () => {
    expect(countMappable(events)).toBe(2);
  });
});
