import { MapPinOff } from 'lucide-react';
import { Suspense, lazy, useState } from 'react';
import type { CalEvent } from '../../data/types';
import { WherePanel } from './WherePanel';

const MapPanel = lazy(() => import('../MapPanel/MapPanel'));

export type ContextRailProps = {
  mappable: CalEvent[];
  unmappedCount: number;
  localityCounts: Array<{ name: string; count: number }>;
  onlineCount: number;
  center: { lat: number; lng: number };
  tz: string;
  selectedKey: string | null;
  hoveredKey: string | null;
  dark: boolean;
  mapOn: boolean;
  onSelect: (key: string) => void;
  onPickLocality: (locality: string) => void;
  onPickOnline: () => void;
};

/**
 * Layer 3's companion column. Two modules, and it is never empty.
 *
 * v1 handed half the screen to the map and left a blank rectangle whenever the
 * tiles could not load, which is every time the page runs somewhere that
 * blocks the tile host. Here the map is a card that collapses to a single note
 * row on failure, and "Where it's happening" carries the location story
 * underneath it either way.
 */
export function ContextRail({
  mappable,
  unmappedCount,
  localityCounts,
  onlineCount,
  center,
  tz,
  selectedKey,
  hoveredKey,
  dark,
  mapOn,
  onSelect,
  onPickLocality,
  onPickOnline,
}: ContextRailProps) {
  const [mapFailed, setMapFailed] = useState(false);

  return (
    <aside
      aria-label="Event context"
      className="sticky hidden shrink-0 self-start xl:block"
      style={{
        top: 'calc(var(--band-h) + var(--control-h) + 16px)',
        width: 'clamp(320px, 34%, 420px)',
        paddingTop: 16,
      }}
    >
      <div className="flex flex-col gap-4">
        {mapOn &&
          (mapFailed ? (
            /* 72px, not an empty half-screen. */
            <p
              className="t-meta flex items-center gap-2 rounded-[var(--r-sheet)] px-4"
              style={{ background: 'var(--bg-soft)', color: 'var(--ink-2)', minHeight: 72 }}
            >
              <MapPinOff size={18} strokeWidth={1.5} aria-hidden className="shrink-0" />
              Map unavailable here. Every event is in the list.
            </p>
          ) : (
            <div
              className="overflow-hidden rounded-[var(--r-sheet)]"
              style={{ aspectRatio: '16 / 11', background: 'var(--bg-soft)' }}
            >
              <Suspense fallback={<div className="h-full w-full" />}>
                <MapPanel
                  events={mappable}
                  unmappedCount={unmappedCount}
                  center={center}
                  tz={tz}
                  selectedKey={selectedKey}
                  hoveredKey={hoveredKey}
                  dark={dark}
                  onSelect={onSelect}
                  onUnavailable={() => setMapFailed(true)}
                />
              </Suspense>
            </div>
          ))}

        <WherePanel
          localities={localityCounts}
          onlineCount={onlineCount}
          onPickLocality={onPickLocality}
          onPickOnline={onPickOnline}
        />
      </div>
    </aside>
  );
}
