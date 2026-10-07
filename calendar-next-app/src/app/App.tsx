import { List, Map as MapIcon } from 'lucide-react';
import {
  Component,
  Suspense,
  lazy,
  useCallback,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import { Agenda } from '../components/Agenda/Agenda';
import { ContextRail } from '../components/ContextRail/ContextRail';
import { ControlBar } from '../components/ControlBar/ControlBar';
import { Footer } from '../components/Footer';
import { BrandBand } from '../components/Header/BrandBand';
import { MonthGrid } from '../components/MonthGrid/MonthGrid';
import { SearchPill } from '../components/SearchPill/SearchPill';
import {
  AgendaSkeleton,
  EmptyState,
  ErrorState,
  MetaSkeleton,
  TideSkeleton,
} from '../components/States/States';
import { StatusChip, dataStatus } from '../components/States/StatusChip';
import { TideLine } from '../components/TideLine/TideLine';
import { getCity } from '../data/cities';
import { invalidateEvents } from '../data/fetchEvents';
import { buildPredicates, type FilterState } from '../data/filters';
import { isSectorId } from '../data/sectors';
import { relativeTime } from '../data/time';
import type { DatePreset, SectorId } from '../data/types';
import { useChromeHeight, useCondensed, useDarkTheme, useMediaQuery } from './layoutHooks';
import { useCalendar } from './useCalendar';

/* Heavy, interaction-only surfaces stay out of the initial payload. */
const EventSheet = lazy(() =>
  import('../components/EventSheet/EventSheet').then((m) => ({ default: m.EventSheet })),
);
const FiltersSheet = lazy(() =>
  import('../components/FiltersSheet/FiltersSheet').then((m) => ({ default: m.FiltersSheet })),
);
const SubscribePopover = lazy(() =>
  import('../components/SubscribePopover/SubscribePopover').then((m) => ({
    default: m.SubscribePopover,
  })),
);
const Interlude = lazy(() =>
  import('../components/Interlude/Interlude').then((m) => ({ default: m.Interlude })),
);
const PhoneMap = lazy(() => import('../components/MapPanel/MapPanel'));

/* ---------------- error boundary ---------------- */

type BoundaryProps = { children: ReactNode; fallback: (retry: () => void) => ReactNode };

class Boundary extends Component<BoundaryProps, { failed: boolean }> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  render() {
    if (this.state.failed) return this.props.fallback(() => this.setState({ failed: false }));
    return this.props.children;
  }
}

/* ---------------- toast ---------------- */

function Toast({ message }: { message: string | null }) {
  return (
    <div
      aria-live="polite"
      className="pointer-events-none fixed inset-x-0 bottom-6 z-[90] flex justify-center"
    >
      {message && (
        <span
          className="t-meta rounded-[var(--r-pill)] px-4 py-2"
          style={{ background: 'var(--ink)', color: 'var(--bg)', boxShadow: 'var(--shadow-sheet)' }}
        >
          {message}
        </span>
      )}
    </div>
  );
}

/* ---------------- shell ---------------- */

const STALE_AFTER_MS = 48 * 3600_000;

