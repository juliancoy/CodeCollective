import { ChevronLeft, ChevronRight } from 'lucide-react';
import { motion } from 'motion/react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { dayKeyRange, formatShortDay, tideLabels } from '../../data/time';
import { TIDE_STAGGER, spring } from '../../motion/tokens';

/** How far ahead the strip reaches when scrolled. */
export const TIDE_DAYS = 60;

const BAR_MAX = 24;
const BAR_MIN = 3;
const BAR_SPAN = 21;

export type TideLineProps = {
  todayKey: string;
  tz: string;
  /** Counts under every filter except the date range, so the strip stays navigable. */
  counts: Map<string, number>;
  activeDay: string | null;
  onPick: (dayKey: string) => void;
  /** Set when exactly one sector is selected, so the bars take its colour. */
  sectorColor: string | null;
  /** True once the data has landed, to run the one orchestrated load moment. */
  ready: boolean;
};

/**
 * Without the scroll padding, `snap-align: start` pins the first cell's edge
 * to the scrollport edge and swallows the gutter.
 */
const SCROLLER_STYLE: React.CSSProperties = {
  scrollSnapType: 'x proximity',
  scrollPaddingLeft: 4,
  scrollPaddingRight: 4,
};

/**
 * The tide line: a day strip whose bars rise and fall with how busy each day
 * is, like a tide chart.
 *
 * v2 moves it out of its own full-width band and makes it the list column's
 * header, beside the list it actually controls. Height uses a square root,
 * because a 105-event Saturday against a 15-event Tuesday flattens every other
 * day on a linear scale.
 */
function barHeight(count: number, max: number): number {
  if (count === 0) return 2;
  if (max <= 0) return BAR_MIN;
  return BAR_MIN + BAR_SPAN * Math.sqrt(count / max);
}

