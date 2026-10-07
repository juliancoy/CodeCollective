import { Dialog } from '@base-ui/react/dialog';
import { Drawer } from '@base-ui/react/drawer';
import { Slider } from '@base-ui/react/slider';
import { Switch } from '@base-ui/react/switch';
import { LocateFixed, X } from 'lucide-react';
import { useEffect, useId, useMemo, useState, type ReactNode } from 'react';
import { EMPTY_FILTERS, type Coords, type FilterState } from '../../data/filters';
import { LENSES, LENS_LABEL } from '../../data/lenses';
import { RAIL_ORDER, SECTOR_LABEL } from '../../data/sectors';
import { TIME_OF_DAY_LABEL, TIME_OF_DAY_ORDER } from '../../data/time';
import type { DatePreset, LensId, SectorId, TimeOfDay } from '../../data/types';
import { SectorIcon } from '../SectorIcon';

const WHEN_OPTIONS: Array<{ id: DatePreset; label: string }> = [
  { id: 'any', label: 'Any date' },
  { id: 'today', label: 'Today' },
  { id: 'tomorrow', label: 'Tomorrow' },
  { id: 'weekend', label: 'This weekend' },
  { id: 'next7', label: 'Next 7 days' },
  { id: 'custom', label: 'Custom' },
];

const TIME_HINT: Record<TimeOfDay, string> = {
  morning: '6 AM to noon',
  afternoon: 'Noon to 5 PM',
  evening: '5 to 9 PM',
  late: 'After 9 PM',
};

function Chip({
  active,
  onClick,
  children,
  count,
}: {
  active: boolean;
  onClick: () => void;
  children: ReactNode;
  count?: number;
}) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className="t-meta flex items-center gap-2 rounded-[var(--r-pill)] border px-3 py-2"
      style={{
        minHeight: 44,
        borderColor: active ? 'var(--brand)' : 'var(--line)',
        background: active ? 'var(--brand-soft)' : 'var(--bg)',
        color: 'var(--ink)',
      }}
    >
      {children}
      {count !== undefined && (
        <span className="t-caption tnum" style={{ color: 'var(--ink-2)' }}>
          {count}
        </span>
      )}
    </button>
  );
}

function Section({ title, children, aside }: { title: string; children: ReactNode; aside?: ReactNode }) {
  return (
    <section className="border-t px-5 py-5" style={{ borderColor: 'var(--line)' }}>
      <div className="mb-3 flex items-baseline justify-between gap-3">
        <h3 className="t-body font-semibold" style={{ color: 'var(--ink)' }}>
          {title}
        </h3>
        {aside}
      </div>
      {children}
    </section>
  );
}

export type FiltersSheetProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  current: FilterState;
  /** Counts for each sector under everything except the sector filter. */
  sectorCounts: Map<SectorId, number>;
  /** How many events a candidate filter state would show. */
  countFor: (draft: FilterState) => number;
  /** Top localities, shown here when the context rail is not on screen. */
  localityCounts: Array<{ name: string; count: number }>;
  showWherePanel: boolean;
  onApply: (next: FilterState) => void;
  isPhone: boolean;
};

/**
 * Filters apply when the visitor presses Show, not on every chip tap, so a
 * dense list does not thrash underneath them. The count on the button is live,
 * so they can see what each choice buys before committing.
 */
