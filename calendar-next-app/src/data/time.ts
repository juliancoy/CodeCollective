import { TZDate } from '@date-fns/tz';
import type { TimeOfDay } from './types';

/**
 * Everything here is zone-explicit on purpose. 97% of upstream `startDate`
 * values carry a +00:00 offset, so the only correct way to render a wall clock
 * is to convert into the city's zone. Nothing may rely on the machine's zone.
 */

const dayKeyFmt = new Map<string, Intl.DateTimeFormat>();
function fmtDayKey(tz: string): Intl.DateTimeFormat {
  let f = dayKeyFmt.get(tz);
  if (!f) {
    f = new Intl.DateTimeFormat('en-CA', {
      timeZone: tz,
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    });
    dayKeyFmt.set(tz, f);
  }
  return f;
}

/** YYYY-MM-DD as the calendar reads in `tz`. */
export function dayKeyOf(date: Date, tz: string): string {
  return fmtDayKey(tz).format(date);
}

const partsFmt = new Map<string, Intl.DateTimeFormat>();
function fmtParts(tz: string): Intl.DateTimeFormat {
  let f = partsFmt.get(tz);
  if (!f) {
    f = new Intl.DateTimeFormat('en-US', {
      timeZone: tz,
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
      weekday: 'short',
    });
    partsFmt.set(tz, f);
  }
  return f;
}

type ZoneParts = { hour: number; minute: number; weekday: string };

/** Wall-clock hour, minute and weekday in `tz`. */
export function zoneParts(date: Date, tz: string): ZoneParts {
  const parts = fmtParts(tz).formatToParts(date);
  const get = (t: string) => parts.find((p) => p.type === t)?.value ?? '';
  // Some engines render midnight as "24" under hour12:false.
  const hour = Number(get('hour')) % 24;
  return { hour, minute: Number(get('minute')), weekday: get('weekday') };
}

export function hourInZone(date: Date, tz: string): number {
  return zoneParts(date, tz).hour;
}

const WD = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

/** 0 = Sunday. */
export function weekdayInZone(date: Date, tz: string): number {
  const i = WD.indexOf(zoneParts(date, tz).weekday);
  return i === -1 ? 0 : i;
}

/** True when the date falls Monday to Friday in `tz`. */
export function isWeekdayInZone(date: Date, tz: string): boolean {
  const d = weekdayInZone(date, tz);
  return d >= 1 && d <= 5;
}

/** Minutes since midnight in `tz`. */
export function minutesInZone(date: Date, tz: string): number {
  const { hour, minute } = zoneParts(date, tz);
  return hour * 60 + minute;
}

/**
 * Intl.formatToParts costs a microsecond or two, which is several milliseconds
 * across 1,695 events on every keystroke. Event Date objects are stable for the
 * life of a city's payload, so the answer is cached against them.
 */
const clockCache = new WeakMap<Date, Map<string, { minutes: number; weekday: number }>>();

function clockFor(date: Date, tz: string): { minutes: number; weekday: number } {
  let byZone = clockCache.get(date);
  if (!byZone) {
    byZone = new Map();
    clockCache.set(date, byZone);
  }
  let hit = byZone.get(tz);
  if (!hit) {
    const { hour, minute, weekday } = zoneParts(date, tz);
    const wd = WD.indexOf(weekday);
    hit = { minutes: hour * 60 + minute, weekday: wd === -1 ? 0 : wd };
    byZone.set(tz, hit);
  }
  return hit;
}

export function minutesInZoneCached(date: Date, tz: string): number {
  return clockFor(date, tz).minutes;
}

export function weekdayInZoneCached(date: Date, tz: string): number {
  return clockFor(date, tz).weekday;
}

/** A Date at 00:00 of `dayKey` in `tz`. DST-safe via TZDate. */
export function startOfDayKey(dayKey: string, tz: string): Date {
  const [y, m, d] = dayKey.split('-').map(Number);
  return new Date(new TZDate(y ?? 1970, (m ?? 1) - 1, d ?? 1, tz).getTime());
}

/** A Date at 23:59:59.999 of `dayKey` in `tz`. */
export function endOfDayKey(dayKey: string, tz: string): Date {
  const [y, m, d] = dayKey.split('-').map(Number);
  return new Date(
    new TZDate(y ?? 1970, (m ?? 1) - 1, d ?? 1, 23, 59, 59, 999, tz).getTime(),
  );
}

/** Shift a day key by whole calendar days. */
export function addDaysToKey(dayKey: string, days: number): string {
  const [y, m, d] = dayKey.split('-').map(Number);
  // UTC arithmetic on a pure calendar date never meets a DST boundary.
  const dt = new Date(Date.UTC(y ?? 1970, (m ?? 1) - 1, (d ?? 1) + days));
  const mm = String(dt.getUTCMonth() + 1).padStart(2, '0');
  const dd = String(dt.getUTCDate()).padStart(2, '0');
  return dt.getUTCFullYear() + '-' + mm + '-' + dd;
}

