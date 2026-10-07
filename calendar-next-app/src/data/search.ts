import Fuse from 'fuse.js';
import type { CalEvent } from './types';

/**
 * Search never reorders the agenda. Fuse decides which events match; the
 * caller keeps them in chronological order, because a calendar sorted by
 * relevance is unusable.
 */
type Indexed = {
  key: string;
  title: string;
  organizer: string;
  place: string;
  tags: string;
};

const OPTIONS: ConstructorParameters<typeof Fuse<Indexed>>[1] = {
  includeScore: false,
  threshold: 0.32,
  ignoreLocation: true,
  minMatchCharLength: 2,
  keys: [
    { name: 'title', weight: 0.5 },
    { name: 'organizer', weight: 0.2 },
    { name: 'place', weight: 0.15 },
    { name: 'tags', weight: 0.15 },
  ],
};

function toIndexed(e: CalEvent): Indexed {
  return {
    key: e.key,
    title: e.title,
    organizer: e.orgName,
    place: [e.venue, e.locality].filter(Boolean).join(', '),
    tags: e.tags.join(' '),
  };
}

export class EventSearch {
  private fuse: Fuse<Indexed>;

  constructor(events: readonly CalEvent[]) {
    this.fuse = new Fuse(events.map(toIndexed), OPTIONS);
  }

  /** The keys that match, as a set for O(1) membership in the filter pass. */
  matchKeys(query: string): Set<string> {
    const q = query.trim();
    if (q === '') return new Set();
    return new Set(this.fuse.search(q).map((r) => r.item.key));
  }
}

/**
 * Build the index off the critical path. The agenda renders before the index
 * exists, and the first keystroke waits at most one idle tick.
 */
export function buildSearchIndexWhenIdle(
  events: readonly CalEvent[],
  onReady: (search: EventSearch) => void,
): () => void {
  let cancelled = false;
  const run = () => {
    if (cancelled) return;
    onReady(new EventSearch(events));
  };
  const ric = (globalThis as { requestIdleCallback?: (cb: () => void, o?: { timeout: number }) => number })
    .requestIdleCallback;
  if (typeof ric === 'function') {
    const id = ric(run, { timeout: 1200 });
    return () => {
      cancelled = true;
      (globalThis as { cancelIdleCallback?: (h: number) => void }).cancelIdleCallback?.(id);
    };
  }
  const t = setTimeout(run, 200);
  return () => {
    cancelled = true;
    clearTimeout(t);
  };
}
