import { cleanOrganizer, cleanTitle, initialsFor, looksOnline } from './display';
import { sectorsForTags, inMapOrder } from './sectors';
import { FEED_ZONE, dayKeyOf, hourInZone, minutesInZone, parseInstant } from './time';
import type { CalEvent, RawEvent, RawLocation, SectorId } from './types';

const SITE = 'https://codecollective.us';

/** Stable 32-bit FNV-1a, base36. */
export function fnv1a(input: string): string {
  let h = 0x811c9dc5;
  for (let i = 0; i < input.length; i++) {
    h ^= input.charCodeAt(i);
    // 16777619, via shifts to stay in 32-bit range.
    h = (h + (h << 1) + (h << 4) + (h << 7) + (h << 8) + (h << 24)) >>> 0;
  }
  return h.toString(36);
}

/**
 * A key that identifies one *occurrence*.
 *
 * The upstream `id` is not per-occurrence: 18 time.ly ids in the Baltimore feed
 * are reused across every date in a recurring series, one of them across 23
 * dates. Keying on the id alone silently merged 161 real events out of the
 * calendar, so the start is always part of the key. Verified to give 1,695
 * distinct keys for the 1,695 rows in the committed snapshot.
 */
export function eventKey(raw: Pick<RawEvent, 'id' | 'name' | 'startDate' | 'source'>): string {
  const id = raw.id === undefined || raw.id === null ? '' : String(raw.id).trim();
  if (id !== '') return `${id}@${fnv1a(String(raw.startDate))}`;
  return fnv1a(`${raw.name}|${raw.startDate}|${raw.source}`);
}