export function FiltersSheet({
  open,
  onOpenChange,
  current,
  sectorCounts,
  countFor,
  localityCounts,
  showWherePanel,
  onApply,
  isPhone,
}: FiltersSheetProps) {
  const [draft, setDraft] = useState<FilterState>(current);
  const [locating, setLocating] = useState(false);
  const [locationError, setLocationError] = useState<string | null>(null);
  const zipId = useId();

  // Reopening always starts from what is actually applied.
  useEffect(() => {
    if (open) {
      setDraft(current);
      setLocationError(null);
    }
  }, [open, current]);

  const count = useMemo(() => countFor(draft), [countFor, draft]);
  const patch = (next: Partial<FilterState>) => setDraft((d) => ({ ...d, ...next }));

  const toggleSector = (id: SectorId) => {
    const has = draft.sectors.includes(id);
    patch({ sectors: has ? draft.sectors.filter((s) => s !== id) : [...draft.sectors, id] });
  };

  const toggleLensCategory = (id: string) => {
    const has = draft.lensCategories.includes(id);
    patch({
      lensCategories: has
        ? draft.lensCategories.filter((s) => s !== id)
        : [...draft.lensCategories, id],
    });
  };

  const toggleTime = (id: TimeOfDay) => {
    const has = draft.timesOfDay.includes(id);
    patch({
      timesOfDay: has ? draft.timesOfDay.filter((t) => t !== id) : [...draft.timesOfDay, id],
      // A chip selection supersedes any raw window from a legacy link.
      timeStart: null,
      timeEnd: null,
    });
  };

  /** Geolocation is only ever requested from this button. */
  const useMyLocation = () => {
    if (!navigator.geolocation) {
      setLocationError('This browser cannot share a location.');
      return;
    }
    setLocating(true);
    setLocationError(null);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setLocating(false);
        patch({
          nearCoords: { lat: pos.coords.latitude, lng: pos.coords.longitude },
          near: 'My location',
          radiusMiles: draft.radiusMiles || 10,
        });
      },
      () => {
        setLocating(false);
        setLocationError('Could not get your location. Enter a ZIP code instead.');
      },
      { timeout: 10_000 },
    );
  };

  const lookupZip = async (zip: string) => {
    const clean = zip.trim();
    if (!/^\d{5}$/.test(clean)) return;
    try {
      const res = await fetch(`https://api.zippopotam.us/us/${clean}`);
      if (!res.ok) throw new Error('not found');
      const body = (await res.json()) as { places?: Array<{ latitude: string; longitude: string }> };
      const place = body.places?.[0];
      if (!place) throw new Error('not found');
      const coords: Coords = {
        lat: Number.parseFloat(place.latitude),
        lng: Number.parseFloat(place.longitude),
      };
      if (!Number.isFinite(coords.lat) || !Number.isFinite(coords.lng)) throw new Error('bad');
      setLocationError(null);
      patch({ nearCoords: coords, near: clean, radiusMiles: draft.radiusMiles || 10 });
    } catch {
      setLocationError('No match for that ZIP code.');
    }
  };

  const lens = LENSES[draft.lens];

  const body = (
    <>
      <div className="flex items-center justify-between px-5 pt-4 pb-3">
        <Dialog.Title className="t-sheet-title" style={{ color: 'var(--ink)' }}>
          Filters
        </Dialog.Title>
        <Dialog.Close
          aria-label="Close"
          className="flex items-center justify-center rounded-full"
          style={{ color: 'var(--ink-2)', minWidth: 44, minHeight: 44 }}
        >
          <X size={20} strokeWidth={1.5} aria-hidden />
        </Dialog.Close>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto">
        <Section
          title={draft.lens === 'community_sectors' ? 'Sectors' : lens.label}
          aside={
            <span className="flex gap-3">
              <button
                type="button"
                className="t-meta underline"
                style={{ color: 'var(--brand-on-bg)', textUnderlineOffset: '2px' }}
                onClick={() =>
                  draft.lens === 'community_sectors'
                    ? patch({ sectors: [...RAIL_ORDER] })
                    : patch({ lensCategories: lens.categories.map((c) => c.id) })
                }
              >
                Select all
              </button>
              <button
                type="button"
                className="t-meta underline"
                style={{ color: 'var(--ink-2)', textUnderlineOffset: '2px' }}
                onClick={() => patch({ sectors: [], lensCategories: [] })}
              >
                Clear
              </button>
            </span>
          }
        >
          <div className="flex flex-wrap gap-2">
            {draft.lens === 'community_sectors'
              ? RAIL_ORDER.map((id) => (
                  <Chip
                    key={id}
                    active={draft.sectors.includes(id)}
                    onClick={() => toggleSector(id)}
                    count={sectorCounts.get(id) ?? 0}
                  >
                    <SectorIcon sector={id} size={16} />
                    {SECTOR_LABEL[id]}
                  </Chip>
                ))
              : lens.categories.map((c) => (
                  <Chip
                    key={c.id}
                    active={draft.lensCategories.includes(c.id)}
                    onClick={() => toggleLensCategory(c.id)}
                  >
                    <span
                      aria-hidden
                      className="h-3 w-3 rounded-full"
                      style={{ background: c.color }}
                    />
                    {c.label}
                  </Chip>
                ))}
          </div>
        </Section>

        <Section title="When">
          <div className="flex flex-wrap gap-2">
            {WHEN_OPTIONS.map((o) => (
              <Chip
                key={o.id}
                active={draft.datePreset === o.id}
                onClick={() =>
                  patch({
                    datePreset: o.id,
                    ...(o.id === 'custom' ? {} : { from: null, to: null }),
                  })
                }
              >
                {o.label}
              </Chip>
            ))}
          </div>
          {draft.datePreset === 'custom' && (
            <div className="mt-3 flex flex-wrap gap-3">
              <label className="t-caption" style={{ color: 'var(--ink-2)' }}>
                From
                <input
                  type="date"
                  value={draft.from ?? ''}
                  onChange={(e) => patch({ from: e.target.value || null })}
                  className="t-meta mt-1 block rounded-[var(--r-cell)] border px-3 py-2"
                  style={{ borderColor: 'var(--line)', background: 'var(--bg)', color: 'var(--ink)', minHeight: 44 }}
                />
              </label>
              <label className="t-caption" style={{ color: 'var(--ink-2)' }}>
                To
                <input
                  type="date"
                  value={draft.to ?? ''}
                  onChange={(e) => patch({ to: e.target.value || null })}
                  className="t-meta mt-1 block rounded-[var(--r-cell)] border px-3 py-2"
                  style={{ borderColor: 'var(--line)', background: 'var(--bg)', color: 'var(--ink)', minHeight: 44 }}
                />
              </label>
            </div>
          )}
        </Section>

        <Section title="Time of day">
          <div className="flex flex-wrap gap-2">
            {TIME_OF_DAY_ORDER.map((id) => (
              <Chip key={id} active={draft.timesOfDay.includes(id)} onClick={() => toggleTime(id)}>
                {TIME_OF_DAY_LABEL[id]}
                <span className="t-caption" style={{ color: 'var(--ink-2)' }}>
                  {TIME_HINT[id]}
                </span>
              </Chip>
            ))}
          </div>

          <label className="mt-4 flex items-start gap-3">
            <Switch.Root
              checked={draft.outsideWorkHours}
              onCheckedChange={(v: boolean) => patch({ outsideWorkHours: v })}
              className="mt-[2px] shrink-0 rounded-[var(--r-pill)]"
              style={{
                width: 44,
                height: 26,
                padding: 3,
                background: draft.outsideWorkHours ? 'var(--brand)' : 'var(--bg-soft)',
                border: '1px solid var(--line)',
              }}
            >
              <Switch.Thumb
                className="block rounded-full"
                style={{
                  width: 18,
                  height: 18,
                  background: draft.outsideWorkHours ? 'var(--brand-ink)' : 'var(--ink-2)',
                  transform: draft.outsideWorkHours ? 'translateX(18px)' : 'translateX(0)',
                  transition: 'transform 0.16s ease',
                }}
              />
            </Switch.Root>
            <span>
              <span className="t-body block" style={{ color: 'var(--ink)' }}>
                Outside work hours
              </span>
              <span className="t-meta block" style={{ color: 'var(--ink-2)' }}>
                Hide weekday events between 9 AM and 5 PM.
              </span>
            </span>
          </label>
        </Section>

        {/* Below 1280 the context rail is gone, so the "where" answer moves
            here rather than disappearing. */}
        {showWherePanel && localityCounts.length > 0 && (
          <Section title="Where it's happening">
            <div className="flex flex-wrap gap-2">
              {localityCounts.map((l) => (
                <Chip
                  key={l.name}
                  active={draft.near === l.name}
                  onClick={() => patch({ near: l.name, radiusMiles: 5 })}
                  count={l.count}
                >
                  {l.name}
                </Chip>
              ))}
            </div>
          </Section>
        )}

        <Section title="Distance">
          <div className="flex flex-wrap items-end gap-3">
            <label className="t-caption min-w-0 flex-1" htmlFor={zipId} style={{ color: 'var(--ink-2)' }}>
              ZIP code or neighborhood
              <input
                id={zipId}
                type="text"
                inputMode="numeric"
                defaultValue={draft.near ?? ''}
                onBlur={(e) => void lookupZip(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault();
                    void lookupZip((e.target as HTMLInputElement).value);
                  }
                }}
                className="t-meta mt-1 block w-full rounded-[var(--r-cell)] border px-3 py-2"
                style={{ borderColor: 'var(--line)', background: 'var(--bg)', color: 'var(--ink)', minHeight: 44 }}
              />
            </label>
            <button
              type="button"
              onClick={useMyLocation}
              className="t-meta flex items-center gap-2 rounded-[var(--r-pill)] border px-3 py-2"
              style={{ borderColor: 'var(--line)', color: 'var(--ink)', minHeight: 44 }}
            >
              <LocateFixed size={16} strokeWidth={1.5} aria-hidden />
              {locating ? 'Locating…' : 'Use my location'}
            </button>
          </div>

          {locationError && (
            <p className="t-meta mt-2" style={{ color: 'var(--danger)' }}>
              {locationError}
            </p>
          )}

          <div className="mt-4">
            <Slider.Root
              value={draft.radiusMiles}
              min={1}
              max={50}
              step={1}
              disabled={draft.nearCoords === null}
              onValueChange={(v: number | readonly number[]) =>
                patch({ radiusMiles: Array.isArray(v) ? (v[0] as number) : (v as number) })
              }
            >
              <Slider.Label className="t-caption block" style={{ color: 'var(--ink-2)' }}>
                Within
              </Slider.Label>
              <div className="flex items-center gap-3">
                <Slider.Control className="flex flex-1 items-center py-3">
                  <Slider.Track
                    className="relative w-full rounded-full"
                    style={{ height: 4, background: 'var(--bg-soft)' }}
                  >
                    <Slider.Indicator className="rounded-full" style={{ background: 'var(--brand-on-bg)' }} />
                    <Slider.Thumb
                      className="rounded-full"
                      style={{
                        width: 20,
                        height: 20,
                        background: 'var(--bg)',
                        border: '2px solid var(--brand)',
                      }}
                    />
                  </Slider.Track>
                </Slider.Control>
                {/* Every drag has a non-drag alternative. */}
                <label className="t-caption" style={{ color: 'var(--ink-2)' }}>
                  <span className="sr-only">Distance in miles</span>
                  <input
                    type="number"
                    min={1}
                    max={50}
                    value={draft.radiusMiles}
                    disabled={draft.nearCoords === null}
                    onChange={(e) =>
                      patch({
                        radiusMiles: Math.min(50, Math.max(1, Number(e.target.value) || 1)),
                      })
                    }
                    className="t-meta tnum w-16 rounded-[var(--r-cell)] border px-2 py-2"
                    style={{ borderColor: 'var(--line)', background: 'var(--bg)', color: 'var(--ink)', minHeight: 44 }}
                  />
                </label>
                <span className="t-meta" style={{ color: 'var(--ink-2)' }}>
                  miles
                </span>
              </div>
            </Slider.Root>

            {draft.nearCoords !== null && (
              <p className="t-meta mt-1" style={{ color: 'var(--ink-2)' }}>
                Events without an address we can place are hidden while distance is on.
              </p>
            )}
          </div>
        </Section>

        <Section title="Lens">
          <fieldset className="m-0 border-0 p-0">
            <legend className="sr-only">Choose a lens</legend>
            {(Object.keys(LENS_LABEL) as LensId[]).map((id) => (
              <label key={id} className="flex items-center gap-3 py-2" style={{ minHeight: 44 }}>
                <input
                  type="radio"
                  name="lens"
                  checked={draft.lens === id}
                  onChange={() => patch({ lens: id, sectors: [], lensCategories: [] })}
                  style={{ accentColor: 'var(--brand)', width: 18, height: 18 }}
                />
                <span className="t-body" style={{ color: 'var(--ink)' }}>
                  {LENS_LABEL[id]}
                </span>
              </label>
            ))}
          </fieldset>
        </Section>
      </div>

      <div
        className="flex items-center justify-between gap-3 border-t px-5 py-4"
        style={{ borderColor: 'var(--line)', background: 'var(--bg)' }}
      >
        <button
          type="button"
          onClick={() => setDraft({ ...EMPTY_FILTERS, query: draft.query })}
          className="t-meta underline"
          style={{ color: 'var(--ink-2)', textUnderlineOffset: '2px', minHeight: 44 }}
        >
          Clear all
        </button>
        <button
          type="button"
          disabled={count === 0}
          onClick={() => {
            onApply(draft);
            onOpenChange(false);
          }}
          className="t-meta tnum rounded-[var(--r-pill)] px-5 py-2.5"
          style={{
            background: count === 0 ? 'var(--bg-soft)' : 'var(--brand)',
            color: count === 0 ? 'var(--ink-2)' : 'var(--brand-ink)',
            minHeight: 44,
            cursor: count === 0 ? 'not-allowed' : 'pointer',
          }}
        >
          {count === 0 ? 'No events' : `Show ${count.toLocaleString('en-US')} events`}
        </button>
      </div>
    </>
  );

  if (isPhone) {
    return (
      <Drawer.Root open={open} onOpenChange={onOpenChange} swipeDirection="down">
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
              <span aria-hidden className="block h-1 w-10 rounded-full" style={{ background: 'var(--line)' }} />
            </Drawer.SwipeArea>
            {body}
          </Drawer.Popup>
        </Drawer.Portal>
      </Drawer.Root>
    );
  }

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Backdrop style={{ background: 'var(--scrim)', position: 'fixed', inset: 0, zIndex: 70 }} />
        <Dialog.Popup
          className="flex flex-col"
          style={{
            position: 'fixed',
            top: '50%',
            left: '50%',
            transform: 'translate(-50%, -50%)',
            zIndex: 71,
            width: 'min(560px, calc(100vw - 32px))',
            maxHeight: 'min(760px, calc(100dvh - 64px))',
            background: 'var(--bg)',
            borderRadius: 'var(--r-sheet)',
            boxShadow: 'var(--shadow-sheet)',
            overflow: 'hidden',
          }}
        >
          {body}
        </Dialog.Popup>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
