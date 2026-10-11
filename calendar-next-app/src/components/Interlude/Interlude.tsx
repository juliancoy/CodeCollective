import { useMemo, useState } from 'react';
import { addDaysToKey, diffDayKeys, formatShortDay, formatTime, tideLabels } from '../../data/time';
import type { CalEvent } from '../../data/types';

export type InterludeProps = {
  events: CalEvent[];
  tz: string;
  todayKey: string;
  /** 0 = Sunday, in the city's zone. */
  todayWeekday: number;
  /** True when a filter or a search is active, which hides the interlude. */
  suppressed: boolean;
  onOpen: (key: string) => void;
  onSeeAll: () => void;
};

const TECH_FIRST = new Set(['technology', 'entrepreneurship', 'makerspace']);

/**
 * Pick up to eight, by a rule a visitor could be told:
 * Code Collective first, then anything with a picture, then the builder
 * sectors, then earliest start. No scoring, no surprises.
 */
function pickWeekend(events: CalEvent[], from: string, to: string): CalEvent[] {
  return events
    .filter((e) => e.dayKey >= from && e.dayKey <= to)
    .sort((a, b) => {
      if (a.featured !== b.featured) return a.featured ? -1 : 1;
      const aImg = a.image !== null;
      const bImg = b.image !== null;
      if (aImg !== bImg) return aImg ? -1 : 1;
      const aTech = TECH_FIRST.has(a.primarySector);
      const bTech = TECH_FIRST.has(b.primarySector);
      if (aTech !== bTech) return aTech ? -1 : 1;
      return a.start.getTime() - b.start.getTime();
    })
    .slice(0, 8);
}

/**
 * The poster fallback. Typographic, varies by sector, and never a generic
 * icon: 68% of the feed has an image, so this stands in often enough that a
 * repeated placeholder would define the look of the page.
 */
function Poster({ event, tz }: { event: CalEvent; tz: string }) {
  const { weekday, numeral } = tideLabels(event.dayKey, tz);
  return (
    <span
      aria-hidden
      className="relative flex aspect-[4/3] w-full flex-col justify-between overflow-hidden rounded-[var(--r-image)] p-3"
      style={{
        background: `var(--sector-${event.primarySector}-tint)`,
        color: `var(--sector-${event.primarySector})`,
      }}
    >
      <span
        className="leading-none"
        style={{ fontStretch: '75%', fontWeight: 600, color: 'var(--ink)' }}
      >
        <span className="block" style={{ fontSize: 15, lineHeight: '18px' }}>
          {weekday}
        </span>
        <span className="block" style={{ fontSize: 40, lineHeight: '40px' }}>
          {numeral}
        </span>
      </span>
      <span className="flex items-center gap-2">
        <span
          className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full"
          style={{
            // Same pairing as the row avatar: the tint carries the sector,
            // ink carries the letters. The inverse measures about 4.3:1.
            background: 'var(--bg)',
            color: 'var(--ink)',
            fontSize: 11,
            fontWeight: 600,
          }}
        >
          {event.initials}
        </span>
        <span className="t-caption truncate" style={{ color: 'var(--ink-2)' }}>
          {event.orgName}
        </span>
      </span>
    </span>
  );
}

function Card({
  event,
  tz,
  onOpen,
}: {
  event: CalEvent;
  tz: string;
  onOpen: (key: string) => void;
}) {
  const [failed, setFailed] = useState(false);
  const place = event.online
    ? 'Online'
    : [event.venue, event.locality].filter(Boolean).join(', ') || 'Location not listed';

  return (
    <li className="w-[232px] shrink-0" style={{ scrollSnapAlign: 'start' }}>
      <a
        href={`?event=${encodeURIComponent(event.key)}`}
        onClick={(e) => {
          if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0) return;
          e.preventDefault();
          onOpen(event.key);
        }}
        className="interlude-card focus-inset block rounded-[var(--r-image)]"
      >
        <span className="interlude-frame block overflow-hidden rounded-[var(--r-image)]">
          {event.image && !failed ? (
            <img
              src={event.image}
              alt=""
              loading="lazy"
              decoding="async"
              onError={() => setFailed(true)}
              className="interlude-img aspect-[4/3] w-full object-cover"
              style={{ background: 'var(--bg-soft)' }}
            />
          ) : (
            <Poster event={event} tz={tz} />
          )}
        </span>
        <span className="t-caption tnum mt-2 block" style={{ color: 'var(--ink-2)' }}>
          {formatShortDay(event.dayKey, tz)}
          {event.allDay ? '' : `, ${formatTime(event.start, tz)}`}
        </span>
        <span className="t-row-title clamp-2 mt-0.5 block" style={{ color: 'var(--ink)' }}>
          {event.title}
        </span>
        <span className="t-row-meta mt-0.5 block truncate" style={{ color: 'var(--ink-2)' }}>
          {place}
        </span>
      </a>
    </li>
  );
}

/**
 * An interlude in the agenda rather than a banner above it, inserted after
 * today so today's events keep the top of the page. Skipped from Friday to
 * Sunday, when the weekend is already the first thing you see.
 */
export function Interlude({
  events,
  tz,
  todayKey,
  todayWeekday,
  suppressed,
  onOpen,
  onSeeAll,
}: InterludeProps) {
  const weekendIsHere = todayWeekday === 5 || todayWeekday === 6 || todayWeekday === 0;

  const picks = useMemo(() => {
    if (suppressed || weekendIsHere) return [];
    const toSaturday = todayWeekday === 0 ? -1 : 6 - todayWeekday;
    const sat = addDaysToKey(todayKey, toSaturday);
    const sun = addDaysToKey(sat, 1);
    if (diffDayKeys(todayKey, sat) < 0) return [];
    return pickWeekend(events, sat, sun);
  }, [events, todayKey, todayWeekday, suppressed, weekendIsHere]);

  const featured = useMemo(() => events.filter((e) => e.featured).slice(0, 8), [events]);

  if (picks.length === 0 && featured.length === 0) return null;

  const which = picks.length > 0 ? picks : featured;
  const heading = picks.length > 0 ? 'This weekend' : 'From Code Collective';

  return (
    <section className="py-5" aria-labelledby="interlude-heading">
      <div className="flex items-baseline justify-between gap-3 px-3">
        <h2 id="interlude-heading" className="t-section" style={{ color: 'var(--ink)' }}>
          {heading}
        </h2>
        {picks.length > 0 && (
          <button
            type="button"
            onClick={onSeeAll}
            className="t-meta shrink-0"
            style={{ color: 'var(--brand-on-bg)', minHeight: 32 }}
          >
            See all {picks.length}
          </button>
        )}
      </div>

      <ul
        className="no-scrollbar m-0 mt-3 flex list-none gap-4 overflow-x-auto px-3 pb-1"
        style={{ scrollSnapType: 'x proximity' }}
      >
        {which.map((e) => (
          <Card key={e.key} event={e} tz={tz} onOpen={onOpen} />
        ))}
      </ul>
    </section>
  );
}