/** `count` consecutive day keys starting at `startKey`. */
export function dayKeyRange(startKey: string, count: number): string[] {
  const out: string[] = [];
  for (let i = 0; i < count; i++) out.push(addDaysToKey(startKey, i));
  return out;
}

/** Whole calendar days from `a` to `b`. */
export function diffDayKeys(a: string, b: string): number {
  const p = (k: string) => {
    const [y, m, d] = k.split('-').map(Number);
    return Date.UTC(y ?? 1970, (m ?? 1) - 1, d ?? 1);
  };
  return Math.round((p(b) - p(a)) / 86_400_000);
}

/* ---------------- formatting ---------------- */

const timeFmt = new Map<string, Intl.DateTimeFormat>();

/** "5:30 PM" */
export function formatTime(date: Date, tz: string): string {
  let f = timeFmt.get(tz);
  if (!f) {
    f = new Intl.DateTimeFormat('en-US', { timeZone: tz, hour: 'numeric', minute: '2-digit' });
    timeFmt.set(tz, f);
  }
  return f.format(date);
}

function timeNoMeridiem(date: Date, tz: string): string {
  return formatTime(date, tz).replace(/\s?[AP]M$/i, '');
}

function meridiem(date: Date, tz: string): string {
  return formatTime(date, tz).match(/[AP]M$/i)?.[0] ?? '';
}

/** "6:00 to 9:00 PM", collapsing a shared meridiem. */
export function formatTimeRange(start: Date, end: Date | null, tz: string): string {
  if (!end) return formatTime(start, tz);
  if (meridiem(start, tz) === meridiem(end, tz)) {
    return timeNoMeridiem(start, tz) + ' to ' + formatTime(end, tz);
  }
  return formatTime(start, tz) + ' to ' + formatTime(end, tz);
}

const longDayFmt = new Map<string, Intl.DateTimeFormat>();

/** "Saturday, September 26" */
export function formatLongDay(dayKey: string, tz: string): string {
  let f = longDayFmt.get(tz);
  if (!f) {
    f = new Intl.DateTimeFormat('en-US', {
      timeZone: tz,
      weekday: 'long',
      month: 'long',
      day: 'numeric',
    });
    longDayFmt.set(tz, f);
  }
  return f.format(startOfDayKey(dayKey, tz));
}

/** "Sat, Sep 26" */
export function formatShortDay(dayKey: string, tz: string): string {
  return new Intl.DateTimeFormat('en-US', {
    timeZone: tz,
    weekday: 'short',
    month: 'short',
    day: 'numeric',
  }).format(startOfDayKey(dayKey, tz));
}

/** "Today", "Tomorrow", or "Saturday, September 26". */
export function formatDayHeader(dayKey: string, todayKey: string, tz: string): string {
  const delta = diffDayKeys(todayKey, dayKey);
  if (delta === 0) return 'Today';
  if (delta === 1) return 'Tomorrow';
  return formatLongDay(dayKey, tz);
}

/** Weekday, date numeral, and month name on the first of a month. */
export function tideLabels(
  dayKey: string,
  tz: string,
): { weekday: string; numeral: string; month: string | null } {
  const d = startOfDayKey(dayKey, tz);
  const weekday = new Intl.DateTimeFormat('en-US', { timeZone: tz, weekday: 'short' }).format(d);
  const numeral = String(Number(dayKey.slice(8, 10)));
  const month =
    dayKey.slice(8, 10) === '01'
      ? new Intl.DateTimeFormat('en-US', { timeZone: tz, month: 'short' }).format(d)
      : null;
  return { weekday, numeral, month };
}

/** "3 hours ago", "in 3 hours", "just now". */
export function relativeTime(date: Date, now: Date = new Date()): string {
  const secs = Math.round((date.getTime() - now.getTime()) / 1000);
  const abs = Math.abs(secs);
  const rtf = new Intl.RelativeTimeFormat('en-US', { numeric: 'auto' });
  if (abs < 60) return secs <= 0 ? 'just now' : 'in less than a minute';
  const units: Array<[Intl.RelativeTimeFormatUnit, number]> = [
    ['minute', 60],
    ['hour', 3600],
    ['day', 86_400],
    ['month', 2_592_000],
    ['year', 31_536_000],
  ];
  let chosen: [Intl.RelativeTimeFormatUnit, number] = units[0]!;
  for (const u of units) if (abs >= u[1]) chosen = u;
  return rtf.format(Math.round(secs / chosen[1]), chosen[0]);
}

/** Which of the four day parts a moment falls in. Before 6am counts as Late. */
export function timeOfDayOf(date: Date, tz: string): TimeOfDay {
  const h = hourInZone(date, tz);
  if (h >= 6 && h < 12) return 'morning';
  if (h >= 12 && h < 17) return 'afternoon';
  if (h >= 17 && h < 21) return 'evening';
  return 'late';
}

export const TIME_OF_DAY_LABEL: Record<TimeOfDay, string> = {
  morning: 'Morning',
  afternoon: 'Afternoon',
  evening: 'Evening',
  late: 'Late',
};

export const TIME_OF_DAY_ORDER: TimeOfDay[] = ['morning', 'afternoon', 'evening', 'late'];

