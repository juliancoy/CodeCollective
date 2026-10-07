import { ChevronLeft, ChevronRight } from 'lucide-react';
import { useMemo, useRef, useState } from 'react';
import { monthModel } from '../../data/pipeline';
import { addDaysToKey, diffDayKeys, formatLongDay, startOfDayKey } from '../../data/time';
import type { CalEvent } from '../../data/types';

const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

/** The Monday on or before `dayKey`. */
function mondayOf(dayKey: string, tz: string): string {
  const d = startOfDayKey(dayKey, tz);
  const js = new Intl.DateTimeFormat('en-US', { timeZone: tz, weekday: 'short' }).format(d);
  const idx = WEEKDAYS.indexOf(js);
  return addDaysToKey(dayKey, -(idx === -1 ? 0 : idx));
}

/** Widest the load bar goes, as a share of the cell. */
const BAR_MAX = 100;
/** Narrow enough to read as "barely anything", wide enough to see. */
const BAR_MIN = 9;

/**
 * How much of the cell the load bar fills.
 *
 * Square-rooted, like the tide line, and for the same reason: a 57-event
 * Wednesday against a 9-event Sunday flattens every ordinary day on a linear
 * scale. Sharing the scale also means the two views agree about which days
 * look busy, which they did not when the grid used a five-step colour wash.
 */
function loadWidth(count: number, max: number): number {
  if (count === 0 || max <= 0) return 0;
  return BAR_MIN + (BAR_MAX - BAR_MIN) * Math.sqrt(count / max);
}

export type MonthGridProps = {
  events: CalEvent[];
  tz: string;
  todayKey: string;
  /** Set while one sector is selected, so the grid answers the rail. */
  sectorColor: string | null;
  onPickDay: (dayKey: string) => void;
};