function absoluteImage(url: string | null | undefined): string | null {
  const v = (url ?? '').trim();
  if (v === '') return null;
  if (/^https?:\/\//i.test(v)) return v;
  return SITE + (v.startsWith('/') ? v : '/' + v);
}

/**
 * Event times. Every `startDate` in the feed carries an explicit offset today,
 * but a future offset-less value is read in the city zone rather than the
 * viewer's, which is the only sensible local reading.
 */
function validDate(value: string | null | undefined, zone: string): Date | null {
  return parseInstant(value, zone);
}

const NAMED_ENTITIES: Record<string, string> = {
  amp: '&',
  lt: '<',
  gt: '>',
  quot: '"',
  apos: "'",
  nbsp: ' ',
  ndash: '–',
  mdash: '—',
  lsquo: '‘',
  rsquo: '’',
  ldquo: '“',
  rdquo: '”',
  hellip: '…',
  eacute: 'é',
  egrave: 'è',
  uuml: 'ü',
  ouml: 'ö',
  auml: 'ä',
  ntilde: 'ñ',
  deg: '°',
  middot: '·',
  bull: '•',
  trade: '™',
  reg: '®',
  copy: '©',
};

/**
 * Plain-text fields arrive HTML-encoded from several scrapers: 15 titles and
 * 10 location fields in the Baltimore feed carry things like `&#038;` and
 * `&#8217;`. One decode pass, which is what a browser would render. Decoding
 * twice would mangle text that legitimately reads "&amp;".
 *
 * Written by hand rather than through the DOM so it behaves identically in
 * the browser and under test.
 */
export function decodeEntities(input: string): string {
  if (!input.includes('&')) return input;
  return input.replace(
    /&(?:([a-zA-Z][a-zA-Z0-9]{1,31})|#(\d{1,7})|#[xX]([0-9a-fA-F]{1,6}));/g,
    (match: string, named?: string, dec?: string, hex?: string) => {
      if (named !== undefined) return NAMED_ENTITIES[named.toLowerCase()] ?? match;
      const code = dec !== undefined ? Number.parseInt(dec, 10) : Number.parseInt(hex ?? '', 16);
      // Reject surrogate halves and anything past the Unicode range.
      if (!Number.isFinite(code) || code <= 0 || code > 0x10ffff) return match;
      if (code >= 0xd800 && code <= 0xdfff) return match;
      return String.fromCodePoint(code);
    },
  );
}

/**
 * Percent escapes that reached a title instead of a URL.
 *
 * Part of the feed is scraped from query strings, so the same event can arrive
 * twice with its ampersand written `&#038;` once and `%26` the other time —
 * which reads as "Lunch %26 Learn" on the page and defeats any dedupe that
 * compares titles. Only this fixed set is decoded: running decodeURIComponent
 * over free text turns a literal "50% 26 inch" into mojibake, and throws on a
 * lone "%".
 */
const PERCENT_ESCAPES: Record<string, string> = {
  '%20': ' ', '%21': '!', '%22': '"', '%23': '#', '%24': '$', '%25': '%',
  '%26': '&', '%27': "'", '%28': '(', '%29': ')', '%2B': '+', '%2C': ',',
  '%2D': '-', '%2E': '.', '%2F': '/', '%3A': ':', '%3B': ';', '%3F': '?',
  '%40': '@', '%5F': '_', '%7C': '|',
};

function decodePercentEscapes(input: string): string {
  if (!input.includes('%')) return input;
  return input.replace(/%[0-9a-fA-F]{2}/g, (m) => PERCENT_ESCAPES[m.toUpperCase()] ?? m);
}

function cleanText(value: string | null | undefined): string {
  return decodePercentEscapes(decodeEntities((value ?? '').replace(/\r\n?/g, '\n'))).trim();
}

/**
 * Plain-text summary for accessible descriptions and meta tags. Strips tags
 * and the commonest markdown punctuation without pulling in a parser.
 */
export function toExcerpt(md: string, max = 160): string {
  const text = md
    .replace(/<[^>]+>/g, ' ')
    .replace(/!?\[([^\]]*)\]\([^)]*\)/g, '$1')
    .replace(/[*_`>#]+/g, ' ')
    .replace(/&nbsp;/g, ' ')
    .replace(/&amp;/g, '&')
    .replace(/&#\d+;/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
  if (text.length <= max) return text;
  const cut = text.slice(0, max);
  const lastSpace = cut.lastIndexOf(' ');
  return (lastSpace > max * 0.6 ? cut.slice(0, lastSpace) : cut).trimEnd() + '…';
}

function normalizeLocation(loc: RawEvent['location']): {
  venue: string | null;
  address: string | null;
  locality: string | null;
  coords: { lat: number; lng: number } | null;
} {
  if (!loc) return { venue: null, address: null, locality: null, coords: null };

  // Some rows ship the location as a bare string.
  if (typeof loc === 'string') {
    const v = cleanText(loc);
    return { venue: v === '' ? null : v, address: null, locality: null, coords: null };
  }

  const o = loc as RawLocation;
  const name = cleanText(o.name);
  const address = cleanText(o.address);
  const city = cleanText(o.city);

  const lat = o.latitude;
  const lng = o.longitude;
  const coords =
    typeof lat === 'number' && Number.isFinite(lat) && typeof lng === 'number' && Number.isFinite(lng)
      ? { lat, lng }
      : null;

  return {
    venue: name === '' ? null : name,
    // When the name and address are the same string, show it once.
    address: address === '' || address === name ? null : address,
    locality: city === '' ? null : city,
    coords,
  };
}

const FEATURED_SOURCE = /^https?:\/\/(?:www\.)?(?:luma\.com|lu\.ma)\/codecollective\/?$/i;

export type NormalizeOptions = {
  /** The zone the calendar is rendered in. */
  tz: string;
  /** Reference moment; events already finished are dropped relative to this. */
  now: Date;
};

/** One raw row to a CalEvent, or null when the row should not be listed. */
export function normalizeEvent(raw: RawEvent, opts: NormalizeOptions): CalEvent | null {
  const { tz, now } = opts;

  const start = validDate(raw.startDate, tz);
  if (!start) return null;

  // `endTime` wins over `endDate`; either is dropped when it is not after start.
  const endCandidate = validDate(raw.endTime, tz) ?? validDate(raw.endDate, tz);
  const end = endCandidate && endCandidate.getTime() > start.getTime() ? endCandidate : null;

  // Drop what has already finished. With no end, an event runs for 2 hours.
  const finish = end ?? new Date(start.getTime() + 2 * 3600_000);
  if (finish.getTime() < now.getTime()) return null;

  const durationHrs = end ? (end.getTime() - start.getTime()) / 3600_000 : 0;
  const startsAtMidnightLocal = minutesInZone(start, tz) === 0;
  const allDay = durationHrs >= 20 || (startsAtMidnightLocal && !end);

  const dayKey = dayKeyOf(start, tz);
  const endDayKey = end ? dayKeyOf(end, tz) : null;

  const descriptionMd = cleanText(raw.description);
  const tags = Array.isArray(raw.tags) ? raw.tags.filter((t) => typeof t === 'string') : [];
  const sectors: SectorId[] = inMapOrder(sectorsForTags(tags));

  const loc = normalizeLocation(raw.location);
  // Display hygiene: the raw strings stay available through "Copy event
  // details", but nobody should have to read a shouted title or an internal
  // user handle where an organizer's name belongs.
  const rawOrg = cleanText(raw.org_name || raw.orgName) || 'Unknown organizer';
  const orgName = cleanOrganizer(rawOrg);
  const online = looksOnline(loc.venue, loc.address, loc.locality);

  return {
    key: eventKey(raw),
    title: cleanTitle(cleanText(raw.name)) || 'Untitled event',
    descriptionMd,
    excerpt: toExcerpt(descriptionMd),
    start,
    end,
    allDay,
    dayKey,
    endDayKey: endDayKey && endDayKey !== dayKey ? endDayKey : null,
    url: cleanText(raw.url),
    cancelled: String(raw.status ?? '').toUpperCase() === 'CANCELLED',
    recurring: raw.recurring === true,
    venue: loc.venue,
    address: loc.address,
    locality: loc.locality,
    online,
    // An online event has no place to pin, so it never reaches the map.
    coords: online ? null : loc.coords,
    image: absoluteImage(raw.imageUrl),
    orgName,
    orgLogo: absoluteImage(raw.orgImageUrl),
    initials: initialsFor(rawOrg, loc.venue),
    sectors,
    primarySector: sectors[0] ?? 'other',
    tags,
    sourceGroup: cleanText(raw.source_group) || cleanText(raw.source) || 'Unknown source',
    featured: FEATURED_SOURCE.test(cleanText(raw.source)),
    // The scrape stamp describes the pipeline, so it is always read in the
    // scrapers' own zone, never the city's or the viewer's.
    scrapedAt: validDate(raw.scrapeTime, FEED_ZONE),
  };
}

/**
 * The whole feed, normalized, de-duplicated by key and ordered by start.
 * A stable tiebreak on title keeps the order identical between runs.
 */
export function normalizeEvents(rows: readonly RawEvent[], opts: NormalizeOptions): CalEvent[] {
  const byKey = new Map<string, CalEvent>();
  for (const row of rows) {
    if (!row || typeof row !== 'object') continue;
    const ev = normalizeEvent(row, opts);
    if (!ev) continue;
    const existing = byKey.get(ev.key);
    if (existing) {
      // Same key twice: keep the richer row rather than the later one.
      const better =
        (ev.descriptionMd.length > existing.descriptionMd.length ? 1 : 0) +
        (ev.coords && !existing.coords ? 1 : 0) +
        (ev.image && !existing.image ? 1 : 0);
      if (better < 2) continue;
    }
    byKey.set(ev.key, ev);
  }
  return [...byKey.values()].sort(
    (a, b) => a.start.getTime() - b.start.getTime() || a.title.localeCompare(b.title),
  );
}

/** Newest scrapeTime across the feed, for the freshness and stale-data lines. */
export function newestScrape(events: readonly CalEvent[]): Date | null {
  let newest: Date | null = null;
  for (const e of events) {
    if (e.scrapedAt && (!newest || e.scrapedAt > newest)) newest = e.scrapedAt;
  }
  return newest;
}

/** Distinct organizer count, for the meta line. */
export function organizerCount(events: readonly CalEvent[]): number {
  return new Set(events.map((e) => e.orgName)).size;
}

/** Hour of day in the city zone; re-exported so filters need one import. */
export { hourInZone };
