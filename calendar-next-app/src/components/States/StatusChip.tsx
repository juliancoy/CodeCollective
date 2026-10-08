import { Clock, CloudOff, WifiOff } from 'lucide-react';
import { Suspense, lazy, useEffect, useState } from 'react';
import { relativeTime } from '../../data/time';

const StatusChipPopover = lazy(() => import('./StatusChipPopover'));

/**
 * v1 gave data problems a full-width banner, which cost a whole band above the
 * first event. v2 puts a chip at the end of the meta line instead. No sentence
 * is lost: the full wording opens in a popover.
 */
export type DataStatus =
  | { kind: 'ok' }
  | { kind: 'snapshot'; takenOn: string | null }
  | { kind: 'stale'; newest: Date; now: Date }
  | { kind: 'offline' };

export function dataStatus(args: {
  feedSource: 'live' | 'session' | 'snapshot';
  snapshotDate: string | null;
  newestScrapeAt: Date | null;
  now: Date;
  staleAfterMs: number;
}): DataStatus {
  if (args.feedSource === 'snapshot') return { kind: 'snapshot', takenOn: args.snapshotDate };
  if (args.feedSource === 'session') return { kind: 'offline' };
  if (args.newestScrapeAt && args.now.getTime() - args.newestScrapeAt.getTime() > args.staleAfterMs) {
    return { kind: 'stale', newest: args.newestScrapeAt, now: args.now };
  }
  return { kind: 'ok' };
}

function describe(status: DataStatus): { label: string; body: string; Icon: typeof Clock } | null {
  switch (status.kind) {
    case 'snapshot':
      return {
        label: 'Saved copy',
        Icon: CloudOff,
        body: `The live feed could not be reached, so this is a saved copy${
          status.takenOn ? ` from ${status.takenOn}` : ''
        }. Check the event page before you go.`,
      };
    case 'stale':
      return {
        label: `Updated ${relativeTime(status.newest, status.now)}`,
        Icon: Clock,
        body: `Listings were last updated ${relativeTime(
          status.newest,
          status.now,
        )}. Check the event page before you go.`,
      };
    case 'offline':
      return {
        label: 'Offline',
        Icon: WifiOff,
        body: 'Showing events from your last visit.',
      };
    case 'ok':
    default:
      return null;
  }
}

export function StatusChip({ status }: { status: DataStatus }) {
  const [ready, setReady] = useState(false);
  const [pending, setPending] = useState(false);

  // Swap the popover in on the first idle tick, so its 33 KB of Base UI
  // machinery never sits on the critical path for a chip in the brand band.
  useEffect(() => {
    const ric = (
      globalThis as { requestIdleCallback?: (cb: () => void, o?: { timeout: number }) => number }
    ).requestIdleCallback;
    if (typeof ric === 'function') {
      const id = ric(() => setReady(true), { timeout: 2000 });
      return () =>
        (globalThis as { cancelIdleCallback?: (h: number) => void }).cancelIdleCallback?.(id);
    }
    const t = setTimeout(() => setReady(true), 400);
    return () => clearTimeout(t);
  }, []);

  const detail = describe(status);
  if (!detail) return null;
  const { label, body, Icon } = detail;

  const inner = (
    <>
      <Icon size={12} strokeWidth={2} aria-hidden />
      {label}
    </>
  );

  if (ready) {
    return (
      <Suspense fallback={null}>
        <StatusChipPopover trigger={inner} body={body} openOnMount={pending} />
      </Suspense>
    );
  }

  // Before the chunk lands the chip still reads, and the full sentence is
  // available as a tooltip rather than being lost.
  return (
    <button
      type="button"
      title={body}
      onClick={() => {
        setPending(true);
        setReady(true);
      }}
      className="t-caption ml-2 inline-flex items-center gap-1.5 rounded-[var(--r-pill)] px-2.5 align-middle"
      style={{ minHeight: 26, background: 'var(--brand-soft)', color: 'var(--brand-soft-ink)' }}
    >
      {inner}
    </button>
  );
}
