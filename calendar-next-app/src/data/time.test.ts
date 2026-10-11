import { describe, expect, it } from 'vitest';
import {
  addDaysToKey,
  dayKeyOf,
  dayKeyRange,
  diffDayKeys,
  endOfDayKey,
  formatDayHeader,
  formatTime,
  formatTimeRange,
  eventWindow,
  isHappeningNow,
  isLive,
  isWeekdayInZone,
  minutesInZone,
  relativeTime,
  startOfDayKey,
  statusChip,
  tideLabels,
  timeOfDayOf,
  weekdayInZone,
} from './time';

const ET = 'America/New_York';
const HI = 'Pacific/Honolulu';

describe('dayKeyOf', () => {
  it('uses the city zone, not the machine zone', () => {
    // 97% of upstream rows carry +00:00, so this is the common case.
    expect(dayKeyOf(new Date('2026-09-25T12:00:00+00:00'), ET)).toBe('2026-09-25');
  });

  it('rolls a late-evening UTC stamp back to the previous Eastern day', () => {
    // Midnight UTC on the 26th is 8pm Eastern on the 25th. 138 rows look like this.
    expect(dayKeyOf(new Date('2026-09-26T00:00:00+00:00'), ET)).toBe('2026-09-25');
  });

  it('honours a zone far from Eastern', () => {
    expect(dayKeyOf(new Date('2026-09-26T05:00:00+00:00'), HI)).toBe('2026-09-25');
  });
});

describe('daylight saving, 1 November 2026', () => {
  it('places 1:30 AM EDT and the repeated 1:30 AM EST on the same day', () => {
    expect(dayKeyOf(new Date('2026-11-01T05:30:00Z'), ET)).toBe('2026-11-01');
    expect(dayKeyOf(new Date('2026-11-01T06:30:00Z'), ET)).toBe('2026-11-01');
    // Both render as the same wall clock, which is genuinely what happened.
    expect(formatTime(new Date('2026-11-01T05:30:00Z'), ET)).toBe('1:30 AM');
    expect(formatTime(new Date('2026-11-01T06:30:00Z'), ET)).toBe('1:30 AM');
  });

  it('keeps 11 PM on 31 October on the October day', () => {
    expect(dayKeyOf(new Date('2026-11-01T03:00:00Z'), ET)).toBe('2026-10-31');
  });

  it('starts the day at midnight EDT and ends it at 23:59 EST, so it runs 25 hours', () => {
    const start = startOfDayKey('2026-11-01', ET);
    const end = endOfDayKey('2026-11-01', ET);
    expect(start.toISOString()).toBe('2026-11-01T04:00:00.000Z');
    expect(end.toISOString()).toBe('2026-11-02T04:59:59.999Z');
    const hours = (end.getTime() - start.getTime()) / 3_600_000;
    expect(hours).toBeCloseTo(25, 3);
  });

  it('shifts day keys across the change without drifting an hour', () => {
    expect(addDaysToKey('2026-10-31', 1)).toBe('2026-11-01');
    expect(addDaysToKey('2026-11-01', 1)).toBe('2026-11-02');
    expect(diffDayKeys('2026-10-30', '2026-11-03')).toBe(4);
  });
});

describe('daylight saving, 8 March 2026 (spring forward)', () => {
  it('skips the 2 AM hour without losing the day', () => {
    expect(dayKeyOf(new Date('2026-03-08T06:30:00Z'), ET)).toBe('2026-03-08');
    expect(formatTime(new Date('2026-03-08T06:30:00Z'), ET)).toBe('1:30 AM');
    // 07:30Z is 3:30 AM EDT; 2:30 AM never existed.
    expect(formatTime(new Date('2026-03-08T07:30:00Z'), ET)).toBe('3:30 AM');
  });

  it('runs 23 hours', () => {
    const start = startOfDayKey('2026-03-08', ET);
    const end = endOfDayKey('2026-03-08', ET);
    const hours = (end.getTime() - start.getTime()) / 3_600_000;
    expect(hours).toBeCloseTo(23, 3);
  });
});

describe('day key arithmetic', () => {
  it('crosses month and year boundaries', () => {
    expect(addDaysToKey('2026-09-30', 1)).toBe('2026-10-01');
    expect(addDaysToKey('2026-12-31', 1)).toBe('2027-01-01');
    expect(addDaysToKey('2026-03-01', -1)).toBe('2026-02-28');
  });

  it('produces a contiguous range', () => {
    expect(dayKeyRange('2026-09-25', 4)).toEqual([
      '2026-09-25',
      '2026-09-26',
      '2026-09-27',
      '2026-09-28',
    ]);
  });
});

describe('formatting', () => {
  it('collapses a shared meridiem in a range', () => {
    const start = new Date('2026-09-26T22:00:00Z'); // 6:00 PM ET
    const end = new Date('2026-09-27T01:00:00Z'); // 9:00 PM ET
    expect(formatTimeRange(start, end, ET)).toBe('6:00 to 9:00 PM');
  });

  it('keeps both meridiems when they differ', () => {
    const start = new Date('2026-09-26T15:00:00Z'); // 11:00 AM ET
    const end = new Date('2026-09-26T19:00:00Z'); // 3:00 PM ET
    expect(formatTimeRange(start, end, ET)).toBe('11:00 AM to 3:00 PM');
  });

  it('shows only the start when there is no end', () => {
    expect(formatTimeRange(new Date('2026-09-26T22:00:00Z'), null, ET)).toBe('6:00 PM');
  });

  it('labels today and tomorrow, then falls back to the long form', () => {
    expect(formatDayHeader('2026-09-25', '2026-09-25', ET)).toBe('Today');
    expect(formatDayHeader('2026-09-26', '2026-09-25', ET)).toBe('Tomorrow');
    expect(formatDayHeader('2026-09-27', '2026-09-25', ET)).toBe('Sunday, September 27');
  });

  it('shows the month name only on the first of a month', () => {
    expect(tideLabels('2026-09-26', ET)).toEqual({ weekday: 'Sat', numeral: '26', month: null });
    expect(tideLabels('2026-10-01', ET)).toEqual({ weekday: 'Thu', numeral: '1', month: 'Oct' });
  });

  it('describes freshness in plain language', () => {
    const now = new Date('2026-09-25T12:00:00Z');
    expect(relativeTime(new Date('2026-09-25T09:00:00Z'), now)).toBe('3 hours ago');
    expect(relativeTime(new Date('2026-09-25T15:00:00Z'), now)).toBe('in 3 hours');
  });
});

