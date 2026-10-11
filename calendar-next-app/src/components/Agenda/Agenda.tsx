import { useEffect, useRef, useState, type ReactNode } from 'react';
import type { DaySectionModel } from '../../data/pipeline';
import { useMediaQuery } from '../../app/layoutHooks';
import { DaySection } from './DaySection';

/** How many day sections the sentinel adds each time it comes into view. */
const BATCH = 14;
/**
 * The first paint renders fewer. Today alone can hold 105 events, so a full
 * 14-day first slice put ~350 rows on the main thread before anything was
 * interactive. The sentinel fills the rest in immediately.
 */
const FIRST_BATCH = 3;

export type AgendaProps = {
  days: DaySectionModel[];
  tz: string;
  todayKey: string;
  selectedKey: string | null;
  flashKey: string | null;
  onOpen: (key: string) => void;
  onHover: (key: string | null) => void;
  /** Called with the topmost visible day, to drive the tide line's active day. */
  onVisibleDayChange: (dayKey: string) => void;
  /**
   * Changes only when a filter changes. The clock ticks every minute, which
   * rebuilds `days`, and resetting on that would yank a scrolled visitor back
   * to the first batch once a minute.
   */
  resetToken: string;
  /**
   * Slotted in after today's section, so today's events stay above the fold
   * and the interlude reads as a break in the list rather than a banner.
   */
  interlude?: ReactNode;
};

/**
 * Day sections render in batches rather than all 262 at once, and each section
 * carries `content-visibility: auto` so off-screen days cost no layout. The
 * list is the accessible equivalent of the map, so nothing is virtualized away
 * from the accessibility tree once it has been rendered.
 */
export function Agenda({
  days,
  tz,
  todayKey,
  selectedKey,
  flashKey,
  onOpen,
  onHover,
  onVisibleDayChange,
  resetToken,
  interlude,
}: AgendaProps) {
  const isPhone = useMediaQuery('(max-width: 767px)');
  const [limit, setLimit] = useState(FIRST_BATCH);
  const sentinelRef = useRef<HTMLDivElement | null>(null);
  const rootRef = useRef<HTMLDivElement | null>(null);

  // A new filter result starts the list again from the top batch.
  useEffect(() => {
    setLimit(FIRST_BATCH);
  }, [resetToken]);

  useEffect(() => {
    const el = sentinelRef.current;
    if (!el) return;
    const io = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          setLimit((n) => (n >= days.length ? n : n + BATCH));
        }
      },
      { rootMargin: '600px 0px' },
    );
    io.observe(el);
    return () => io.disconnect();
  }, [days.length, limit]);

  // Scroll spy: the active day follows the topmost visible day header.
  useEffect(() => {
    const root = rootRef.current;
    if (!root) return;
    const headers = root.querySelectorAll<HTMLElement>('[data-day]');
    if (headers.length === 0) return;

    const io = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
        const top = visible[0]?.target.getAttribute('data-day');
        if (top) onVisibleDayChange(top);
      },
      {
        // Only count a day once its header has cleared the sticky chrome.
        rootMargin: '-40% 0px -55% 0px',
      },
    );
    for (const h of headers) io.observe(h);
    return () => io.disconnect();
  }, [limit, days, onVisibleDayChange]);

  const shown = days.slice(0, limit);

  return (
    <div ref={rootRef}>
      {shown.map((day, i) => (
        <div key={day.dayKey}>
          <DaySection
            day={day}
            tz={tz}
            todayKey={todayKey}
            selectedKey={selectedKey}
            flashKey={flashKey}
            onOpen={onOpen}
            onHover={onHover}
            isPhone={isPhone}
          />
          {/* After today, or after the first day when today has nothing on. */}
          {interlude && (day.dayKey === todayKey || (i === 0 && day.dayKey > todayKey))
            ? interlude
            : null}
        </div>
      ))}

      {limit < days.length && (
        <div ref={sentinelRef} className="px-4 py-8">
          <p className="t-meta" style={{ color: 'var(--ink-2)' }}>
            Loading more days…
          </p>
        </div>
      )}
    </div>
  );
}
