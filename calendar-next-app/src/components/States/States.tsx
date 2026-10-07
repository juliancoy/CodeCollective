import { CircleAlert, WifiOff } from 'lucide-react';
import type { Relaxation } from '../../data/pipeline';
import { relativeTime } from '../../data/time';

/* ---------------- loading ---------------- */

/**
 * A skeleton that mirrors the real layout, so nothing shifts when the data
 * lands. Static blocks with a slow opacity pulse, and no spinner anywhere.
 */
export function AgendaSkeleton() {
  return (
    <div aria-hidden>
      <div className="flex items-baseline justify-between px-4 py-2">
        <div className="skeleton h-6 w-48 rounded-[var(--r-cell)]" />
        <div className="skeleton h-4 w-20 rounded-[var(--r-cell)]" />
      </div>
      <ul className="row-list">
        {Array.from({ length: 6 }, (_, i) => (
          <li key={i} className="grid grid-cols-[76px_1fr_auto] items-start gap-4 px-4 py-4">
            <div className="space-y-2">
              <div className="skeleton h-4 w-14 rounded-[var(--r-cell)]" />
              <div className="skeleton h-4 w-12 rounded-[var(--r-cell)]" />
            </div>
            <div className="space-y-2">
              <div className="skeleton h-5 rounded-[var(--r-cell)]" style={{ width: `${70 - i * 4}%` }} />
              <div className="skeleton h-4 w-32 rounded-[var(--r-cell)]" />
              <div className="skeleton h-4 w-44 rounded-[var(--r-cell)]" />
            </div>
            <div className="skeleton h-16 w-16 rounded-[var(--r-thumb)]" />
          </li>
        ))}
      </ul>
      <p className="sr-only" role="status">
        Loading events.
      </p>
    </div>
  );
}

/** Only the counts are unknown before the feed lands; the heading is not. */
export function MetaSkeleton() {
  return (
    <div aria-hidden className="mt-2">
      <div className="skeleton h-5 w-96 max-w-full rounded-[var(--r-cell)]" />
    </div>
  );
}

export function TideSkeleton() {
  return (
    <div aria-hidden className="flex gap-1 px-4 py-2">
      {Array.from({ length: 14 }, (_, i) => (
        <div key={i} className="flex w-11 flex-col items-center gap-1">
          <div className="skeleton h-3 w-6 rounded" />
          <div className="skeleton h-5 w-5 rounded" />
          <div className="h-8 w-full self-end" style={{ borderTop: '2px solid var(--line)' }} />
        </div>
      ))}
    </div>
  );
}

/* ---------------- error ---------------- */

export function ErrorState({ city, onRetry }: { city: string; onRetry: () => void }) {
  return (
    <div className="mx-auto max-w-md px-4 py-16 text-center">
      <CircleAlert
        size={28}
        strokeWidth={1.5}
        aria-hidden
        className="mx-auto mb-4"
        style={{ color: 'var(--ink-2)' }}
      />
      <h2 className="t-sheet-title" style={{ color: 'var(--ink)' }}>
        {city} events did not load.
      </h2>
      <p className="t-body mt-2" style={{ color: 'var(--ink-2)' }}>
        Check your connection, then try again.
      </p>
      <button
        type="button"
        onClick={onRetry}
        className="t-body mt-6 rounded-[var(--r-pill)] px-5 py-2.5"
        style={{ background: 'var(--brand)', color: 'var(--brand-ink)' }}
      >
        Try again
      </button>
    </div>
  );
}

/* ---------------- empty ---------------- */

export function EmptyState({
  query,
  hasDateFilter,
  relaxations,
  onRelax,
  onClearAll,
  onSearchAllDates,
}: {
  query: string;
  hasDateFilter: boolean;
  relaxations: Relaxation[];
  onRelax: (r: Relaxation) => void;
  onClearAll: () => void;
  onSearchAllDates: () => void;
}) {
  const searching = query.trim() !== '';

  return (
    <div className="mx-auto max-w-md px-4 py-16 text-center">
      <h2 className="t-sheet-title" style={{ color: 'var(--ink)' }}>
        {searching ? `No events match “${query.trim()}”.` : 'No events match these filters.'}
      </h2>

      {searching && hasDateFilter && (
        <p className="mt-4">
          <button
            type="button"
            onClick={onSearchAllDates}
            className="t-body underline"
            style={{ color: 'var(--brand-on-bg)', textUnderlineOffset: '2px', minHeight: 44 }}
          >
            Search all dates
          </button>
        </p>
      )}

      {relaxations.length > 0 && (
        <ul className="mt-6 flex flex-col items-stretch gap-2">
          {relaxations.map((r) => (
            <li key={r.id}>
              <button
                type="button"
                onClick={() => onRelax(r)}
                className="t-body w-full rounded-[var(--r-pill)] border px-4 py-2.5"
                style={{ borderColor: 'var(--line)', background: 'var(--bg)', color: 'var(--ink)' }}
              >
                {r.label}
              </button>
            </li>
          ))}
        </ul>
      )}

      <p className="mt-6">
        <button
          type="button"
          onClick={onClearAll}
          className="t-meta underline"
          style={{ color: 'var(--ink-2)', textUnderlineOffset: '2px', minHeight: 44 }}
        >
          Clear all filters
        </button>
      </p>
    </div>
  );
}

/* ---------------- banners ---------------- */

/** Shown when the newest scrape is more than 48 hours old. */
export function StaleBanner({ newest }: { newest: Date }) {
  return (
    <p
      className="t-meta mt-3 rounded-[var(--r-cell)] px-3 py-2"
      style={{ background: 'var(--bg-soft)', color: 'var(--ink-2)' }}
    >
      Listings were last updated {relativeTime(newest)}. Check the event page before you go.
    </p>
  );
}

/** Shown when the live feed was unreachable and bundled data is standing in. */
export function SnapshotBanner({ takenOn }: { takenOn: string | null }) {
  return (
    <p
      className="t-meta mt-3 flex items-center gap-2 rounded-[var(--r-cell)] px-3 py-2"
      style={{ background: 'var(--bg-soft)', color: 'var(--ink-2)' }}
    >
      <WifiOff size={16} strokeWidth={1.5} aria-hidden className="shrink-0" />
      <span>
        The live feed could not be reached, so this is a saved copy
        {takenOn ? ` from ${takenOn}` : ''}. Check the event page before you go.
      </span>
    </p>
  );
}

/** Shown when the fetch failed but this session had a copy. */
export function OfflineBanner() {
  return (
    <p
      className="t-meta mt-3 flex items-center gap-2 rounded-[var(--r-cell)] px-3 py-2"
      style={{ background: 'var(--bg-soft)', color: 'var(--ink-2)' }}
    >
      <WifiOff size={16} strokeWidth={1.5} aria-hidden />
      Offline. Showing events from your last visit.
    </p>
  );
}