describe('zone-aware clock helpers', () => {
  it('reads minutes since midnight in the city zone', () => {
    expect(minutesInZone(new Date('2026-09-25T12:00:00Z'), ET)).toBe(8 * 60);
    expect(minutesInZone(new Date('2026-09-26T00:00:00Z'), ET)).toBe(20 * 60);
  });

  it('reads the weekday in the city zone', () => {
    // Midnight UTC Saturday is still Friday evening in Baltimore.
    expect(weekdayInZone(new Date('2026-09-26T00:00:00Z'), ET)).toBe(5);
    expect(isWeekdayInZone(new Date('2026-09-26T00:00:00Z'), ET)).toBe(true);
    expect(isWeekdayInZone(new Date('2026-09-26T16:00:00Z'), ET)).toBe(false);
  });

  it('buckets the four day parts, with pre-dawn counting as late', () => {
    const at = (h: number) => new Date(`2026-09-25T${String(h).padStart(2, '0')}:00:00-04:00`);
    expect(timeOfDayOf(at(7), ET)).toBe('morning');
    expect(timeOfDayOf(at(13), ET)).toBe('afternoon');
    expect(timeOfDayOf(at(18), ET)).toBe('evening');
    expect(timeOfDayOf(at(22), ET)).toBe('late');
    expect(timeOfDayOf(at(2), ET)).toBe('late');
    expect(timeOfDayOf(at(5), ET)).toBe('late');
    expect(timeOfDayOf(at(6), ET)).toBe('morning');
  });
});

describe('status', () => {
  const timed = {
    start: new Date('2026-09-25T18:00:00Z'),
    end: new Date('2026-09-25T20:00:00Z'),
    allDay: false,
    dayKey: '2026-09-25',
    endDayKey: null,
  };

  it('detects an event in progress', () => {
    expect(isHappeningNow(timed.start, timed.end, new Date('2026-09-25T19:00:00Z'))).toBe(true);
    expect(statusChip(timed, ET, new Date('2026-09-25T19:00:00Z'))).toBe('Happening now');
  });

  it('treats a timed event with no end as two hours long', () => {
    expect(isHappeningNow(timed.start, null, new Date('2026-09-25T19:30:00Z'))).toBe(true);
    expect(isHappeningNow(timed.start, null, new Date('2026-09-25T20:30:00Z'))).toBe(false);
  });

  it('counts down inside a day and stays quiet beyond it', () => {
    expect(statusChip(timed, ET, new Date('2026-09-25T15:00:00Z'))).toBe('In 3 hours');
    expect(statusChip(timed, ET, new Date('2026-09-20T15:00:00Z'))).toBeNull();
  });
});

describe('all-day spans', () => {
  const allDay = {
    start: new Date('2026-09-26T04:00:00Z'), // midnight Eastern
    end: null,
    allDay: true,
    dayKey: '2026-09-26',
    endDayKey: null,
  };

  it('runs the whole day, not two hours', () => {
    const w = eventWindow(allDay, ET);
    expect(w.from.toISOString()).toBe('2026-09-26T04:00:00.000Z');
    expect(w.to.toISOString()).toBe('2026-09-27T03:59:59.999Z');
  });

  it('is live at midday, not only just after midnight', () => {
    // The two-hour default made every date-only listing "happening now"
    // between midnight and 2am, and finished for the rest of its own day.
    expect(isLive(allDay, ET, new Date('2026-09-26T04:30:00Z'))).toBe(true);
    expect(isLive(allDay, ET, new Date('2026-09-26T17:00:00Z'))).toBe(true);
    expect(isLive(allDay, ET, new Date('2026-09-27T05:00:00Z'))).toBe(false);
    expect(isLive(allDay, ET, new Date('2026-09-25T20:00:00Z'))).toBe(false);
  });

  it('covers every day of a multi-day span', () => {
    const multi = { ...allDay, endDayKey: '2026-09-30' };
    expect(isLive(multi, ET, new Date('2026-09-28T17:00:00Z'))).toBe(true);
    expect(isLive(multi, ET, new Date('2026-10-01T17:00:00Z'))).toBe(false);
  });

  it('says "Happening now" across the whole day', () => {
    expect(statusChip(allDay, ET, new Date('2026-09-26T17:00:00Z'))).toBe('Happening now');
  });

  it('leaves a timed event unchanged', () => {
    const w = eventWindow(
      {
        start: new Date('2026-09-26T22:00:00Z'),
        end: new Date('2026-09-27T01:00:00Z'),
        allDay: false,
        dayKey: '2026-09-26',
        endDayKey: null,
      },
      ET,
    );
    expect(w.from.toISOString()).toBe('2026-09-26T22:00:00.000Z');
    expect(w.to.toISOString()).toBe('2026-09-27T01:00:00.000Z');
  });
});
