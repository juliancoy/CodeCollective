import { Popover } from '@base-ui/react/popover';
import { useEffect, useState } from 'react';
import { CITIES } from '../../data/cities';
import type { CityId, DatePreset } from '../../data/types';
import { WHEN_OPTIONS, segmentClass, whenLabel } from './pillShared';

/**
 * The two popover segments, split into their own chunk.
 *
 * Base UI's popover pulls in the floating-ui compositing machinery, which is
 * about 22 KB gzipped of the initial payload for something nobody can see
 * until they click. The pill renders plain buttons first and swaps these in on
 * the first idle tick, so the interaction is still instant.
 */
const popupStyle: React.CSSProperties = {
  background: 'var(--bg)',
  borderRadius: 'var(--r-sheet)',
  boxShadow: 'var(--shadow-sheet)',
  padding: 8,
  minWidth: 220,
  maxWidth: 'calc(100vw - 24px)',
  maxHeight: 'var(--available-height, calc(100dvh - 24px))',
  overflowY: 'auto',
  color: 'var(--ink)',
};

function OptionList({
  options,
  selected,
  onPick,
}: {
  options: ReadonlyArray<{ id: string; label: string }>;
  selected: string;
  onPick: (id: string) => void;
}) {
  return (
    <ul className="m-0 list-none p-0">
      {options.map((o) => (
        <li key={o.id}>
          <button
            type="button"
            onClick={() => onPick(o.id)}
            aria-pressed={selected === o.id}
            className="t-body w-full rounded-[var(--r-cell)] px-3 py-2 text-left"
            style={{
              color: 'var(--ink)',
              background: selected === o.id ? 'var(--brand-soft)' : 'transparent',
              minHeight: 44,
            }}
          >
            {o.label}
          </button>
        </li>
      ))}
    </ul>
  );
}

export type PillSegmentsProps = {
  city: CityId;
  cityLabel: string;
  datePreset: DatePreset;
  from: string | null;
  to: string | null;
  /** Which segment the visitor clicked before this chunk had loaded. */
  openOnMount: 'where' | 'when' | null;
  onCity: (city: CityId) => void;
  onWhen: (preset: DatePreset, from?: string | null, to?: string | null) => void;
};

export default function PillSegments({
  city,
  cityLabel,
  datePreset,
  from,
  to,
  openOnMount,
  onCity,
  onWhen,
}: PillSegmentsProps) {
  const [openSegment, setOpenSegment] = useState<'where' | 'when' | null>(null);

  // Honour a click that landed before this chunk arrived.
  useEffect(() => {
    if (openOnMount) setOpenSegment(openOnMount);
  }, [openOnMount]);

  return (
    <>
      <Popover.Root open={openSegment === 'where'} onOpenChange={(open) => setOpenSegment(current => open ? 'where' : current === 'where' ? null : current)}>
        <Popover.Trigger
          className={`${segmentClass} shrink-0 rounded-l-[var(--r-pill)]`}
          style={{ minHeight: 56 }}
        >
          <span className="t-caption" style={{ color: 'var(--ink-2)' }}>
            Where
          </span>
          <span className="t-meta truncate" style={{ color: 'var(--ink)' }}>
            {cityLabel}
          </span>
        </Popover.Trigger>
        <Popover.Portal>
          <Popover.Positioner sideOffset={8} align="start" collisionPadding={12} style={{ zIndex: 60 }}>
            <Popover.Popup style={popupStyle}>
              <Popover.Title className="sr-only">Choose a city</Popover.Title>
              <OptionList
                options={CITIES.map((c) => ({ id: c.id, label: c.label }))}
                selected={city}
                onPick={(id) => {
                  onCity(id as CityId);
                  setOpenSegment(null);
                }}
              />
            </Popover.Popup>
          </Popover.Positioner>
        </Popover.Portal>
      </Popover.Root>

      <span aria-hidden className="my-3 w-px shrink-0" style={{ background: 'var(--line)' }} />

      <Popover.Root open={openSegment === 'when'} onOpenChange={(open) => setOpenSegment(current => open ? 'when' : current === 'when' ? null : current)}>
        <Popover.Trigger className={`${segmentClass} shrink-0`} style={{ minHeight: 56 }}>
          <span className="t-caption" style={{ color: 'var(--ink-2)' }}>
            When
          </span>
          <span className="t-meta truncate" style={{ color: 'var(--ink)' }}>
            {whenLabel(datePreset, from, to)}
          </span>
        </Popover.Trigger>
        <Popover.Portal>
          <Popover.Positioner sideOffset={8} align="start" collisionPadding={12} style={{ zIndex: 60 }}>
            <Popover.Popup style={popupStyle}>
              <Popover.Title className="sr-only">Choose when</Popover.Title>
              <OptionList
                options={WHEN_OPTIONS}
                selected={datePreset}
                onPick={(id) => {
                  onWhen(id as DatePreset);
                  if (id !== 'custom') setOpenSegment(null);
                }}
              />
              {datePreset === 'custom' && (
                <div
                  className="flex flex-col gap-2 border-t p-2"
                  style={{ borderColor: 'var(--line)' }}
                >
                  <label className="t-caption" style={{ color: 'var(--ink-2)' }}>
                    From
                    <input
                      type="date"
                      value={from ?? ''}
                      onChange={(e) => onWhen('custom', e.target.value || null, to)}
                      className="t-meta mt-1 block w-full rounded-[var(--r-cell)] border px-2 py-2"
                      style={{
                        borderColor: 'var(--line)',
                        background: 'var(--bg)',
                        color: 'var(--ink)',
                        minHeight: 44,
                      }}
                    />
                  </label>
                  <label className="t-caption" style={{ color: 'var(--ink-2)' }}>
                    To
                    <input
                      type="date"
                      value={to ?? ''}
                      onChange={(e) => onWhen('custom', from, e.target.value || null)}
                      className="t-meta mt-1 block w-full rounded-[var(--r-cell)] border px-2 py-2"
                      style={{
                        borderColor: 'var(--line)',
                        background: 'var(--bg)',
                        color: 'var(--ink)',
                        minHeight: 44,
                      }}
                    />
                  </label>
                </div>
              )}
            </Popover.Popup>
          </Popover.Positioner>
        </Popover.Portal>
      </Popover.Root>
    </>
  );
}
