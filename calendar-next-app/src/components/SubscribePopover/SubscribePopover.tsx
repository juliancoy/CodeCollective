import { Dialog } from '@base-ui/react/dialog';
import { Download, ExternalLink, X } from 'lucide-react';
import {
  googleSubscribeUrl,
  icsFeedUrl,
  webcalSubscribeUrl,
} from '../../data/calendarLinks';
import type { CityId } from '../../data/types';

const rowStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: 12,
  padding: '12px 14px',
  borderRadius: 'var(--r-cell)',
  color: 'var(--ink)',
  minHeight: 44,
  border: '1px solid var(--line)',
};

export function SubscribePopover({
  open,
  onOpenChange,
  city,
  cityLabel,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  city: CityId;
  cityLabel: string;
}) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Backdrop
          style={{ background: 'var(--scrim)', position: 'fixed', inset: 0, zIndex: 70 }}
        />
        <Dialog.Popup
          style={{
            position: 'fixed',
            top: '50%',
            left: '50%',
            transform: 'translate(-50%, -50%)',
            zIndex: 71,
            width: 'min(420px, calc(100vw - 32px))',
            background: 'var(--bg)',
            borderRadius: 'var(--r-sheet)',
            boxShadow: 'var(--shadow-sheet)',
            padding: 20,
          }}
        >
          <div className="mb-1 flex items-start justify-between gap-3">
            <Dialog.Title className="t-sheet-title" style={{ color: 'var(--ink)' }}>
              Subscribe to {cityLabel} events
            </Dialog.Title>
            <Dialog.Close
              aria-label="Close"
              className="flex shrink-0 items-center justify-center rounded-full"
              style={{ color: 'var(--ink-2)', minWidth: 44, minHeight: 44 }}
            >
              <X size={20} strokeWidth={1.5} aria-hidden />
            </Dialog.Close>
          </div>

          <Dialog.Description className="t-body" style={{ color: 'var(--ink-2)' }}>
            Every {cityLabel} event in your calendar app. It updates on its own.
          </Dialog.Description>

          <div className="mt-4 flex flex-col gap-2">
            <a
              href={googleSubscribeUrl(city)}
              target="_blank"
              rel="noopener noreferrer"
              className="t-body"
              style={rowStyle}
            >
              <ExternalLink size={18} strokeWidth={1.5} aria-hidden style={{ color: 'var(--ink-2)' }} />
              Google Calendar
            </a>
            <a href={webcalSubscribeUrl(city)} className="t-body" style={rowStyle}>
              <ExternalLink size={18} strokeWidth={1.5} aria-hidden style={{ color: 'var(--ink-2)' }} />
              Apple Calendar or Outlook
            </a>
            <a href={icsFeedUrl(city)} download className="t-body" style={rowStyle}>
              <Download size={18} strokeWidth={1.5} aria-hidden style={{ color: 'var(--ink-2)' }} />
              Download .ics file
            </a>
          </div>

          <p className="t-caption mt-4" style={{ color: 'var(--ink-2)' }}>
            Includes all events for this city. Filters do not apply.
          </p>
        </Dialog.Popup>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
