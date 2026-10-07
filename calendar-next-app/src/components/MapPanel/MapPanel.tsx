import type { FeatureCollection, Point } from 'geojson';
import type { GeoJSONSource, Map as MapLibreMap, MapGeoJSONFeature } from 'maplibre-gl';
// MapLibre resolves its worker at runtime with
// `new URL('./maplibre-gl-worker.mjs', import.meta.url)`, which no bundler can
// see, so the file is never emitted and every production build silently loses
// the worker: the canvas mounts and no tile ever draws. Vite bundles it here
// (it imports maplibre-gl-shared.mjs) and the URL is handed to setWorkerUrl.
import maplibreWorkerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url';
import { useEffect, useRef, useState } from 'react';
import { haversineMiles } from '../../data/filters';
import { formatTime } from '../../data/time';
import type { CalEvent } from '../../data/types';

/**
 * MapLibre 6 is ESM-only and weighs more than the rest of the app together,
 * so it is imported here and this whole component is a lazy chunk. Nothing on
 * the agenda path can pull it in.
 *
 * The public OpenFreeMap instance is provided as is. For production, self-host
 * Protomaps PMTiles instead.
 */
const STYLE_LIGHT = 'https://tiles.openfreemap.org/styles/positron';
const STYLE_DARK = 'https://tiles.openfreemap.org/styles/dark';

/** Anything further out than this is an outlier, not part of the metro. */
const OUTLIER_MILES = 150;

export type MapPanelProps = {
  events: CalEvent[];
  unmappedCount: number;
  center: { lat: number; lng: number };
  tz: string;
  selectedKey: string | null;
  hoveredKey: string | null;
  dark: boolean;
  onSelect: (key: string) => void;
  /** Called once when the basemap cannot be shown, so the rail can collapse. */
  onUnavailable?: () => void;
};

type FeatureProps = { key: string; sector: string; title: string; start: number };

function toGeoJson(events: CalEvent[]): FeatureCollection<Point, FeatureProps> {
  return {
    type: 'FeatureCollection',
    features: events
      .filter((e) => e.coords !== null)
      .map((e) => ({
        type: 'Feature' as const,
        id: e.key,
        geometry: { type: 'Point' as const, coordinates: [e.coords!.lng, e.coords!.lat] },
        properties: {
          key: e.key,
          sector: e.primarySector,
          title: e.title,
          start: e.start.getTime(),
        },
      })),
  };
}

/** Read a token off the document so the map matches the active theme. */
function token(name: string, fallback: string): string {
  if (typeof window === 'undefined') return fallback;
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return v === '' ? fallback : v;
}

/**
 * Repaint the vendor basemap into the Harbor palette by walking the style's
 * layers and matching on id.
 */
function retint(map: MapLibreMap, dark: boolean) {
  const water = dark ? '#13303D' : '#D3E6EF';
  const land = token('--bg', dark ? '#0E1A24' : '#F5F7F9');
  const line = token('--line', dark ? '#253847' : '#DDE3E9');
  const ink2 = token('--ink-2', dark ? '#93A4B3' : '#586878');

  for (const layer of map.getStyle().layers ?? []) {
    const id = layer.id.toLowerCase();
    try {
      if (layer.type === 'background') {
        map.setPaintProperty(layer.id, 'background-color', land);
      } else if (layer.type === 'fill') {
        if (id.includes('water')) map.setPaintProperty(layer.id, 'fill-color', water);
        else if (id.includes('landcover') || id.includes('park') || id.includes('landuse')) {
          map.setPaintProperty(layer.id, 'fill-color', land);
          map.setPaintProperty(layer.id, 'fill-opacity', 0.6);
        } else if (id.includes('building')) {
          map.setPaintProperty(layer.id, 'fill-color', line);
        }
      } else if (layer.type === 'line') {
        if (id.includes('water')) map.setPaintProperty(layer.id, 'line-color', water);
        else if (id.includes('road') || id.includes('transit') || id.includes('bridge')) {
          map.setPaintProperty(layer.id, 'line-color', line);
        }
      } else if (layer.type === 'symbol' && id.includes('label')) {
        map.setPaintProperty(layer.id, 'text-color', ink2);
        map.setPaintProperty(layer.id, 'text-halo-color', land);
      }
    } catch {
      // Vendor styles change; a layer that will not take a property is skipped
      // rather than taking the map down.
    }
  }
}

