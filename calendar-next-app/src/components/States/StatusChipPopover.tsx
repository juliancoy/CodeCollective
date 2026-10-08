import { Popover } from '@base-ui/react/popover';
import type { ReactNode } from 'react';

/**
 * The popover half of the status chip, in its own chunk.
 *
 * Base UI's popover drags about 33 KB of shared compositing machinery, and
 * this chip sits in the brand band on every page load. The label is the part
 * that matters on arrival; the full sentence can wait for the first idle tick.
 */
export default function StatusChipPopover({
  trigger,
  body,
  openOnMount,
}: {
  trigger: ReactNode;
  body: string;
  openOnMount: boolean;
}) {
  return (
    <Popover.Root defaultOpen={openOnMount}>
      <Popover.Trigger
        className="t-caption ml-2 inline-flex items-center gap-1.5 rounded-[var(--r-pill)] px-2.5 align-middle"
        style={{ minHeight: 26, background: 'var(--brand-soft)', color: 'var(--brand-soft-ink)' }}
      >
        {trigger}
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Positioner sideOffset={8} align="start">
          <Popover.Popup
            className="t-meta"
            style={{
              maxWidth: 320,
              padding: '12px 14px',
              background: 'var(--bg)',
              color: 'var(--ink)',
              borderRadius: 'var(--r-cell)',
              boxShadow: 'var(--shadow-sheet)',
              zIndex: 70,
            }}
          >
            {body}
          </Popover.Popup>
        </Popover.Positioner>
      </Popover.Portal>
    </Popover.Root>
  );
}
