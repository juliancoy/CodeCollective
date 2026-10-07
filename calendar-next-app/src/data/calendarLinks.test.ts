import { describe, expect, it } from 'vitest';
import {
  buildIcs,
  effectiveEnd,
  eventJson,
  googleCalendarUrl,
  googleSubscribeUrl,
  icsFeedUrl,
  icsFilename,
  mapsUrl,
  reportMailto,
  webcalSubscribeUrl,
} from './calendarLinks';
import { normalizeEvent } from './normalize';
import type { CalEvent, RawEvent } from './types';

const ET = 'America/New_York';
const NOW = new Date('2026-09-25T16:00:00Z');

function makeEvent(over: Partial<RawEvent> = {}): CalEvent {
  const row: RawEvent = {
    name: 'Bmore on Rails, September',
    description: 'A monthly Ruby meetup; bring a laptop.',
    // 6:00 PM Eastern on Saturday 26 September.
    startDate: '2026-09-26T22:00:00+00:00',
    endTime: '2026-09-27T01:00:00+00:00',
    url: 'https://luma.com/bmore-on-rails',
    status: 'ACTIVE',
    location: {
      name: 'Spark Baltimore',
      address: '8 Market Pl, Baltimore, MD, 21202',
      city: 'Baltimore',
    },
    scrapeTime: '2026-09-25T04:00:00-04:00',
    tags: ['Ruby'],
    source: 'https://luma.com/bmore-on-rails',
    source_url: 'https://luma.com/bmore-on-rails',
    source_group: 'Bmore on Rails',
    org_name: 'Bmore on Rails',
    orgName: 'Bmore on Rails',
    ...over,
  };
  const ev = normalizeEvent(row, { tz: ET, now: NOW });
  if (!ev) throw new Error('fixture did not normalize');
  return ev;
}

describe('effectiveEnd', () => {
  it('uses the real end when there is one', () => {
    expect(effectiveEnd(makeEvent()).toISOString()).toBe('2026-09-27T01:00:00.000Z');
  });

  it('runs two hours when there is none', () => {
    const ev = makeEvent({ endTime: undefined, endDate: undefined });
    expect(effectiveEnd(ev).toISOString()).toBe('2026-09-27T00:00:00.000Z');
  });
});

describe('googleCalendarUrl', () => {
  const url = new URL(googleCalendarUrl(makeEvent()));

  it('carries the absolute UTC instants for a 6 to 9 PM Eastern event', () => {
    // 6 PM EDT is 22:00Z, 9 PM EDT is 01:00Z the next day.
    expect(url.searchParams.get('dates')).toBe('20260926T220000Z/20260927T010000Z');
  });

  it('carries the title, location and a link back', () => {
    expect(url.searchParams.get('text')).toBe('Bmore on Rails, September');
    expect(url.searchParams.get('location')).toBe(
      'Spark Baltimore, 8 Market Pl, Baltimore, MD, 21202, Baltimore',
    );
    expect(url.searchParams.get('details')).toContain('https://luma.com/bmore-on-rails');
  });

  it('is an action=TEMPLATE render URL', () => {
    expect(url.origin + url.pathname).toBe('https://calendar.google.com/calendar/render');
    expect(url.searchParams.get('action')).toBe('TEMPLATE');
  });

  it('uses date-only stamps for an all-day event', () => {
    const allDay = makeEvent({
      startDate: '2026-09-26T04:00:00+00:00',
      endTime: undefined,
      endDate: undefined,
    });
    expect(allDay.allDay).toBe(true);
    const dates = new URL(googleCalendarUrl(allDay)).searchParams.get('dates')!;
    expect(dates).toMatch(/^\d{8}\/\d{8}$/);
  });
});

describe('buildIcs', () => {
  const ics = buildIcs(makeEvent(), new Date('2026-09-25T16:00:00Z'));

  it('is CRLF-delimited and well-formed', () => {
    expect(ics.startsWith('BEGIN:VCALENDAR\r\n')).toBe(true);
    expect(ics.trimEnd().endsWith('END:VCALENDAR')).toBe(true);
    expect(ics).toContain('VERSION:2.0');
    expect(ics.split('\r\n').length).toBeGreaterThan(10);
  });

  it('writes the same absolute times as the Google link', () => {
    expect(ics).toContain('DTSTART:20260926T220000Z');
    expect(ics).toContain('DTEND:20260927T010000Z');
    expect(ics).toContain('DTSTAMP:20260925T160000Z');
  });

  it('escapes commas and semicolons in text fields', () => {
    expect(ics).toContain('SUMMARY:Bmore on Rails\\, September');
    expect(ics).toContain('meetup\\; bring a laptop');
  });

  it('folds long lines to 75 octets', () => {
    const long = buildIcs(makeEvent({ name: 'A'.repeat(200) }));
    for (const line of long.split('\r\n')) {
      expect(line.length).toBeLessThanOrEqual(75);
    }
  });

  it('carries a stable uid and the location', () => {
    expect(ics).toContain('@codecollective.us');
    expect(ics).toContain('LOCATION:Spark Baltimore');
  });

  it('marks a cancelled event cancelled', () => {
    expect(buildIcs(makeEvent({ status: 'CANCELLED' }))).toContain('STATUS:CANCELLED');
    expect(buildIcs(makeEvent())).not.toContain('STATUS:CANCELLED');
  });

  it('uses VALUE=DATE for an all-day event', () => {
    const allDay = buildIcs(
      makeEvent({ startDate: '2026-09-26T04:00:00+00:00', endTime: undefined, endDate: undefined }),
    );
    expect(allDay).toContain('DTSTART;VALUE=DATE:20260926');
  });
});

describe('filenames and helper links', () => {
  it('slugifies the title for the download', () => {
    expect(icsFilename(makeEvent())).toBe('bmore-on-rails-september.ics');
  });

  it('never produces an empty filename', () => {
    expect(icsFilename(makeEvent({ name: '!!!' }))).toBe('event.ics');
  });

  it('builds a maps search link, or none without a place', () => {
    expect(mapsUrl(makeEvent())).toContain('https://www.google.com/maps/search/?api=1&query=');
    expect(mapsUrl(makeEvent({ location: {} }))).toBeNull();
  });

  it('matches the current site subscription links', () => {
    expect(icsFeedUrl('baltimore')).toBe('https://codecollective.us/baltimore/cc_events.ics');
    expect(webcalSubscribeUrl('baltimore')).toBe('webcal://codecollective.us/baltimore/cc_events.ics');
    expect(googleSubscribeUrl('baltimore')).toBe(
      'https://calendar.google.com/calendar/u/0/r?cid=http://codecollective.us/baltimore/cc_events.ics',
    );
  });

  it('prefills the problem report', () => {
    const m = reportMailto(makeEvent());
    expect(m.startsWith('mailto:julian@codecollective.us')).toBe(true);
    expect(m).toContain('Calendar%20listing%20issue');
  });

  it('serialises dates as ISO in the copied JSON', () => {
    const parsed = JSON.parse(eventJson(makeEvent()));
    expect(parsed.start).toBe('2026-09-26T22:00:00.000Z');
    expect(parsed.end).toBe('2026-09-27T01:00:00.000Z');
    expect(parsed.title).toBe('Bmore on Rails, September');
  });
});
