import { describe, expect, it } from 'vitest';
import { monthModel } from './pipeline';
import { normalizeEvent } from './normalize';
import type { CalEvent, RawEvent } from './types';

const ET = 'America/New_York';
const NOW = new Date('2026-09-27T12:00:00-04:00');

function ev(over: { start: string; title: string; tags?: string[] }): CalEvent {
  const row: RawEvent = {
    name: over.title,
    description: '',
    startDate: over.start,
    url: 'https://example.com/e',
    status: 'ACTIVE',
    location: { name: 'Somewhere', latitude: 39.29, longitude: -76.61 },
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

describe('monthModel previews', () => {
  it('names real events ahead of placeholder titles, whatever the feed order', () => {
    // The broken rows arrive first, which is exactly what happened in the
    // live feed and what filled the grid with timestamps and field labels.
    const cells = monthModel([
      ev({ start: '2026-09-30T09:00:00-04:00', title: '2026-09-30T18:30:00' }),
      ev({ start: '2026-09-30T10:00:00-04:00', title: 'Start Date and Time' }),
      ev({ start: '2026-09-30T18:00:00-04:00', title: 'Dine to Donate' }),
      ev({ start: '2026-09-30T19:00:00-04:00', title: 'Contamination Control Short Course' }),
    ]);

    const cell = cells.get('2026-09-30');
    expect(cell?.preview.map((p) => p.title)).toEqual([
      'Dine to Donate',
      'Contamination Control Short Course',
    ]);
  });

  it('counts every event on the day, including the ones it declined to name', () => {
    const cells = monthModel([
      ev({ start: '2026-09-30T09:00:00-04:00', title: '212 S Bond Street' }),
      ev({ start: '2026-09-30T18:00:00-04:00', title: 'Dine to Donate' }),
    ]);

    // Demoting a title must never quietly drop the event.
    expect(cells.get('2026-09-30')?.count).toBe(2);
  });

  it('still names placeholder titles when a day has nothing better', () => {
    const cells = monthModel([ev({ start: '2026-09-30T09:00:00-04:00', title: 'NEXT' })]);

    // An honest bad title beats an empty cell that implies an empty day.
    expect(cells.get('2026-09-30')?.preview.map((p) => p.title)).toEqual(['Next']);
  });

  it('reads chronologically when nothing is demoted', () => {
    const cells = monthModel([
      ev({ start: '2026-09-30T19:00:00-04:00', title: 'Evening Talk' }),
      ev({ start: '2026-09-30T08:00:00-04:00', title: 'Morning Standup' }),
    ]);

    expect(cells.get('2026-09-30')?.preview.map((p) => p.title)).toEqual([
      'Morning Standup',
      'Evening Talk',
    ]);
  });

  it('tallies the sector mix largest first, for the load bar', () => {
    const cells = monthModel([
      ev({ start: '2026-09-30T09:00:00-04:00', title: 'A', tags: ['Technology'] }),
      ev({ start: '2026-09-30T10:00:00-04:00', title: 'B', tags: ['Technology'] }),
      ev({ start: '2026-09-30T11:00:00-04:00', title: 'C', tags: ['Community'] }),
    ]);

    const load = cells.get('2026-09-30')!.load;
    expect(load[0]!.count).toBe(2);
    expect(load.reduce((n, l) => n + l.count, 0)).toBe(3);
  });
});

describe('monthModel duplicates', () => {
  it('names a repeated title once, then moves to the next event', () => {
    const cells = monthModel([
      ev({ start: '2026-10-01T09:00:00-04:00', title: 'From Crisis to Connection' }),
      ev({ start: '2026-10-01T14:00:00-04:00', title: 'From Crisis to Connection' }),
      ev({ start: '2026-10-01T19:00:00-04:00', title: 'Evening Lecture' }),
    ]);

    expect(cells.get('2026-10-01')?.preview.map((p) => p.title)).toEqual([
      'From Crisis to Connection',
      'Evening Lecture',
    ]);
    // All three still count toward the day.
    expect(cells.get('2026-10-01')?.count).toBe(3);
  });
});
