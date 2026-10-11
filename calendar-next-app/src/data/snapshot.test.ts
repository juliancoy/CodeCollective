import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';
import { countByDay, countBySector, countMappable } from './filters';
import { newestScrape, normalizeEvents, organizerCount } from './normalize';
import type { RawEvent } from './types';

/**
 * Integrity check against the committed snapshot of the live Baltimore feed.
 *
 * This replaces the throwaway debug route the brief suggested: it proves the
 * pipeline reproduces the real data profile, and it keeps proving it. `now` is
 * pinned so the numbers stay fixed as real time moves on.
 */
const ET = 'America/New_York';
const NOW = new Date('2026-09-25T16:00:00Z'); // Friday noon Eastern, when the snapshot was taken

const snapshotPath = path.join(process.cwd(), 'public', 'snapshot', 'baltimore.json');
const rows = JSON.parse(fs.readFileSync(snapshotPath, 'utf8')) as RawEvent[];
const events = normalizeEvents(rows, { tz: ET, now: NOW });

describe('the committed Baltimore snapshot', () => {
  it('is the feed we profiled, 1,695 rows', () => {
    expect(rows).toHaveLength(1695);
  });

  it('keeps every occurrence, losing none to a shared upstream id', () => {
    // 18 time.ly ids are reused across a whole recurring series. Keying on the
    // id alone collapsed 161 real events out of the calendar.
    expect(new Set(events.map((e) => e.key)).size).toBe(events.length);
    expect(events).toHaveLength(1695);
  });

  it('normalizes without losing rows to parse errors', () => {
    // The only rows dropped are ones that had already finished by NOW.
    const finished = rows.filter((r) => {
      const start = new Date(r.startDate);
      const end = r.endTime || r.endDate ? new Date((r.endTime ?? r.endDate)!) : null;
      const finish = end && end > start ? end : new Date(start.getTime() + 2 * 3600_000);
      return finish < NOW;
    });
    expect(events.length).toBe(rows.length - finished.length);
    expect(events.length).toBeGreaterThan(1600);
  });

  it('reports 104 organizers, the 105 raw names with the two Luma handles merged', () => {
    // The feed carries 105 distinct organizer strings, two of which are
    // internal handles ("Luma User cTlmPNsi6jHYweP"). Both now display as
    // "Independent organizer", so they count once.
    expect(organizerCount(events)).toBe(104);
    expect(events.some((e) => /^Luma User/i.test(e.orgName))).toBe(false);
    expect(events.some((e) => e.orgName === 'Independent organizer')).toBe(true);
  });

  it('puts 105 events on Saturday 26 September, the busiest day', () => {
    const byDay = countByDay(events);
    expect(byDay.get('2026-09-26')).toBe(105);
    const busiest = [...byDay.entries()].sort((a, b) => b[1] - a[1])[0]!;
    expect(busiest[0]).toBe('2026-09-26');
  });

  it('matches the per-day counts for the first two weeks', () => {
    const byDay = countByDay(events);
    // Taken from the live feed on 25 September 2026.
    const expected: Record<string, number> = {
      '2026-09-25': 39,
      '2026-09-26': 105,
      '2026-09-27': 38,
      '2026-09-28': 31,
      '2026-09-29': 39,
      '2026-09-30': 43,
      '2026-10-01': 34,
      '2026-10-02': 23,
      '2026-10-03': 26,
      '2026-10-04': 18,
      '2026-10-05': 19,
      '2026-10-06': 15,
      '2026-10-07': 30,
      '2026-10-08': 19,
    };
    for (const [day, count] of Object.entries(expected)) {
      expect(byDay.get(day), `count for ${day}`).toBe(count);
    }
  });

  it('reproduces the sector distribution, including Technology at 4%', () => {
    const bySector = countBySector(events);
    // Sector counts are computed over the whole feed, so they are unaffected
    // by the handful of rows that had already finished.
    const all = normalizeEvents(rows, { tz: ET, now: new Date('2000-01-01T00:00:00Z') });
    const full = countBySector(all);
    expect(full.get('culture')).toBe(824);
    expect(full.get('economics')).toBe(273);
    expect(full.get('politics')).toBe(265);
    expect(full.get('faith')).toBe(265);
    expect(full.get('government')).toBe(233);
    expect(full.get('technology')).toBe(73);
    expect(full.get('finance')).toBe(25);
    // Technology really is a small slice, which is why the rail leads with it.
    expect((full.get('technology')! / all.length) * 100).toBeLessThan(5);
    expect(bySector.get('technology')).toBeGreaterThan(60);
  });

  it('places 773 events, the 798 with coordinates less the 25 that are online', () => {
    const all = normalizeEvents(rows, { tz: ET, now: new Date('2000-01-01T00:00:00Z') });
    // 798 rows carry coordinates, but 25 of those name a screen rather than a
    // place, and an online event has nothing to pin.
    expect(countMappable(all)).toBe(773);
    expect(all.filter((e) => e.online)).toHaveLength(70);
    expect(all.filter((e) => e.online && e.coords !== null)).toHaveLength(0);
    // The map note has to account for the rest.
    expect(all.length - countMappable(all)).toBe(922);
  });

  it('cleans the titles that the sources shout', () => {
    // "BLACKBIRD FORUM: Reshaping..." and friends.
    const shouty = events.filter((e) => {
      const letters = [...e.title].filter((c) => /\p{L}/u.test(c));
      if (letters.length < 8) return false;
      return letters.filter((c) => /\p{Lu}/u.test(c)).length / letters.length >= 0.6;
    });
    expect(shouty.map((e) => e.title)).toEqual([]);
  });

  it('gives every event two initials for its avatar', () => {
    for (const e of events) {
      expect(e.initials.length).toBeGreaterThan(0);
      expect(e.initials.length).toBeLessThanOrEqual(2);
    }
  });

  it('finds no Code Collective featured events, so the strip must handle absence', () => {
    expect(events.filter((e) => e.featured)).toHaveLength(0);
  });

  it('carries 3 cancellations, which stay listed', () => {
    const all = normalizeEvents(rows, { tz: ET, now: new Date('2000-01-01T00:00:00Z') });
    expect(all.filter((e) => e.cancelled)).toHaveLength(3);
  });

  it('has a fresh scrape timestamp for the freshness line', () => {
    const newest = newestScrape(events);
    expect(newest).not.toBeNull();
    expect(newest!.toISOString()).toBe('2026-09-25T12:08:02.924Z');
  });

  it('holds every event to a valid absolute url', () => {
    const bad = events.filter((e) => !/^https?:\/\//.test(e.url));
    expect(bad.map((e) => e.title)).toEqual([]);
  });

  it('never assigns more sectors than the map defines', () => {
    for (const e of events) {
      expect(e.sectors.length).toBeGreaterThan(0);
      expect(e.sectors.length).toBeLessThanOrEqual(13);
      expect(e.sectors).toContain(e.primarySector);
    }
  });

  it('keeps every event in chronological order', () => {
    for (let i = 1; i < events.length; i++) {
      expect(events[i]!.start.getTime()).toBeGreaterThanOrEqual(events[i - 1]!.start.getTime());
    }
  });
});
