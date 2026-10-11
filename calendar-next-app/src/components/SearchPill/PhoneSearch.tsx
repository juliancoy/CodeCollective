import { Dialog } from '@base-ui/react/dialog';
import { Search, X } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { CITIES } from '../../data/cities';
import type { CityId, DatePreset } from '../../data/types';
import { WHEN_OPTIONS, whenLabel } from './pillShared';

/**
 * The phone search is a full-screen sheet rather than a squeezed three-part
 * pill: at 390px the desktop pill leaves about 90px for the text field, which
 * is not a search box anyone can use.
 */
export type PhoneSearchProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  city: CityId;
  cityLabel: string;
  datePreset: DatePreset;
  from: string | null;
  to: string | null;
  query: string;
  resultCount: number;
  onCity: (city: CityId) => void;
  onWhen: (preset: DatePreset, from?: string | null, to?: string | null) => void;
  onQuery: (q: string) => void;
  onClearAll: () => void;
};

const cardStyle: React.CSSProperties = {
  background: 'var(--bg)',
  borderRadius: 'var(--r-sheet)',
  border: '1px solid var(--line)',
  padding: 16,
};

export default function PhoneSearch({
  open,
  onOpenChange,
  city,
  cityLabel,
  datePreset,
  from,
  to,
  query,
  resultCount,
  onCity,
  onWhen,
  onQuery,
  onClearAll,
}: PhoneSearchProps) {
  const [text, setText] = useState(query);
  const inputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    setText(query);
  }, [query]);

  useEffect(() => {
    if (text === query) return;
    const id = setTimeout(() => onQuery(text), 120);
    return () => clearTimeout(id);
  }, [text, query, onQuery]);

  // The field is why the sheet opened, so it takes focus.
  useEffect(() => {
    if (open) {
      const id = setTimeout(() => inputRef.current?.focus(), 60);
      return () => clearTimeout(id);
    }
    return undefined;
  }, [open]);

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Popup
          className="flex flex-col"
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: 75,
            background: 'var(--bg)',
          }}
        >
          <div className="flex items-center justify-between gap-3 px-4 pt-4 pb-2">
            <Dialog.Title className="t-sheet-title" style={{ color: 'var(--ink)' }}>
              Search
            </Dialog.Title>
            <Dialog.Close
              aria-label="Close search"
              className="flex items-center justify-center rounded-full"
              style={{ color: 'var(--ink-2)', minWidth: 44, minHeight: 44 }}
            >
              <X size={22} strokeWidth={1.5} aria-hidden />
            </Dialog.Close>
          </div>

          <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto px-4 pb-4">
            <div style={cardStyle}>
              <span className="t-caption block" style={{ color: 'var(--ink-2)' }}>
                What
              </span>
              <div className="mt-1 flex items-center gap-2">
                <Search size={18} strokeWidth={1.5} aria-hidden style={{ color: 'var(--ink-2)' }} />
                <input
                  ref={inputRef}
                  type="search"
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  placeholder="Search events, organizers, venues"
                  aria-label="Search events, organizers, venues"
                  className="t-body min-w-0 flex-1 bg-transparent outline-none"
                  style={{ color: 'var(--ink)' }}
                />
                {text !== '' && (
                  <button
                    type="button"
                    onClick={() => {
                      setText('');
                      onQuery('');
                      inputRef.current?.focus();
                    }}
                    aria-label="Clear search"
                    style={{ color: 'var(--ink-2)', minWidth: 44, minHeight: 44 }}
                  >
                    <X size={18} strokeWidth={1.5} aria-hidden />
                  </button>
                )}
              </div>
            </div>

            <div style={cardStyle}>
              <span className="t-caption block" style={{ color: 'var(--ink-2)' }}>
                Where
              </span>
              <div className="mt-2 flex flex-wrap gap-2">
                {CITIES.map((c) => (
                  <button
                    key={c.id}
                    type="button"
                    aria-pressed={c.id === city}
                    onClick={() => onCity(c.id)}
                    className="t-meta rounded-[var(--r-pill)] border px-3"
                    style={{
                      minHeight: 44,
                      borderColor: c.id === city ? 'var(--brand-on-bg)' : 'var(--line)',
                      background: c.id === city ? 'var(--brand-soft)' : 'transparent',
                      color: 'var(--ink)',
                    }}
                  >
                    {c.label}
                  </button>
                ))}
              </div>
            </div>

            <div style={cardStyle}>
              <span className="t-caption block" style={{ color: 'var(--ink-2)' }}>
                When
              </span>
              <div className="mt-2 flex flex-wrap gap-2">
                {WHEN_OPTIONS.map((o) => (
                  <button
                    key={o.id}
                    type="button"
                    aria-pressed={o.id === datePreset}
                    onClick={() => onWhen(o.id)}
                    className="t-meta rounded-[var(--r-pill)] border px-3"
                    style={{
                      minHeight: 44,
                      borderColor: o.id === datePreset ? 'var(--brand-on-bg)' : 'var(--line)',
                      background: o.id === datePreset ? 'var(--brand-soft)' : 'transparent',
                      color: 'var(--ink)',
                    }}
                  >
                    {o.label}
                  </button>
                ))}
              </div>
              {datePreset === 'custom' && (
                <div className="mt-3 flex flex-wrap gap-3">
                  <label className="t-caption" style={{ color: 'var(--ink-2)' }}>
                    From
                    <input
                      type="date"
                      value={from ?? ''}
                      onChange={(e) => onWhen('custom', e.target.value || null, to)}
                      className="t-meta mt-1 block rounded-[var(--r-cell)] border px-3 py-2"
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
                      className="t-meta mt-1 block rounded-[var(--r-cell)] border px-3 py-2"
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
              <p className="t-caption mt-2" style={{ color: 'var(--ink-2)' }}>
                {whenLabel(datePreset, from, to)} in {cityLabel}.
              </p>
            </div>
          </div>

          <div
            className="flex items-center justify-between gap-3 border-t px-4 py-3"
            style={{
              borderColor: 'var(--line)',
              background: 'var(--bg)',
              paddingBottom: 'calc(env(safe-area-inset-bottom, 0px) + 12px)',
            }}
          >
            <button
              type="button"
              onClick={onClearAll}
              className="t-meta underline"
              style={{ color: 'var(--ink-2)', textUnderlineOffset: '2px', minHeight: 44 }}
            >
              Clear all
            </button>
            <button
              type="button"
              onClick={() => onOpenChange(false)}
              className="t-meta tnum rounded-[var(--r-pill)] px-5"
              style={{ background: 'var(--brand)', color: 'var(--brand-ink)', minHeight: 44 }}
            >
              Show {resultCount.toLocaleString('en-US')} events
            </button>
          </div>
        </Dialog.Popup>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