export function TideLine({
  todayKey,
  tz,
  counts,
  activeDay,
  onPick,
  sectorColor,
  ready,
}: TideLineProps) {
  const scrollerRef = useRef<HTMLDivElement | null>(null);
  const [overflow, setOverflow] = useState({ start: false, end: false });
  /** Roving tabindex: exactly one day is tabbable at a time. */
  const [focusIndex, setFocusIndex] = useState(0);
  const hasAnimated = useRef(false);

  const days = useMemo(() => dayKeyRange(todayKey, TIDE_DAYS), [todayKey]);

  const max = useMemo(() => {
    let m = 0;
    for (const d of days) m = Math.max(m, counts.get(d) ?? 0);
    return m;
  }, [days, counts]);

  const activeIndex = activeDay ? days.indexOf(activeDay) : -1;

  // Keep the active day in view as the agenda scrolls past it.
  useEffect(() => {
    if (activeIndex < 0) return;
    const scroller = scrollerRef.current;
    const cell = scroller?.querySelector<HTMLElement>(`[data-index="${activeIndex}"]`);
    if (!scroller || !cell) return;
    const left = cell.offsetLeft;
    const right = left + cell.offsetWidth;
    if (left < scroller.scrollLeft || right > scroller.scrollLeft + scroller.clientWidth) {
      scroller.scrollTo({ left: left - scroller.clientWidth / 2 + cell.offsetWidth / 2 });
    }
  }, [activeIndex]);

  const measure = useCallback(() => {
    const el = scrollerRef.current;
    if (!el) return;
    setOverflow({
      start: el.scrollLeft > 4,
      end: el.scrollLeft + el.clientWidth < el.scrollWidth - 4,
    });
  }, []);

  useEffect(() => {
    measure();
    const el = scrollerRef.current;
    if (!el) return;
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    el.addEventListener('scroll', measure, { passive: true });
    return () => {
      ro.disconnect();
      el.removeEventListener('scroll', measure);
    };
  }, [measure]);

  const nudge = (dir: -1 | 1) => {
    const el = scrollerRef.current;
    if (!el) return;
    el.scrollBy({ left: dir * Math.max(200, el.clientWidth * 0.8), behavior: 'smooth' });
  };

  const focusCell = (index: number) => {
    const clamped = Math.max(0, Math.min(days.length - 1, index));
    setFocusIndex(clamped);
    scrollerRef.current?.querySelector<HTMLElement>(`[data-index="${clamped}"] button`)?.focus();
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    switch (e.key) {
      case 'ArrowLeft':
        e.preventDefault();
        focusCell(focusIndex - 1);
        break;
      case 'ArrowRight':
        e.preventDefault();
        focusCell(focusIndex + 1);
        break;
      case 'Home':
        e.preventDefault();
        focusCell(0);
        break;
      case 'End':
        e.preventDefault();
        focusCell(days.length - 1);
        break;
      default:
        break;
    }
  };

  const shouldAnimate = ready && !hasAnimated.current;
  useEffect(() => {
    if (ready) hasAnimated.current = true;
  }, [ready]);

  return (
    <div className="relative flex items-stretch border-b" style={{ borderColor: 'var(--line)' }}>
      {overflow.start && (
        <button
          type="button"
          onClick={() => nudge(-1)}
          aria-label="Earlier days"
          className="absolute left-0 z-10 hidden h-full w-8 items-center justify-center md:flex"
          style={{
            background: 'linear-gradient(to right, var(--bg) 60%, transparent)',
            color: 'var(--ink-2)',
          }}
        >
          <ChevronLeft size={18} strokeWidth={1.5} aria-hidden />
        </button>
      )}

      <div
        ref={scrollerRef}
        role="toolbar"
        aria-label="Choose a day"
        aria-orientation="horizontal"
        onKeyDown={onKeyDown}
        className="relative no-scrollbar flex flex-1 gap-0.5 overflow-x-auto scroll-smooth px-1 pt-2 pb-2"
        style={SCROLLER_STYLE}
      >
        {days.map((dayKey, i) => {
          const count = counts.get(dayKey) ?? 0;
          const { weekday, numeral } = tideLabels(dayKey, tz);
          const isActive = dayKey === activeDay;
          const isToday = dayKey === todayKey;
          const h = barHeight(count, max);

          const barColor = isActive
            ? 'var(--brand-on-bg)'
            : count === 0
              ? 'var(--line)'
              : (sectorColor ?? 'color-mix(in srgb, var(--sky-deep) 55%, transparent)');

          return (
            <div
              key={dayKey}
              data-index={i}
              className="shrink-0"
              style={{ scrollSnapAlign: 'start' }}
            >
              <button
                type="button"
                data-tide-day={dayKey}
                tabIndex={i === focusIndex ? 0 : -1}
                aria-current={isActive ? 'date' : undefined}
                // No aria-label: WCAG 2.5.3 wants the accessible name to
                // contain the visible text, so the weekday and numeral stay in
                // the name and only the count is added for screen readers.
                title={`${formatShortDay(dayKey, tz)}: ${
                  count === 1 ? '1 event' : `${count} events`
                }`}
                onClick={() => {
                  setFocusIndex(i);
                  onPick(dayKey);
                }}
                className="flex w-11 flex-col items-center gap-[3px] rounded-[var(--r-cell)] pt-1 pb-[5px]"
                style={{
                  minHeight: 44,
                  borderBottom: `2px solid ${isActive ? 'var(--brand-on-bg)' : 'transparent'}`,
                }}
              >
                <span
                  className="t-tide-day tide-weekday"
                  style={{ color: isActive ? 'var(--brand-on-bg)' : 'var(--ink-2)' }}
                >
                  {weekday}
                </span>

                {isToday ? (
                  /* Today's coin: the only gold in this zone. */
                  <motion.span
                    className="t-tide-num flex items-center justify-center rounded-full"
                    initial={shouldAnimate ? { scale: 0.6 } : false}
                    animate={{ scale: 1 }}
                    transition={{ ...spring.gentle, delay: shouldAnimate ? TIDE_STAGGER * 14 : 0 }}
                    style={{
                      width: 26,
                      height: 26,
                      background: 'var(--gold)',
                      color: 'var(--gold-ink)',
                    }}
                  >
                    {numeral}
                  </motion.span>
                ) : (
                  <span
                    className="t-tide-num flex h-[26px] items-center"
                    style={{ color: isActive ? 'var(--brand-on-bg)' : 'var(--ink)' }}
                  >
                    {numeral}
                  </span>
                )}

                <span className="sr-only">{`, ${
                  count === 1 ? '1 event' : `${count} events`
                }`}</span>

                <span
                  aria-hidden
                  className="flex w-full items-end justify-center"
                  style={{ height: BAR_MAX }}
                >
                  <motion.span
                    initial={shouldAnimate ? { height: 2 } : false}
                    animate={{ height: h }}
                    transition={{ ...spring.gentle, delay: shouldAnimate ? i * TIDE_STAGGER : 0 }}
                    style={{
                      display: 'block',
                      width: 18,
                      borderRadius: 2,
                      background: barColor,
                      // The sector handoff: colour eases while heights spring.
                      transition: 'background-color 240ms ease',
                    }}
                  />
                </span>
              </button>
            </div>
          );
        })}
      </div>

      {overflow.end && (
        <button
          type="button"
          onClick={() => nudge(1)}
          aria-label="Later days"
          className="absolute right-0 z-10 hidden h-full w-8 items-center justify-center md:flex"
          style={{
            background: 'linear-gradient(to left, var(--bg) 60%, transparent)',
            color: 'var(--ink-2)',
          }}
        >
          <ChevronRight size={18} strokeWidth={1.5} aria-hidden />
        </button>
      )}
    </div>
  );
}
