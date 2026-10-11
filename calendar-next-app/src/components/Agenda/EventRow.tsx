import { Video } from 'lucide-react';
import { memo } from 'react';
import { SECTOR_LABEL } from '../../data/sectors';
import { formatShortDay, formatTime } from '../../data/time';
import type { CalEvent } from '../../data/types';
import { EventVisual } from './EventVisual';

/**
 * Rows are time-first, not image-first. A home listing is chosen by how it
 * looks; an event is chosen by when it happens.
 *
 * v2 compresses the row from three stacked meta lines to one, and the visual
 * from a 64px tile to a 44px circle, which roughly doubles how many events fit
 * on a screen. The row is an anchor to `?event=<key>`, so middle-click and
 * Cmd-click open a tab while a plain click opens the sheet in place.
 */
export type EventRowProps = {
  event: CalEvent;
  tz: string;
  selected: boolean;
  onOpen: (key: string) => void;
  onHover: (key: string | null) => void;
  /** Set when a map pin was just clicked, to flash the row. */
  flash: boolean;
};

function Badge({ tone, children }: { tone: 'danger' | 'quiet' | 'brand'; children: string }) {
  const style =
    tone === 'danger'
      ? { background: 'var(--sector-politics-tint)', color: 'var(--danger)' }
      : tone === 'brand'
        ? { background: 'var(--brand-soft)', color: 'var(--brand-soft-ink)' }
        : { background: 'var(--bg-soft)', color: 'var(--ink-2)' };
  return (
    <span
      className="t-caption ml-2 inline-block shrink-0 rounded-[var(--r-pill)] px-2 py-[1px] align-middle"
      style={style}
    >
      {children}
    </span>
  );
}

export const EventRow = memo(function EventRow({
  event,
  tz,
  selected,
  onOpen,
  onHover,
  flash,
}: EventRowProps) {
  // One truncated line rather than v1's three: organizer, venue, locality.
  const place = event.online
    ? null
    : [event.venue, event.locality].filter(Boolean).join(', ') ||
      event.address ||
      'Location not listed';

  const sectorNames = event.sectors.map((s) => SECTOR_LABEL[s]).join(', ');
  const timeText = event.allDay
    ? 'All day'
    : event.end
      ? `${formatTime(event.start, tz)} to ${formatTime(event.end, tz)}`
      : formatTime(event.start, tz);
  const description = [
    timeText,
    sectorNames,
    event.orgName,
    event.online ? 'Online' : place,
    event.cancelled ? 'Cancelled' : null,
  ]
    .filter(Boolean)
    .join('. ');

  return (
    <li>
      <a
        href={`?event=${encodeURIComponent(event.key)}`}
        aria-current={selected ? 'true' : undefined}
        aria-describedby={`d-${event.key}`}
        data-event-key={event.key}
        title={event.title}
        onClick={(e) => {
          if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0) return;
          e.preventDefault();
          onOpen(event.key);
        }}
        onPointerEnter={() => onHover(event.key)}
        onPointerLeave={() => onHover(null)}
        onFocus={() => onHover(event.key)}
        onBlur={() => onHover(null)}
        className={`row-lift focus-inset grid grid-cols-[72px_1fr_44px] items-start gap-3 rounded-[var(--r-card)] px-3 py-[14px] ${
          flash ? 'row-flash' : ''
        } ${selected ? 'row-selected' : ''}`}
      >
        <span className="pt-[1px]">
          {event.allDay ? (
            <span className="t-row-time block" style={{ color: 'var(--ink)' }}>
              All day
            </span>
          ) : (
            <>
              <time
                dateTime={event.start.toISOString()}
                className="t-row-time block"
                style={{ color: 'var(--ink)' }}
              >
                {formatTime(event.start, tz)}
              </time>
              {event.end && (
                <time
                  dateTime={event.end.toISOString()}
                  className="t-row-time-end block"
                  style={{ color: 'var(--ink-2)' }}
                >
                  {formatTime(event.end, tz)}
                </time>
              )}
            </>
          )}
        </span>

        <span className="min-w-0">
          <span className="t-row-title clamp-2 block" style={{ color: 'var(--ink)' }}>
            {event.title}
            {event.cancelled && <Badge tone="danger">Cancelled</Badge>}
            {event.featured && <Badge tone="brand">Code Collective</Badge>}
            {event.recurring && !event.cancelled && <Badge tone="quiet">Repeats</Badge>}
          </span>

          <span
            className="t-row-meta mt-[3px] flex min-w-0 items-center gap-1.5"
            style={{ color: 'var(--ink-2)' }}
          >
            <span
              aria-hidden
              className="h-2 w-2 shrink-0 rounded-full"
              style={{ background: `var(--sector-${event.primarySector})` }}
            />
            <span className="truncate">
              {event.orgName}
              {place ? `, ${place}` : ''}
            </span>
            {event.online && (
              <span
                className="t-caption flex shrink-0 items-center gap-1 rounded-[var(--r-pill)] px-2"
                style={{ background: 'var(--brand-soft)', color: 'var(--brand-soft-ink)' }}
              >
                <Video size={11} strokeWidth={2} aria-hidden />
                Online
              </span>
            )}
            {event.endDayKey && (
              <span className="t-caption shrink-0">Until {formatShortDay(event.endDayKey, tz)}</span>
            )}
          </span>

          <span id={`d-${event.key}`} className="sr-only">
            {description}
          </span>
        </span>

        <EventVisual event={event} />
      </a>
    </li>
  );
});