/** The clock window each chip stands for, in minutes since midnight. */
export const TIME_OF_DAY_WINDOW: Record<TimeOfDay, { from: number; to: number }> = {
  morning: { from: 6 * 60, to: 12 * 60 },
  afternoon: { from: 12 * 60, to: 17 * 60 },
  evening: { from: 17 * 60, to: 21 * 60 },
  // Late wraps midnight: 21:00-24:00 plus 00:00-06:00.
  late: { from: 21 * 60, to: 24 * 60 },
};

/** True when now sits inside the event. Events with no end run 2 hours. */
export function isHappeningNow(start: Date, end: Date | null, now: Date): boolean {
  const finish = end ?? new Date(start.getTime() + 2 * 3600_000);
  return now >= start && now <= finish;
}

/**
 * The span an event actually occupies.
 *
 * An all-day listing runs for its whole day, not the two hours a timed event
 * with no end is given. Without this, every date-only listing counted as
 * "happening now" between midnight and 2 a.m. and as finished for the rest of
 * the day it is actually on.
 */
export function eventWindow(
  ev: {
    start: Date;
    end: Date | null;
    allDay: boolean;
    dayKey: string;
    endDayKey: string | null;
  },
  tz: string,
): { from: Date; to: Date } {
  if (ev.allDay) {
    return {
      from: startOfDayKey(ev.dayKey, tz),
      to: endOfDayKey(ev.endDayKey ?? ev.dayKey, tz),
    };
  }
  return { from: ev.start, to: ev.end ?? new Date(ev.start.getTime() + 2 * 3600_000) };
}

/** Whether the event is running at `now`, honouring all-day spans. */
export function isLive(
  ev: Parameters<typeof eventWindow>[0],
  tz: string,
  now: Date,
): boolean {
  const w = eventWindow(ev, tz);
  return now >= w.from && now <= w.to;
}

/**
 * "In 3 hours", "Happening now", or null when it is further out than a day.
 * All-day listings are measured against their whole day.
 */
export function statusChip(
  ev: Parameters<typeof eventWindow>[0],
  tz: string,
  now: Date = new Date(),
): string | null {
  const w = eventWindow(ev, tz);
  if (now >= w.from && now <= w.to) return 'Happening now';
  if (now > w.to) return null;
  const hrs = (w.from.getTime() - now.getTime()) / 3600_000;
  if (hrs <= 24) return relativeTime(w.from, now).replace(/^in /, 'In ');
  return null;
}

/**
 * Parse a feed timestamp into a real instant.
 *
 * The feed ships four shapes for these fields, and 1,422 of 1,695 rows use
 * `YYYY-MM-DD HH:MM:SS.ffffff` with no offset at all. `new Date()` hands those
 * to implementation-specific parsing, which in V8 means the *viewer's* local
 * zone, so the same row would resolve to a different instant in Denver than in
 * Baltimore. Anything without an explicit offset is read in `assumeZone`.
 */
export function parseInstant(value: string | null | undefined, assumeZone: string): Date | null {
  if (!value) return null;
  const raw = String(value).trim();
  if (raw === '') return null;

  // An explicit offset or a Z makes the string unambiguous.
  if (/(?:Z|[+-]\d{2}:?\d{2})$/.test(raw)) {
    const d = new Date(raw.replace(' ', 'T'));
    return Number.isFinite(d.getTime()) ? d : null;
  }

  const m =
    /^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})(?::(\d{2}))?(?:\.(\d{1,6}))?$/.exec(raw);
  if (m) {
    const ms = m[7] ? Number(m[7].slice(0, 3).padEnd(3, '0')) : 0;
    const d = new TZDate(
      Number(m[1]),
      Number(m[2]) - 1,
      Number(m[3]),
      Number(m[4]),
      Number(m[5]),
      Number(m[6] ?? 0),
      ms,
      assumeZone,
    );
    return Number.isFinite(d.getTime()) ? new Date(d.getTime()) : null;
  }

  // A bare date, e.g. "2026-09-25".
  const dateOnly = /^(\d{4})-(\d{2})-(\d{2})$/.exec(raw);
  if (dateOnly) return startOfDayKey(raw, assumeZone);

  const fallback = new Date(raw);
  return Number.isFinite(fallback.getTime()) ? fallback : null;
}

/**
 * The zone the scrapers run in. Every `scrapeTime` that carries an offset uses
 * -04:00, so offset-less ones are read as Eastern too. This keeps the
 * freshness line identical for every visitor, whatever zone they are in.
 */
export const FEED_ZONE = 'America/New_York';

/** The viewer's own zone, for the "show in my time" switch. */
export function viewerZone(): string {
  return Intl.DateTimeFormat().resolvedOptions().timeZone;
}

/** A short label for a zone, e.g. "EDT". */
export function zoneAbbrev(date: Date, tz: string): string {
  const p = new Intl.DateTimeFormat('en-US', { timeZone: tz, timeZoneName: 'short' })
    .formatToParts(date)
    .find((x) => x.type === 'timeZoneName');
  return p?.value ?? tz;
}
