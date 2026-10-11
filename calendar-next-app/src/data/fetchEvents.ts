import type { CityId, RawEvent } from './types';

/**
 * One cached promise per city, read with React `use()` inside a Suspense
 * boundary. Nothing here touches the DOM, so it is safe to start early.
 */
export type FeedSource = 'live' | 'session' | 'snapshot';

export type FeedResult = {
  rows: RawEvent[];
  /** Where the rows actually came from, which the meta line has to be honest about. */
  source: FeedSource;
  /** Present when the rows are a bundled snapshot rather than the live feed. */
  snapshotDate: string | null;
  fetchedAt: number;
};

const MODE = (import.meta.env?.VITE_DATA_SOURCE as string | undefined) ?? 'live';
const BASE = import.meta.env?.BASE_URL ?? '/';

/**
 * When set, a failed live fetch falls back to a snapshot bundled beside the
 * app instead of showing the error state. The hosted preview needs this,
 * because a sandboxed frame cannot always reach a third-party origin, and it
 * is a genuine improvement for the real app too: without it, a feed outage
 * leaves a dead page unless this browser happens to hold a session copy.
 */
const SNAPSHOT_FALLBACK = import.meta.env?.VITE_SNAPSHOT_FALLBACK === '1';

/** The date the bundled snapshot was taken, for the banner. */
const SNAPSHOT_DATE = (import.meta.env?.VITE_SNAPSHOT_DATE as string | undefined) ?? null;

function liveUrl(city: CityId): string {
  return `https://codecollective.us/${city}/upcoming_events.json`;
}

function snapshotUrl(city: CityId): string {
  return `${BASE}snapshot/${city}.json`;
}

function cacheKey(city: CityId): string {
  return `cc-feed-${city}`;
}

function readSessionCache(city: CityId): RawEvent[] | null {
  try {
    const raw = sessionStorage.getItem(cacheKey(city));
    if (!raw) return null;
    const parsed = JSON.parse(raw) as { rows?: unknown };
    return Array.isArray(parsed.rows) ? (parsed.rows as RawEvent[]) : null;
  } catch {
    // Private mode, blocked storage, or corrupt JSON. Not worth surfacing.
    return null;
  }
}

function writeSessionCache(city: CityId, rows: RawEvent[]): void {
  try {
    sessionStorage.setItem(cacheKey(city), JSON.stringify({ rows, at: Date.now() }));
  } catch {
    // Over quota on a multi-megabyte feed is normal; the page works without it.
  }
}

async function fetchRows(url: string): Promise<RawEvent[]> {
  const res = await fetch(url, { headers: { accept: 'application/json' } });
  if (!res.ok) throw new Error(`Feed responded ${res.status}`);
  const rows = (await res.json()) as unknown;
  if (!Array.isArray(rows)) throw new Error('Feed was not a JSON array');
  return rows as RawEvent[];
}

async function load(city: CityId): Promise<FeedResult> {
  // An explicit snapshot build never reaches for the network.
  if (MODE === 'snapshot') {
    return {
      rows: await fetchRows(snapshotUrl(city)),
      source: 'snapshot',
      snapshotDate: SNAPSHOT_DATE,
      fetchedAt: Date.now(),
    };
  }

  try {
    const rows = await fetchRows(liveUrl(city));
    writeSessionCache(city, rows);
    return { rows, source: 'live', snapshotDate: null, fetchedAt: Date.now() };
  } catch (liveError) {
    // This browser's own copy is the closest thing to live.
    const cached = readSessionCache(city);
    if (cached) {
      return { rows: cached, source: 'session', snapshotDate: null, fetchedAt: Date.now() };
    }

    if (SNAPSHOT_FALLBACK) {
      try {
        return {
          rows: await fetchRows(snapshotUrl(city)),
          source: 'snapshot',
          snapshotDate: SNAPSHOT_DATE,
          fetchedAt: Date.now(),
        };
      } catch {
        // Fall through to the error state rather than hide the real problem.
      }
    }

    throw liveError instanceof Error ? liveError : new Error('Could not load events');
  }
}

const inFlight = new Map<CityId, Promise<FeedResult>>();

/** The cached promise for a city, created on first read. */
export function eventsPromise(city: CityId): Promise<FeedResult> {
  let p = inFlight.get(city);
  if (!p) {
    p = load(city);
    inFlight.set(city, p);
  }
  return p;
}

/** Drop the cache so "Try again" and the staleness refetch start fresh. */
export function invalidateEvents(city?: CityId): void {
  if (city) inFlight.delete(city);
  else inFlight.clear();
}