function Calendar() {
  const cal = useCalendar();
  const { derived, url, actions } = cal;

  const [hoveredKey, setHoveredKey] = useState<string | null>(null);
  const [flashKey, setFlashKey] = useState<string | null>(null);
  const [activeDay, setActiveDay] = useState<string | null>(null);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [subscribeOpen, setSubscribeOpen] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  const condensed = useCondensed();
  const chromeRef = useChromeHeight<HTMLDivElement>();
  const dark = useDarkTheme();
  const isPhone = useMediaQuery('(max-width: 767px)');
  const isWide = useMediaQuery('(min-width: 1280px)');

  // The rail's map is on by default on desktop, but a phone visitor should
  // land on the list and reach the map through the pill, not the other way
  // round. The URL always wins over both.
  const mapOn = url.mapParam ?? !isPhone;
  const railVisible = isWide && url.view === 'agenda';

  const showToast = useCallback((message: string) => {
    setToast(message);
    setTimeout(() => setToast((t) => (t === message ? null : t)), 2600);
  }, []);

  const onOpen = useCallback((key: string) => actions.openEvent(key), [actions]);
  const onHover = useCallback((key: string | null) => setHoveredKey(key), []);
  const onVisibleDayChange = useCallback((dayKey: string) => setActiveDay(dayKey), []);

  /** Scroll the agenda to a day, clearing a date filter that would hide it. */
  const scrollToDay = useCallback(
    (dayKey: string) => {
      const range = derived.dateRange;
      if (range && (dayKey < range.from || dayKey > range.to)) {
        actions.applyFilters({ datePreset: 'any', from: null, to: null });
      }
      if (url.view === 'month') actions.setView('agenda');
      setActiveDay(dayKey);
      requestAnimationFrame(() => {
        const el = document.querySelector<HTMLElement>(`[data-day="${dayKey}"]`);
        if (!el) return;
        const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        const chrome = Number.parseInt(
          getComputedStyle(document.documentElement).getPropertyValue('--chrome-h'),
          10,
        );
        window.scrollTo({
          top: el.getBoundingClientRect().top + window.scrollY - (chrome || 0),
          behavior: reduce ? 'auto' : 'smooth',
        });
      });
    },
    [derived.dateRange, actions, url.view],
  );

  /** A pin click selects the event and flashes its row into view. */
  const onSelectFromMap = useCallback(
    (key: string) => {
      actions.openEvent(key);
      setFlashKey(key);
      setTimeout(() => setFlashKey((k) => (k === key ? null : k)), 700);
      requestAnimationFrame(() => {
        document
          .querySelector<HTMLElement>(`[data-event-key="${CSS.escape(key)}"]`)
          ?.scrollIntoView({ block: 'center', behavior: 'smooth' });
      });
    },
    [actions],
  );

  const onSelectSector = useCallback(
    (id: string | null) => {
      if (id === null) {
        if (url.filters.lens === 'community_sectors') actions.setSectors([]);
        else actions.setLensCategories([]);
        return;
      }
      if (url.filters.lens === 'community_sectors') {
        actions.setSectors(isSectorId(id) ? [id as SectorId] : []);
      } else {
        actions.setLensCategories([id]);
      }
    },
    [actions, url.filters.lens],
  );

  const onWhen = useCallback(
    (preset: DatePreset, from?: string | null, to?: string | null) => {
      actions.applyFilters({
        datePreset: preset,
        ...(from !== undefined ? { from } : {}),
        ...(to !== undefined ? { to } : {}),
      });
    },
    [actions],
  );

  /** Live count for the filters sheet button, from a candidate draft. */
  const countFor = useCallback(
    (draft: FilterState) => {
      const p = buildPredicates(draft, {
        tz: cal.tz,
        todayKey: cal.todayKey,
        todayWeekday: cal.todayWeekday,
      });
      const searchKeys =
        draft.query.trim() === '' ? null : new Set(derived.filtered.map((e) => e.key));
      let n = 0;
      for (const e of cal.events) {
        if (searchKeys && !searchKeys.has(e.key)) continue;
        if (p.date(e) && p.time(e) && p.sector(e) && p.distance(e)) n++;
      }
      return n;
    },
    [cal.events, cal.tz, cal.todayKey, cal.todayWeekday, derived.filtered],
  );

  const selectedEvent = useMemo(
    () => (url.eventKey ? (cal.events.find((e) => e.key === url.eventKey) ?? null) : null),
    [url.eventKey, cal.events],
  );

  const moreFromOrganizer = useMemo(() => {
    if (!selectedEvent) return [];
    return cal.events
      .filter((e) => e.orgName === selectedEvent.orgName && e.key !== selectedEvent.key)
      .slice(0, 3);
  }, [selectedEvent, cal.events]);

  const status = dataStatus({
    feedSource: cal.feedSource,
    snapshotDate: cal.snapshotDate,
    newestScrapeAt: cal.newestScrapeAt,
    now: cal.now,
    staleAfterMs: STALE_AFTER_MS,
  });

  const total = derived.filtered.length;
  const railSelected =
    url.filters.lens === 'community_sectors' ? url.filters.sectors : url.filters.lensCategories;
  const soleSector = railSelected.length === 1 ? railSelected[0] : null;
  const activeSectorColor =
    soleSector !== undefined && soleSector !== null && isSectorId(soleSector)
      ? `var(--sector-${soleSector})`
      : null;

  const pill = (
    <SearchPill
      city={url.city}
      cityLabel={cal.cityLabel}
      datePreset={url.filters.datePreset}
      from={url.filters.from}
      to={url.filters.to}
      query={url.filters.query}
      onCity={actions.setCity}
      onWhen={onWhen}
      onQuery={actions.setQuery}
      isPhone={isPhone}
      compact={condensed}
      resultCount={total}
      onClearAll={actions.clearAll}
    />
  );

  const listColumn =
    total === 0 ? (
      <EmptyState
        query={url.filters.query}
        hasDateFilter={url.filters.datePreset !== 'any'}
        relaxations={derived.relaxations}
        onRelax={(r) => actions.applyFilters(r.patch)}
        onClearAll={actions.clearAll}
        onSearchAllDates={() => actions.applyFilters({ datePreset: 'any', from: null, to: null })}
      />
    ) : url.view === 'month' ? (
      <MonthGrid
        events={derived.filtered}
        tz={cal.tz}
        todayKey={cal.todayKey}
        sectorColor={activeSectorColor}
        onPickDay={scrollToDay}
      />
    ) : (
      <Agenda
        days={derived.days}
        tz={cal.tz}
        todayKey={cal.todayKey}
        selectedKey={url.eventKey ?? hoveredKey}
        flashKey={flashKey}
        onOpen={onOpen}
        onHover={onHover}
        onVisibleDayChange={onVisibleDayChange}
        resetToken={cal.resetToken}
        interlude={
          <Suspense fallback={null}>
            <Interlude
              events={derived.filtered}
              tz={cal.tz}
              todayKey={cal.todayKey}
              todayWeekday={cal.todayWeekday}
              suppressed={!derived.pristine}
              onOpen={onOpen}
              onSeeAll={() => actions.applyFilters({ datePreset: 'weekend' })}
            />
          </Suspense>
        }
      />
    );

  return (
    <>
      <BrandBand
        city={url.city}
        condensed={condensed}
        onSubscribe={() => setSubscribeOpen(true)}
        pill={pill}
        title={<>What&rsquo;s on in {cal.cityLabel}</>}
        meta={
          <>
            {cal.events.length.toLocaleString('en-US')} events from {cal.organizers} organizers.
            {cal.newestScrapeAt && <> Updated {relativeTime(cal.newestScrapeAt, cal.now)}.</>}{' '}
            {cal.tzLabel === 'your time' ? 'Times in your time.' : `${cal.tzLabel}.`}
            <StatusChip status={status} />
          </>
        }
      />

      <ControlBar
        lens={url.filters.lens}
        selected={railSelected}
        onSelect={onSelectSector}
        onOpenFilters={() => setFiltersOpen(true)}
        filterCount={cal.filtersActive}
        view={url.view}
        onView={actions.setView}
        mapOn={mapOn}
        onMap={actions.setMap}
        isPhone={isPhone}
        isWide={isWide}
        stuck={condensed}
      />

      <main
        id="main"
        className="mx-auto w-full max-w-[1440px] px-4 pb-24 sm:px-6"
        aria-label={`${cal.cityLabel} events`}
      >
        <p className="sr-only" role="status" aria-live="polite">
          {total === 1 ? '1 event' : `${total} events`}
        </p>

        {isPhone && mapOn ? (
          /* The context rail is a desktop arrangement, not a replacement for
             the phone map. Here the map takes over the list, as in v1, so the
             floating pill still has something to toggle. */
          <div
            className="pt-4"
            style={{ height: 'calc(100dvh - var(--band-h) - var(--control-h) - 32px)' }}
          >
            <aside
              aria-label="Map of events"
              className="h-full overflow-hidden rounded-[var(--r-sheet)]"
            >
              <Suspense
                fallback={<div className="h-full w-full" style={{ background: 'var(--bg-soft)' }} />}
              >
                <PhoneMap
                  events={derived.mappable}
                  unmappedCount={derived.unmappedCount}
                  center={getCity(url.city).center}
                  tz={cal.tz}
                  selectedKey={url.eventKey}
                  hoveredKey={hoveredKey}
                  dark={dark}
                  onSelect={onSelectFromMap}
                />
              </Suspense>
            </aside>
          </div>
        ) : (
          <div className="flex gap-8">
            <div className="min-w-0 flex-1">
            {/* The tide line is the list column's own header, beside the list
                it controls rather than spanning the whole page. */}
            {url.view === 'agenda' && total > 0 && (
              <div
                ref={chromeRef}
                className="sticky z-20"
                style={{
                  top: 'calc(var(--band-h) + var(--control-h))',
                  background: 'var(--bg)',
                }}
              >
                <TideLine
                  todayKey={cal.todayKey}
                  tz={cal.tz}
                  counts={derived.tideCounts}
                  activeDay={activeDay}
                  onPick={scrollToDay}
                  sectorColor={activeSectorColor}
                  ready
                />
              </div>
            )}
            {listColumn}
          </div>

          {railVisible && (
            <ContextRail
              mappable={derived.mappable}
              unmappedCount={derived.unmappedCount}
              localityCounts={derived.localityCounts}
              onlineCount={derived.onlineCount}
              center={getCity(url.city).center}
              tz={cal.tz}
              selectedKey={url.eventKey}
              hoveredKey={hoveredKey}
              dark={dark}
              mapOn={mapOn}
              onSelect={onSelectFromMap}
              onPickLocality={(locality) => actions.applyFilters({ near: locality, radiusMiles: 5 })}
              onPickOnline={() => actions.setQuery('online')}
              />
            )}
          </div>
        )}
      </main>

      {/* Phones get a floating toggle rather than a second page. */}
      <button
        type="button"
        onClick={() => actions.setMap(!mapOn)}
        className="t-meta fixed left-1/2 z-40 flex -translate-x-1/2 items-center gap-2 rounded-[var(--r-pill)] px-5 md:hidden"
        style={{
          bottom: 'calc(env(safe-area-inset-bottom, 0px) + 20px)',
          background: 'var(--ink)',
          color: 'var(--bg)',
          minHeight: 44,
          boxShadow: 'var(--shadow-sheet)',
        }}
      >
        {mapOn ? (
          <List size={16} strokeWidth={1.5} aria-hidden />
        ) : (
          <MapIcon size={16} strokeWidth={1.5} aria-hidden />
        )}
        {mapOn ? 'List' : 'Map'}
      </button>

      <Footer organizers={cal.organizers} />

      <Suspense fallback={null}>
        {selectedEvent && (
          <EventSheet
            event={selectedEvent}
            tz={cal.tz}
            now={cal.now}
            moreFromOrganizer={moreFromOrganizer}
            isPhone={isPhone}
            onClose={() => actions.openEvent(null)}
            onOpenOther={onOpen}
            onToast={showToast}
          />
        )}
        {filtersOpen && (
          <FiltersSheet
            open={filtersOpen}
            onOpenChange={setFiltersOpen}
            current={url.filters}
            sectorCounts={derived.sectorCounts}
            localityCounts={derived.localityCounts}
            countFor={countFor}
            onApply={(next) => actions.applyFilters(next)}
            isPhone={isPhone}
            showWherePanel={!railVisible}
          />
        )}
        {subscribeOpen && (
          <SubscribePopover
            open={subscribeOpen}
            onOpenChange={setSubscribeOpen}
            city={url.city}
            cityLabel={cal.cityLabel}
          />
        )}
      </Suspense>

      <Toast message={toast} />
    </>
  );
}

function LoadingShell({ cityLabel }: { cityLabel: string }) {
  return (
    <>
      <div style={{ background: 'var(--brand)' }}>
        <div className="mx-auto w-full max-w-[1440px] px-4 pt-[72px] pb-7 sm:px-6">
          <h1 className="t-h1" style={{ color: 'var(--brand-ink)' }}>
            What&rsquo;s on in {cityLabel}
          </h1>
          <MetaSkeleton />
        </div>
      </div>
      <TideSkeleton />
      <AgendaSkeleton />
    </>
  );
}

export function App() {
  const cityLabel = getCity(new URLSearchParams(window.location.search).get('city')).label;

  return (
    <>
      <a href="#main" className="skip-link t-meta">
        Skip to events
      </a>
      <Boundary
        fallback={(retry) => (
          <ErrorState
            city={cityLabel}
            onRetry={() => {
              invalidateEvents();
              retry();
            }}
          />
        )}
      >
        <Suspense fallback={<LoadingShell cityLabel={cityLabel} />}>
          <Calendar />
        </Suspense>
      </Boundary>
    </>
  );
}
