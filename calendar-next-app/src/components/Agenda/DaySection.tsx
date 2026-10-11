import { useState } from 'react';
import { SUBGROUP_PREVIEW, type DaySectionModel, type TimeGroupModel } from '../../data/pipeline';
import { diffDayKeys, formatLongDay, tideLabels } from '../../data/time';
import { EventRow } from './EventRow';

export type DaySectionProps = {
  day: DaySectionModel;
  tz: string;
  todayKey: string;
  selectedKey: string | null;
  flashKey: string | null;
  onOpen: (key: string) => void;
  onHover: (key: string | null) => void;
  /** Phones swap the gutter for a compact sticky header row. */
  isPhone: boolean;
};

export function countLabel(n: number): string {
  return n === 1 ? '1 event' : `${n} events`;
}

type RowListProps = Omit<DaySectionProps, 'day' | 'todayKey' | 'isPhone'>;

function RowList({
  events,
  tz,
  selectedKey,
  flashKey,
  onOpen,
  onHover,
}: RowListProps & { events: DaySectionModel['events'] }) {
  return (
    <ul className="m-0 list-none p-0">
      {events.map((e) => (
        <EventRow
          key={e.key}
          event={e}
          tz={tz}
          selected={selectedKey === e.key}
          flash={flashKey === e.key}
          onOpen={onOpen}
          onHover={onHover}
        />
      ))}
    </ul>
  );
}

/** A run of rows under one subheading, with the rest behind an expander. */
function TimeGroup({ group, ...rest }: { group: TimeGroupModel } & RowListProps) {
  const [expanded, setExpanded] = useState(false);
  const isLive = group.id === 'now';
  // Live events are never hidden behind an expander.
  const shown = expanded || isLive ? group.events : group.events.slice(0, SUBGROUP_PREVIEW);
  const hidden = group.events.length - shown.length;

  return (
    <div>
      <h3
        className="t-group flex items-center gap-2 px-3 pt-3 pb-1"
        style={{ color: 'var(--ink-2)' }}
      >
        {isLive ? (
          /* Gold as a filled chip, never as a dot or as ink: on white it
             measures 1.9:1 either way. */
          <span
            className="live-dot flex items-center gap-1.5 rounded-[var(--r-pill)] px-2 py-[2px]"
            style={{ background: 'var(--gold)', color: 'var(--gold-ink)' }}
          >
            {group.label}
            <span className="tnum">{group.events.length}</span>
          </span>
        ) : (
          <>
            <span>{group.label}</span>
            <span className="tnum">{group.events.length}</span>
          </>
        )}
      </h3>
      <RowList events={shown} {...rest} />
      {hidden > 0 && (
        <button
          type="button"
          onClick={() => setExpanded(true)}
          className="t-meta w-full rounded-[var(--r-card)] px-3 py-3 text-left"
          style={{ color: 'var(--brand-on-bg)' }}
        >
          Show {hidden} more {group.label.toLowerCase()} event{hidden === 1 ? '' : 's'}
        </button>
      )}
    </div>
  );
}

/**
 * v1 gave each day a full-width header band, so a loud horizontal rule cut the
 * list every few rows. v2 moves the date into a sticky gutter beside its rows:
 * the day stays legible while you read it, and the list keeps one continuous
 * column. The gutter numeral is the single weight-600 element in this zone.
 */
export function DaySection({ day, tz, todayKey, isPhone, ...rest }: DaySectionProps) {
  const { weekday, numeral } = tideLabels(day.dayKey, tz);
  const delta = diffDayKeys(todayKey, day.dayKey);
  const relative = delta === 0 ? 'Today' : delta === 1 ? 'Tomorrow' : null;
  const isToday = delta === 0;
  const fullDate = formatLongDay(day.dayKey, tz);

  const body = day.groups ? (
    day.groups.map((g) => <TimeGroup key={g.id} group={g} tz={tz} {...rest} />)
  ) : (
    <RowList events={day.events} tz={tz} {...rest} />
  );

  if (isPhone) {
    return (
      <section className="day-section" data-day={day.dayKey} aria-labelledby={`h-${day.dayKey}`}>
        <header
          className="sticky z-10 flex items-baseline justify-between gap-3 border-b px-3 py-2"
          style={{
            top: 'calc(var(--band-h) + var(--control-h) + var(--tide-h))',
            borderColor: 'var(--line)',
            background: 'var(--bg)',
          }}
        >
          <h2 id={`h-${day.dayKey}`} className="min-w-0">
            <span className="sr-only">
              {fullDate}
              {relative ? `, ${relative}` : ''}
            </span>
            <span aria-hidden className="t-row-title" style={{ color: 'var(--ink)' }}>
              {weekday} {numeral}
            </span>
            {relative && (
              <span aria-hidden className="t-gutter-rel ml-2" style={{ color: 'var(--ink-2)' }}>
                {relative}
              </span>
            )}
          </h2>
          <span className="t-gutter-count tnum shrink-0" style={{ color: 'var(--ink-2)' }}>
            {countLabel(day.count)}
          </span>
        </header>
        {body}
      </section>
    );
  }

  return (
    <section
      className="day-section grid grid-cols-[96px_1fr] gap-4"
      data-day={day.dayKey}
      aria-labelledby={`h-${day.dayKey}`}
    >
      <div
        className="sticky self-start pt-3"
        style={{ top: 'calc(var(--band-h) + var(--control-h) + var(--tide-h) + 12px)' }}
      >
        <h2 id={`h-${day.dayKey}`}>
          <span className="sr-only">
            {fullDate}
            {relative ? `, ${relative}` : ''}, {countLabel(day.count)}
          </span>
          <span aria-hidden className="t-gutter-day block" style={{ color: 'var(--ink-2)' }}>
            {weekday}
          </span>
          <span aria-hidden className="mt-[2px] block">
            {isToday ? (
              /* The one place gold appears in the list: today's coin. */
              <span
                className="t-gutter-num flex items-center justify-center rounded-full"
                style={{
                  width: 46,
                  height: 46,
                  background: 'var(--gold)',
                  color: 'var(--gold-ink)',
                }}
              >
                {numeral}
              </span>
            ) : (
              <span className="t-gutter-num block" style={{ color: 'var(--gutter-num)' }}>
                {numeral}
              </span>
            )}
          </span>
          {relative && (
            <span aria-hidden className="t-gutter-rel mt-1 block" style={{ color: 'var(--ink-2)' }}>
              {relative}
            </span>
          )}
          <span
            aria-hidden
            className="t-gutter-count tnum mt-1 block"
            style={{ color: 'var(--ink-2)' }}
          >
            {countLabel(day.count)}
          </span>
        </h2>
      </div>

      <div className="min-w-0">{body}</div>
    </section>
  );
}