export function MonthGrid({ events, tz, todayKey, sectorColor, onPickDay }: MonthGridProps) {
  // The grid starts at the current week and moves in four-week pages.
  const firstWeek = useMemo(() => mondayOf(todayKey, tz), [todayKey, tz]);
  const [page, setPage] = useState(0);
  const gridRef = useRef<HTMLDivElement | null>(null);
  const [focusKey, setFocusKey] = useState<string>(todayKey);

  const model = useMemo(() => monthModel(events), [events]);
  const max = useMemo(() => {
    let m = 0;
    for (const cell of model.values()) m = Math.max(m, cell.count);
    return m;
  }, [model]);

  const start = addDaysToKey(firstWeek, page * 28);
  const cells = useMemo(() => Array.from({ length: 28 }, (_, i) => addDaysToKey(start, i)), [start]);

  /** Four rows of seven, so the grid can carry real `role="row"` children. */
  const weeks = useMemo(
    () => Array.from({ length: 4 }, (_, w) => cells.slice(w * 7, w * 7 + 7)),
    [cells],
  );

  /**
   * The window is 28 days, not a calendar month, so name its actual span.
   * "September 2026 to October 2026" claimed two whole months for four weeks.
   */
  const rangeLabel = useMemo(() => {
    const dayMonth = new Intl.DateTimeFormat('en-US', { timeZone: tz, day: 'numeric', month: 'short' });
    const year = new Intl.DateTimeFormat('en-US', { timeZone: tz, year: 'numeric' });
    const a = startOfDayKey(start, tz);
    const b = startOfDayKey(cells[27]!, tz);
    const suffix = year.format(a) === year.format(b) ? year.format(b) : `${year.format(a)}–${year.format(b)}`;
    return `${dayMonth.format(a)} – ${dayMonth.format(b)}, ${suffix}`;
  }, [start, cells, tz]);

  const move = (deltaDays: number) => {
    const next = addDaysToKey(focusKey, deltaDays);
    // Follow the focus onto the next or previous page when it leaves this one.
    const offset = diffDayKeys(start, next);
    if (offset < 0) setPage((p) => Math.max(0, p - 1));
    else if (offset > 27) setPage((p) => p + 1);
    setFocusKey(next);
    requestAnimationFrame(() => {
      gridRef.current?.querySelector<HTMLElement>(`[data-cell="${next}"]`)?.focus();
    });
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    const map: Record<string, number> = {
      ArrowLeft: -1,
      ArrowRight: 1,
      ArrowUp: -7,
      ArrowDown: 7,
      PageUp: -28,
      PageDown: 28,
    };
    const delta = map[e.key];
    if (delta === undefined) return;
    e.preventDefault();
    move(delta);
  };

  return (
    <div className="px-4 pb-8">
      <div className="flex items-center justify-between gap-3 py-3">
        <h2 className="t-day tnum" style={{ color: 'var(--ink)' }}>
          {rangeLabel}
        </h2>
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            disabled={page === 0}
            aria-label="Previous four weeks"
            className="flex items-center justify-center rounded-[var(--r-cell)] border"
            style={{
              borderColor: 'var(--line)',
              color: 'var(--ink-2)',
              minWidth: 44,
              minHeight: 44,
              opacity: page === 0 ? 0.4 : 1,
            }}
          >
            <ChevronLeft size={18} strokeWidth={1.5} aria-hidden />
          </button>
          <button
            type="button"
            onClick={() => setPage(0)}
            className="t-meta rounded-[var(--r-cell)] border px-3"
            style={{ borderColor: 'var(--line)', color: 'var(--ink)', minHeight: 44 }}
          >
            Today
          </button>
          <button
            type="button"
            onClick={() => setPage((p) => p + 1)}
            aria-label="Next four weeks"
            className="flex items-center justify-center rounded-[var(--r-cell)] border"
            style={{ borderColor: 'var(--line)', color: 'var(--ink-2)', minWidth: 44, minHeight: 44 }}
          >
            <ChevronRight size={18} strokeWidth={1.5} aria-hidden />
          </button>
        </div>
      </div>

      <div
        ref={gridRef}
        role="grid"
        aria-label="Events by day"
        onKeyDown={onKeyDown}
        className="grid grid-cols-7 gap-1.5"
      >
        {/* role="grid" requires its cells to sit inside rows. `display: contents`
            supplies the rows to the accessibility tree without disturbing the
            CSS grid the cells are laid out on. */}
        <div role="row" style={{ display: 'contents' }}>
          {WEEKDAYS.map((w) => (
            <div
              key={w}
              role="columnheader"
              className="t-caption px-1 pb-1"
              style={{ color: 'var(--ink-2)' }}
            >
              {w}
            </div>
          ))}
        </div>

        {weeks.map((week, wi) => (
          <div role="row" key={week[0] ?? wi} style={{ display: 'contents' }}>
            {week.map((dayKey) => {
              const cell = model.get(dayKey);
              const count = cell?.count ?? 0;
              const isToday = dayKey === todayKey;
              const isPast = dayKey < todayKey;
              const width = isPast ? 0 : loadWidth(count, max);

              return (
                <button
                  key={dayKey}
                  type="button"
                  role="gridcell"
                  data-cell={dayKey}
                  data-count={count}
                  tabIndex={dayKey === focusKey ? 0 : -1}
                  aria-label={`${formatLongDay(dayKey, tz)}, ${
                    count === 1 ? '1 event' : `${count} events`
                  }`}
                  aria-current={isToday ? 'date' : undefined}
                  aria-disabled={isPast ? true : undefined}
                  onClick={() => onPickDay(dayKey)}
                  onFocus={() => setFocusKey(dayKey)}
                  className="month-cell flex min-h-[74px] flex-col items-stretch rounded-[var(--r-cell)] p-1.5 text-left sm:min-h-[116px] sm:p-2"
                  style={{
                    // A spent day keeps its place in the week but stops
                    // competing: no surface, no ring, nothing but the numeral.
                    background: isPast ? 'transparent' : 'var(--bg)',
                    boxShadow: isPast ? undefined : 'inset 0 0 0 1px var(--line)',
                  }}
                >
                  {/* A 390px screen gives each cell about 48px. Stacked, the
                      numeral and the count both stay legible there; side by
                      side they collide. */}
                  <span className="flex flex-col items-start gap-0.5 sm:flex-row sm:items-center sm:justify-between sm:gap-1">
                    {isToday ? (
                      /* The same gold coin the agenda gutter and the tide line
                         use for today, so the three views agree. Gold only
                         ever appears as a filled shape carrying navy. */
                      <span
                        className="t-tide-num flex size-[26px] items-center justify-center rounded-full sm:size-[30px]"
                        style={{ background: 'var(--gold)', color: 'var(--gold-ink)' }}
                      >
                        {Number(dayKey.slice(8, 10))}
                      </span>
                    ) : (
                      <span
                        className="t-tide-num"
                        style={{ color: isPast ? 'var(--ink-2)' : 'var(--ink)' }}
                      >
                        {Number(dayKey.slice(8, 10))}
                      </span>
                    )}
                    {count > 0 && !isPast && (
                      <span className="t-caption tnum" style={{ color: 'var(--ink-2)' }}>
                        {count}
                      </span>
                    )}
                  </span>

                  {/* Titles are dropped on a phone rather than shipped as
                      "Bi…" and "Ho…". At that width the grid answers which day
                      to look at; the names are one tap away in the list. */}
                  {!isPast && cell && cell.preview.length > 0 && (
                    <span className="mt-1.5 hidden flex-col gap-1 sm:flex">
                      {cell.preview.map((p) => (
                        <span
                          key={p.key}
                          aria-hidden
                          className="t-caption clamp-1"
                          style={{ color: 'var(--ink)' }}
                        >
                          {p.title}
                        </span>
                      ))}
                    </span>
                  )}

                  {/* One mark, doing what the colour wash and the dot row each
                      half-did: length is how full the day is, colour is what it
                      is mostly about. Segmenting it by every sector present put
                      the same six-colour rainbow in all 28 cells, which is the
                      noise the dots were already making. The busiest sector
                      alone actually varies — weekdays run to Government,
                      weekends to Culture — so the grid gains a real rhythm. */}
                  {width > 0 && cell && cell.load[0] && (
                    <span
                      aria-hidden
                      className="mt-auto h-[4px] rounded-full"
                      style={{
                        width: `${width}%`,
                        // With a sector selected the whole grid answers in
                        // that sector, exactly as the tide line does. Left to
                        // the day's own busiest sector, the two views could
                        // disagree: filtering to Health still leaves an event
                        // tagged [Community, Health] with Community primary.
                        background: sectorColor ?? `var(--sector-${cell.load[0].sector})`,
                      }}
                    />
                  )}
                </button>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}