export default function MapPanel({
  events,
  unmappedCount,
  center,
  tz,
  selectedKey,
  hoveredKey,
  dark,
  onSelect,
  onUnavailable,
}: MapPanelProps) {
  const hostRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const [ready, setReady] = useState(false);
  const [failed, setFailed] = useState(false);
  const activeIdRef = useRef<string | null>(null);
  const onSelectRef = useRef(onSelect);
  onSelectRef.current = onSelect;

  // Create the map once.
  useEffect(() => {
    let cancelled = false;
    const host = hostRef.current;
    if (!host) return;

    void (async () => {
      try {
        const maplibre = await import('maplibre-gl');
        await import('maplibre-gl/dist/maplibre-gl.css');
        if (cancelled) return;

        // Must be set before the first Map is constructed.
        maplibre.setWorkerUrl(maplibreWorkerUrl);

        const map = new maplibre.Map({
          container: host,
          style: dark ? STYLE_DARK : STYLE_LIGHT,
          center: [center.lng, center.lat],
          zoom: 9.5,
          attributionControl: { compact: false },
        });
        mapRef.current = map;

        let styled = false;

        map.on('error', (e: unknown) => {
          // Once the style is up, a missing tile is cosmetic and must never
          // blank the agenda. Before that, an error means the style document
          // itself did not arrive, which is fatal and worth saying at once —
          // a sandboxed frame is refused by the tile host on the first
          // request, and waiting out the watchdog would leave a card-sized
          // hole on screen for twelve seconds.
          console.warn('Map error', e);
          if (!cancelled && !styled) setFailed(true);
        });

        // Backstop for the quieter failure, where the request neither resolves
        // nor rejects and no error is ever raised.
        const styleWatchdog = setTimeout(() => {
          if (!cancelled && !map.isStyleLoaded()) setFailed(true);
        }, 12_000);
        map.on('styledata', () => {
          styled = true;
          clearTimeout(styleWatchdog);
        });

        map.on('load', () => {
          if (cancelled) return;
          retint(map, dark);

          map.addSource('events', {
            type: 'geojson',
            data: toGeoJson(events),
            cluster: true,
            clusterRadius: 40,
            clusterMaxZoom: 14,
          });

          map.addLayer({
            id: 'clusters',
            type: 'circle',
            source: 'events',
            filter: ['has', 'point_count'],
            paint: {
              'circle-color': token('--accent-soft', '#E3F3FB'),
              'circle-stroke-color': token('--accent', '#2C6A8A'),
              'circle-stroke-width': 1,
              'circle-radius': ['step', ['get', 'point_count'], 16, 10, 22, 50, 28],
            },
          });

          map.addLayer({
            id: 'cluster-count',
            type: 'symbol',
            source: 'events',
            filter: ['has', 'point_count'],
            layout: {
              'text-field': ['get', 'point_count_abbreviated'],
              'text-size': 12,
              'text-font': ['Noto Sans Regular'],
            },
            paint: { 'text-color': token('--ink', '#1B2733') },
          });

          map.addLayer({
            id: 'points',
            type: 'circle',
            source: 'events',
            filter: ['!', ['has', 'point_count']],
            paint: {
              'circle-radius': ['case', ['boolean', ['feature-state', 'active'], false], 16, 10],
              'circle-color': [
                'case',
                ['boolean', ['feature-state', 'active'], false],
                token('--accent', '#2C6A8A'),
                ['concat', '#', ['get', 'sector']],
              ],
              'circle-stroke-width': 2,
              'circle-stroke-color': token('--surface', '#FFFFFF'),
            },
          });

          // Sector colours are CSS variables, which the style cannot read, so
          // they are resolved to literals here.
          const colorExpr: (string | string[])[] = ['match', ['get', 'sector']];
          for (const s of [
            'technology', 'education', 'entrepreneurship', 'economics', 'finance',
            'health', 'politics', 'government', 'culture', 'faith', 'environment',
            'makerspace', 'other',
          ]) {
            colorExpr.push(s, token(`--sector-${s}`, '#747B83'));
          }
          colorExpr.push(token('--sector-other', '#747B83'));
          map.setPaintProperty('points', 'circle-color', [
            'case',
            ['boolean', ['feature-state', 'active'], false],
            token('--accent', '#2C6A8A'),
            colorExpr,
          ] as never);

          map.on('click', 'clusters', (e) => {
            const f = map.queryRenderedFeatures(e.point, { layers: ['clusters'] })[0];
            const clusterId = f?.properties?.['cluster_id'];
            if (f === undefined || clusterId === undefined) return;
            const center = (f.geometry as Point).coordinates as [number, number];
            const src = map.getSource('events') as GeoJSONSource;
            void src.getClusterExpansionZoom(Number(clusterId)).then((zoom) => {
              // Ease to the cluster's own extent rather than a fixed step.
              map.easeTo({ center, zoom });
            });
          });

          map.on('click', 'points', (e) => {
            const f = e.features?.[0] as MapGeoJSONFeature | undefined;
            const key = f?.properties?.['key'];
            if (typeof key === 'string') onSelectRef.current(key);
          });

          for (const layer of ['clusters', 'points']) {
            map.on('mouseenter', layer, () => {
              map.getCanvas().style.cursor = 'pointer';
            });
            map.on('mouseleave', layer, () => {
              map.getCanvas().style.cursor = '';
            });
          }

          setReady(true);
        });
      } catch (err) {
        console.warn('Map failed to load', err);
        if (!cancelled) setFailed(true);
      }
    })();

    return () => {
      cancelled = true;
      mapRef.current?.remove();
      mapRef.current = null;
    };
    // Created once; theme and data changes are handled by the effects below.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Data and camera follow the filters.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    const src = map.getSource('events') as GeoJSONSource | undefined;
    if (!src) return;
    src.setData(toGeoJson(events));

    const placed = events.filter(
      (e) => e.coords !== null && haversineMiles(center, e.coords) <= OUTLIER_MILES,
    );
    if (placed.length === 0) return;

    let minLng = 180;
    let minLat = 90;
    let maxLng = -180;
    let maxLat = -90;
    for (const e of placed) {
      minLng = Math.min(minLng, e.coords!.lng);
      maxLng = Math.max(maxLng, e.coords!.lng);
      minLat = Math.min(minLat, e.coords!.lat);
      maxLat = Math.max(maxLat, e.coords!.lat);
    }
    map.fitBounds(
      [
        [minLng, minLat],
        [maxLng, maxLat],
      ],
      { padding: 48, maxZoom: 13, duration: 400 },
    );
  }, [events, ready, center]);

  // Hover and selection highlight a single point through feature state.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    const next = selectedKey ?? hoveredKey;
    const prev = activeIdRef.current;
    if (prev === next) return;

    if (prev !== null) {
      map.setFeatureState({ source: 'events', id: prev }, { active: false });
    }
    if (next !== null) {
      map.setFeatureState({ source: 'events', id: next }, { active: true });
    }
    activeIdRef.current = next;
  }, [selectedKey, hoveredKey, ready]);

  const activeEvent = events.find((e) => e.key === (selectedKey ?? hoveredKey)) ?? null;

  // The rail owns the failure copy, so it can collapse to a 72px note instead
  // of leaving a card-sized hole.
  const reported = useRef(false);
  useEffect(() => {
    if (failed && !reported.current) {
      reported.current = true;
      onUnavailable?.();
    }
  }, [failed, onUnavailable]);

  if (failed) {
    return (
      <div
        className="flex h-full items-center justify-center p-6"
        style={{ background: 'var(--bg-soft)' }}
      >
        <p className="t-meta text-center" style={{ color: 'var(--ink-2)' }}>
          Map unavailable here. Every event is in the list.
        </p>
      </div>
    );
  }

  return (
    <div className="relative h-full w-full overflow-hidden">
      <div ref={hostRef} className="h-full w-full" />

      {activeEvent && (
        <span
          className="t-caption tnum pointer-events-none absolute top-3 left-3 rounded-[var(--r-pill)] px-3 py-1"
          style={{ background: 'var(--bg)', color: 'var(--ink)', boxShadow: 'var(--shadow-pill)' }}
        >
          {formatTime(activeEvent.start, tz)} · {activeEvent.title}
        </span>
      )}

      {unmappedCount > 0 && (
        /* Raised clear of MapLibre's attribution strip, which also sits
           bottom-left and is not ours to move. */
        <p
          className="t-caption absolute left-3 rounded-[var(--r-pill)] px-3 py-1"
          style={{
            bottom: 28,
            background: 'var(--bg)',
            color: 'var(--ink-2)',
            boxShadow: 'var(--shadow-pill)',
          }}
        >
          Not on map: {unmappedCount} events without a mapped location
        </p>
      )}
    </div>
  );
}
