import type { CalEvent, CityId } from './types';

/** UTC stamp in the basic format both Google and iCalendar accept. */
function toUtcStamp(d: Date): string {
  return d.toISOString().replace(/[-:]/g, '').replace(/\.\d{3}/, '');
}

/** A date-only stamp, for all-day entries. */
function toUtcDate(d: Date): string {
  return d.toISOString().slice(0, 10).replace(/-/g, '');
}

/** Events with no end run for two hours, matching how they are listed. */
export function effectiveEnd(ev: Pick<CalEvent, 'start' | 'end'>): Date {
  return ev.end ?? new Date(ev.start.getTime() + 2 * 3600_000);
}

function placeText(ev: CalEvent): string {
  return [ev.venue, ev.address, ev.locality].filter(Boolean).join(', ');
}

function detailsText(ev: CalEvent): string {
  const lines: string[] = [];
  if (ev.excerpt) lines.push(ev.excerpt);
  lines.push(`Organizer: ${ev.orgName}`);
  lines.push(ev.url);
  lines.push(`Listed by Code Collective from ${ev.sourceGroup}.`);
  return lines.join('\n\n');
}

/** Google Calendar template URL. Times are absolute, so no zone is needed. */
export function googleCalendarUrl(ev: CalEvent): string {
  const end = effectiveEnd(ev);
  const dates = ev.allDay
    ? `${toUtcDate(ev.start)}/${toUtcDate(new Date(end.getTime() + 86_400_000))}`
    : `${toUtcStamp(ev.start)}/${toUtcStamp(end)}`;
  const p = new URLSearchParams({
    action: 'TEMPLATE',
    text: ev.title,
    dates,
    details: detailsText(ev),
  });
  const place = placeText(ev);
  if (place) p.set('location', place);
  return `https://calendar.google.com/calendar/render?${p.toString()}`;
}

/** Google Maps search link for the venue. */
export function mapsUrl(ev: CalEvent): string | null {
  const place = placeText(ev);
  if (!place) return null;
  return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(place)}`;
}

/** Fold a content line to 75 octets, as iCalendar requires. */
function fold(line: string): string {
  if (line.length <= 73) return line;
  const parts: string[] = [];
  let rest = line;
  parts.push(rest.slice(0, 73));
  rest = rest.slice(73);
  while (rest.length > 0) {
    parts.push(' ' + rest.slice(0, 72));
    rest = rest.slice(72);
  }
  return parts.join('\r\n');
}

function escapeIcs(v: string): string {
  return v
    .replace(/\\/g, '\\\\')
    .replace(/;/g, '\\;')
    .replace(/,/g, '\\,')
    .replace(/\r\n|\r|\n/g, '\\n');
}

/** A single-event .ics file body, CRLF-delimited per RFC 5545. */
export function buildIcs(ev: CalEvent, now: Date = new Date()): string {
  const end = effectiveEnd(ev);
  const lines: string[] = [
    'BEGIN:VCALENDAR',
    'VERSION:2.0',
    'PRODID:-//Code Collective//Calendar//EN',
    'CALSCALE:GREGORIAN',
    'METHOD:PUBLISH',
    'BEGIN:VEVENT',
    `UID:${ev.key}@codecollective.us`,
    `DTSTAMP:${toUtcStamp(now)}`,
  ];

  if (ev.allDay) {
    lines.push(`DTSTART;VALUE=DATE:${toUtcDate(ev.start)}`);
    lines.push(`DTEND;VALUE=DATE:${toUtcDate(new Date(end.getTime() + 86_400_000))}`);
  } else {
    lines.push(`DTSTART:${toUtcStamp(ev.start)}`);
    lines.push(`DTEND:${toUtcStamp(end)}`);
  }

  lines.push(fold(`SUMMARY:${escapeIcs(ev.title)}`));
  lines.push(fold(`DESCRIPTION:${escapeIcs(detailsText(ev))}`));
  const place = placeText(ev);
  if (place) lines.push(fold(`LOCATION:${escapeIcs(place)}`));
  if (ev.url) lines.push(fold(`URL:${ev.url}`));
  if (ev.cancelled) lines.push('STATUS:CANCELLED');
  lines.push(`ORGANIZER;CN=${escapeIcs(ev.orgName)}:MAILTO:noreply@codecollective.us`);
  lines.push('END:VEVENT', 'END:VCALENDAR');

  return lines.join('\r\n') + '\r\n';
}

/** A filesystem-safe filename for the download. */
export function icsFilename(ev: CalEvent): string {
  const slug =
    ev.title
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '')
      .slice(0, 48) || 'event';
  return `${slug}.ics`;
}

/* ---------------- whole-city subscription links, section 7.11 ---------------- */

export function icsFeedUrl(city: CityId): string {
  return `https://codecollective.us/${city}/cc_events.ics`;
}

/** Google needs an http cid, which is what the current site uses. */
export function googleSubscribeUrl(city: CityId): string {
  return `https://calendar.google.com/calendar/u/0/r?cid=http://codecollective.us/${city}/cc_events.ics`;
}

export function webcalSubscribeUrl(city: CityId): string {
  return `webcal://codecollective.us/${city}/cc_events.ics`;
}

/** The "Report a problem" mailto, prefilled with the listing title. */
export function reportMailto(ev: CalEvent): string {
  const subject = encodeURIComponent(`Calendar listing issue: ${ev.title}`);
  const body = encodeURIComponent(
    `Listing: ${ev.title}\nStarts: ${ev.start.toISOString()}\nSource: ${ev.sourceGroup}\nLink: ${ev.url}\n\nWhat looks wrong:\n`,
  );
  return `mailto:julian@codecollective.us?subject=${subject}&body=${body}`;
}

/** Everything a power user might want, as pretty JSON. */
export function eventJson(ev: CalEvent): string {
  return JSON.stringify(
    {
      ...ev,
      start: ev.start.toISOString(),
      end: ev.end ? ev.end.toISOString() : null,
      scrapedAt: ev.scrapedAt ? ev.scrapedAt.toISOString() : null,
    },
    null,
    2,
  );
}
