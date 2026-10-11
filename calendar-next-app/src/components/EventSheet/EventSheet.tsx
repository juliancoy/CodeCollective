import { Dialog } from '@base-ui/react/dialog';
import { Drawer } from '@base-ui/react/drawer';
import { Menu } from '@base-ui/react/menu';
import {
  CalendarPlus,
  Copy,
  ExternalLink,
  Flag,
  MapPin,
  MoreHorizontal,
  Share2,
  X,
} from 'lucide-react';
import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import {
  buildIcs,
  eventJson,
  googleCalendarUrl,
  icsFilename,
  mapsUrl,
  reportMailto,
} from '../../data/calendarLinks';
import { SECTOR_LABEL } from '../../data/sectors';
import { formatLongDay, formatTimeRange, relativeTime, statusChip } from '../../data/time';
import type { CalEvent } from '../../data/types';
import { Description } from './Description';

export type EventSheetProps = {
  event: CalEvent | null;
  tz: string;
  now: Date;
  /** Next few events from the same organizer. */
  moreFromOrganizer: CalEvent[];
  isPhone: boolean;
  onClose: () => void;
  onOpenOther: (key: string) => void;
  onToast: (message: string) => void;
};

function downloadIcs(event: CalEvent, onToast: (m: string) => void) {
  const blob = new Blob([buildIcs(event)], { type: 'text/calendar;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = icsFilename(event);
  document.body.appendChild(a);
  a.click();
  a.remove();
  // Revoke on the next tick so the download has certainly started.
  setTimeout(() => URL.revokeObjectURL(url), 2000);
  onToast('Event file downloaded');
}

async function copyText(text: string, onToast: (m: string) => void, message: string) {
  try {
    await navigator.clipboard.writeText(text);
    onToast(message);
  } catch {
    onToast('Could not copy. Try again.');
  }
}

const menuPopupStyle: React.CSSProperties = {
  background: 'var(--bg)',
  borderRadius: 'var(--r-cell)',
  boxShadow: 'var(--shadow-sheet)',
  padding: 6,
  minWidth: 220,
  zIndex: 80,
};

const menuItemStyle: React.CSSProperties = {
  display: 'block',
  width: '100%',
  textAlign: 'left',
  padding: '10px 12px',
  borderRadius: 'var(--r-cell)',
  color: 'var(--ink)',
  minHeight: 44,
};

function Body({
  event,
  tz,
  now,
  moreFromOrganizer,
  onOpenOther,
}: Omit<EventSheetProps, 'isPhone' | 'onClose' | 'event' | 'onToast'> & { event: CalEvent }) {
  const [imageFailed, setImageFailed] = useState(false);
  const status = statusChip(event, tz, now);
  const maps = mapsUrl(event);
  const timeText = event.allDay ? 'All day' : formatTimeRange(event.start, event.end, tz);

  return (
    <div className="flex flex-col gap-5 px-5 pb-6">
      {event.image && !imageFailed && (
        <img
          src={event.image}
          alt=""
          onError={() => setImageFailed(true)}
          className="aspect-video w-full rounded-[var(--r-image)] object-cover"
          style={{ background: 'var(--bg-soft)' }}
        />
      )}

      <div>
        <Dialog.Title className="t-sheet-title" style={{ color: 'var(--ink)' }}>
          {event.title}
        </Dialog.Title>

        <p className="t-meta mt-2 flex flex-wrap items-center gap-2" style={{ color: 'var(--ink-2)' }}>
          <time dateTime={event.start.toISOString()}>
            {formatLongDay(event.dayKey, tz)}, {timeText}
          </time>
          {event.cancelled ? (
            <span
              className="t-caption rounded-[var(--r-pill)] px-2 py-[2px]"
              style={{ background: 'var(--sector-politics-tint)', color: 'var(--danger)' }}
            >
              Cancelled
            </span>
          ) : status ? (
            <span
              className="t-caption flex items-center gap-1 rounded-[var(--r-pill)] px-2 py-[2px]"
              // Gold is only ever a filled shape carrying navy text. As ink on
              // white it measures 1.9:1, which is the reason for that rule.
              style={
                status === 'Happening now'
                  ? { background: 'var(--gold)', color: 'var(--gold-ink)' }
                  : { background: 'var(--brand-soft)', color: 'var(--brand-soft-ink)' }
              }
            >
              {status === 'Happening now' && (
                <span
                  aria-hidden
                  className="live-dot h-2 w-2 rounded-full"
                  style={{ background: 'var(--gold-ink)' }}
                />
              )}
              {status}
            </span>
          ) : null}
        </p>
      </div>

      <div className="flex items-start gap-2">
        <MapPin size={18} strokeWidth={1.5} aria-hidden className="mt-[2px] shrink-0" style={{ color: 'var(--ink-2)' }} />
        <div className="min-w-0">
          {/* Never say "Location not listed" above an address. Some rows carry
              only a country, which is not a venue but is not nothing either. */}
          <p className="t-body" style={{ color: 'var(--ink)' }}>
            {event.venue ?? event.address ?? 'Location not listed'}
          </p>
          {event.venue && event.address && (
            <p className="t-meta" style={{ color: 'var(--ink-2)' }}>
              {event.address}
              {event.locality && event.address.includes(event.locality)
                ? ''
                : event.locality
                  ? `, ${event.locality}`
                  : ''}
            </p>
          )}
          {maps && (
            <a
              href={maps}
              target="_blank"
              rel="noopener noreferrer"
              className="t-meta mt-1 inline-block underline"
              style={{ color: 'var(--brand-on-bg)', textUnderlineOffset: '2px' }}
            >
              Open in Maps
            </a>
          )}
        </div>
      </div>

      <div className="flex items-center gap-3">
        {event.orgLogo && (
          <img
            src={event.orgLogo}
            alt=""
            width={32}
            height={32}
            className="h-8 w-8 rounded-full object-contain"
            style={{ background: 'var(--bg-soft)' }}
          />
        )}
        <p className="t-body" style={{ color: 'var(--ink)' }}>
          {event.orgName}
        </p>
      </div>

      <ul className="m-0 flex list-none flex-wrap gap-2 p-0">
        {event.sectors.map((s) => (
          <li
            key={s}
            className="t-caption rounded-[var(--r-pill)] px-3 py-1"
            style={{ background: `var(--sector-${s}-tint)`, color: 'var(--ink)' }}
          >
            {SECTOR_LABEL[s]}
          </li>
        ))}
      </ul>

      <Description markdown={event.descriptionMd} />

      {moreFromOrganizer.length > 0 && (
        <section>
          <h3 className="t-body font-semibold" style={{ color: 'var(--ink)' }}>
            More from {event.orgName}
          </h3>
          <ul className="row-list mt-2">
            {moreFromOrganizer.map((e) => (
              <li key={e.key}>
                <button
                  type="button"
                  onClick={() => onOpenOther(e.key)}
                  className="w-full py-2 text-left"
                >
                  <span className="t-meta block" style={{ color: 'var(--ink)' }}>
                    {e.title}
                  </span>
                  <span className="t-caption block" style={{ color: 'var(--ink-2)' }}>
                    {formatLongDay(e.dayKey, tz)}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}

      <p className="t-caption" style={{ color: 'var(--ink-2)' }}>
        Listed from {event.sourceGroup}.
        {event.scrapedAt && <> Checked {relativeTime(event.scrapedAt, now)}.</>}
      </p>
    </div>
  );
}

function Actions({
  event,
  onToast,
}: {
  event: CalEvent;
  onToast: (m: string) => void;
}) {
  const share = async () => {
    const url = `${window.location.origin}${window.location.pathname}?city=${
      new URLSearchParams(window.location.search).get('city') ?? 'baltimore'
    }&event=${encodeURIComponent(event.key)}`;
    if (navigator.share) {
      try {
        await navigator.share({ title: event.title, url });
        return;
      } catch {
        // The visitor dismissed the sheet; fall through to copying.
      }
    }
    await copyText(url, onToast, 'Link copied');
  };

  return (
    <div
      className="flex flex-wrap items-center gap-2 border-t px-5 py-4"
      style={{ borderColor: 'var(--line)', background: 'var(--bg)' }}
    >
      <a
        href={event.url}
        target="_blank"
        rel="noopener noreferrer"
        className="t-meta flex items-center gap-2 rounded-[var(--r-pill)] px-4 py-2.5"
        style={{ background: 'var(--brand)', color: 'var(--brand-ink)', minHeight: 44 }}
      >
        <ExternalLink size={16} strokeWidth={1.5} aria-hidden />
        View event page
      </a>

      <Menu.Root>
        <Menu.Trigger
          className="t-meta flex items-center gap-2 rounded-[var(--r-pill)] border px-4 py-2.5"
          style={{ borderColor: 'var(--line)', color: 'var(--ink)', minHeight: 44 }}
        >
          <CalendarPlus size={16} strokeWidth={1.5} aria-hidden />
          Add to calendar
        </Menu.Trigger>
        <Menu.Portal>
          <Menu.Positioner sideOffset={8}>
            <Menu.Popup style={menuPopupStyle}>
              <Menu.LinkItem
                href={googleCalendarUrl(event)}
                target="_blank"
                rel="noopener noreferrer"
                className="t-meta"
                style={menuItemStyle}
              >
                Google Calendar
              </Menu.LinkItem>
              <Menu.Item
                className="t-meta"
                style={menuItemStyle}
                onClick={() => downloadIcs(event, onToast)}
              >
                Apple Calendar or Outlook
              </Menu.Item>
            </Menu.Popup>
          </Menu.Positioner>
        </Menu.Portal>
      </Menu.Root>

      <button
        type="button"
        onClick={() => void share()}
        className="t-meta flex items-center gap-2 rounded-[var(--r-pill)] border px-4 py-2.5"
        style={{ borderColor: 'var(--line)', color: 'var(--ink)', minHeight: 44 }}
      >
        <Share2 size={16} strokeWidth={1.5} aria-hidden />
        Share
      </button>

      <Menu.Root>
        <Menu.Trigger
          aria-label="More actions"
          className="flex items-center justify-center rounded-[var(--r-pill)] border px-3"
          style={{ borderColor: 'var(--line)', color: 'var(--ink)', minHeight: 44, minWidth: 44 }}
        >
          <MoreHorizontal size={18} strokeWidth={1.5} aria-hidden />
        </Menu.Trigger>
        <Menu.Portal>
          <Menu.Positioner sideOffset={8} align="end">
            <Menu.Popup style={menuPopupStyle}>
              <Menu.Item
                className="t-meta flex items-center gap-2"
                style={menuItemStyle}
                onClick={() => void copyText(eventJson(event), onToast, 'Event details copied')}
              >
                <Copy size={16} strokeWidth={1.5} aria-hidden />
                Copy event details (JSON)
              </Menu.Item>
              <Menu.LinkItem
                href={reportMailto(event)}
                className="t-meta flex items-center gap-2"
                style={menuItemStyle}
              >
                <Flag size={16} strokeWidth={1.5} aria-hidden />
                Report a problem
              </Menu.LinkItem>
            </Menu.Popup>
          </Menu.Positioner>
        </Menu.Portal>
      </Menu.Root>
    </div>
  );
}

/**
 * Detail opens in place so the list position is never lost: a drawer on
 * phones, a sheet over the map column on larger screens. Escape and the back
 * button both close it, and focus returns to the row that opened it.
 */
export function EventSheet({
  event,
  tz,
  now,
  moreFromOrganizer,
  isPhone,
  onClose,
  onOpenOther,
  onToast,
}: EventSheetProps) {
  const open = event !== null;
  const lastKey = useRef<string | null>(null);
  // Keep the last event around during the close animation so the sheet does
  // not blank out as it leaves.
  const shown = useMemo(() => event, [event]);

  useEffect(() => {
    if (event) lastKey.current = event.key;
  }, [event]);

  // Return focus to the originating row.
  useEffect(() => {
    if (open || lastKey.current === null) return;
    const row = document.querySelector<HTMLElement>(`[data-event-key="${CSS.escape(lastKey.current)}"]`);
    row?.focus();
  }, [open]);

  if (!shown) return null;

  const content: ReactNode = (
    <>
      <div className="flex items-center justify-between px-5 pt-4 pb-2">
        <span className="t-caption" style={{ color: 'var(--ink-2)' }}>
          Event
        </span>
        <Dialog.Close
          aria-label="Close"
          className="flex items-center justify-center rounded-full"
          style={{ color: 'var(--ink-2)', minWidth: 44, minHeight: 44 }}
        >
          <X size={20} strokeWidth={1.5} aria-hidden />
        </Dialog.Close>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto">
        <Body
          event={shown}
          tz={tz}
          now={now}
          moreFromOrganizer={moreFromOrganizer}
          onOpenOther={onOpenOther}
        />
      </div>
      <Actions event={shown} onToast={onToast} />
    </>
  );

  if (isPhone) {
    return (
      <Drawer.Root open={open} onOpenChange={(next) => !next && onClose()} swipeDirection="down">
        <Drawer.Portal>
          <Drawer.Backdrop style={{ background: 'var(--scrim)', position: 'fixed', inset: 0, zIndex: 70 }} />
          <Drawer.Popup
            className="flex flex-col"
            style={{
              position: 'fixed',
              insetInline: 0,
              bottom: 0,
              zIndex: 71,
              maxHeight: '92dvh',
              background: 'var(--bg)',
              borderTopLeftRadius: 'var(--r-sheet)',
              borderTopRightRadius: 'var(--r-sheet)',
              boxShadow: 'var(--shadow-sheet)',
            }}
          >
            <Drawer.SwipeArea className="flex justify-center py-2">
              <span
                aria-hidden
                className="block h-1 w-10 rounded-full"
                style={{ background: 'var(--line)' }}
              />
            </Drawer.SwipeArea>
            {content}
          </Drawer.Popup>
        </Drawer.Portal>
      </Drawer.Root>
    );
  }

  return (
    <Dialog.Root open={open} onOpenChange={(next) => !next && onClose()} modal={false}>
      <Dialog.Portal>
        <Dialog.Popup
          className="flex flex-col"
          style={{
            position: 'fixed',
            top: 'calc(var(--chrome-h) + 8px)',
            right: 16,
            bottom: 16,
            zIndex: 71,
            width: 'min(520px, calc(100vw - 32px))',
            background: 'var(--bg)',
            borderRadius: 'var(--r-sheet)',
            boxShadow: 'var(--shadow-sheet)',
            overflow: 'hidden',
          }}
        >
          {content}
        </Dialog.Popup>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
