import { ChevronLeft, ChevronRight } from 'lucide-react';
import { motion } from 'motion/react';
import { useCallback, useEffect, useRef, useState } from 'react';
import { LENSES } from '../../data/lenses';
import { RAIL_ORDER, SECTOR_LABEL, isSectorId } from '../../data/sectors';
import type { LensId, SectorId } from '../../data/types';
import { spring } from '../../motion/tokens';
import { SectorIcon } from '../SectorIcon';

export type SectorRailProps = {
  lens: LensId;
  selected: string[];
  onSelect: (id: string | null) => void;
};

type Item = { id: string; label: string; color?: string };

/**
 * Mission-first order, not by volume. Technology is 4% of the listings and
 * leads the rail, because it is why someone opens a calendar branded for
 * technologists.
 */
function itemsFor(lens: LensId): Item[] {
  if (lens === 'community_sectors') {
    return RAIL_ORDER.map((id) => ({ id, label: SECTOR_LABEL[id] }));
  }
  return LENSES[lens].categories.map((c) => ({ id: c.id, label: c.label, color: c.color }));
}

/** The colour that identifies a rail item once it is active. */
function accentFor(item: Item | null): string {
  if (item === null) return 'var(--brand-on-bg)';
  if (item.color) return item.color;
  return isSectorId(item.id) ? `var(--sector-${item.id})` : 'var(--brand-on-bg)';
}

export function SectorRail({ lens, selected, onSelect }: SectorRailProps) {
  const scrollerRef = useRef<HTMLUListElement | null>(null);
  const [overflow, setOverflow] = useState({ start: false, end: false });
  const items = itemsFor(lens);
  const allActive = selected.length === 0;

  const measure = useCallback(() => {
    const el = scrollerRef.current;
    if (!el) return;
    setOverflow({
      start: el.scrollLeft > 4,
      end: el.scrollLeft + el.clientWidth < el.scrollWidth - 4,
    });
  }, []);

  useEffect(() => {
    measure();
    const el = scrollerRef.current;
    if (!el) return;
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    el.addEventListener('scroll', measure, { passive: true });
    return () => {
      ro.disconnect();
      el.removeEventListener('scroll', measure);
    };
  }, [measure, lens]);

  const nudge = (dir: -1 | 1) => {
    scrollerRef.current?.scrollBy({ left: dir * 240, behavior: 'smooth' });
  };

  const renderItem = (item: Item | null) => {
    const isAll = item === null;
    const id = isAll ? 'all' : item.id;
    const active = isAll ? allActive : selected.includes(item.id);
    const accent = accentFor(item);

    return (
      <li key={id} className="relative shrink-0">
        <button
          type="button"
          aria-pressed={active}
          onClick={() => onSelect(isAll ? null : item.id)}
          // A 76px floor plus 12px of padding, so labels can never touch.
          className="rail-item flex flex-col items-center justify-center gap-1 px-3"
          style={{
            minWidth: 76,
            minHeight: 56,
            color: active ? 'var(--ink)' : 'var(--ink-2)',
          }}
        >
          <span
            className="rail-icon flex h-[22px] items-center justify-center"
            style={{ color: active ? accent : 'var(--ink-2)' }}
          >
            {isAll || item.color === undefined ? (
              <SectorIcon sector={(isAll ? 'all' : item.id) as SectorId | 'all'} size={22} />
            ) : (
              <span aria-hidden className="h-3 w-3 rounded-full" style={{ background: item.color, border: '1px solid var(--ink)' }} />
            )}
          </span>
          <span className={`t-rail whitespace-nowrap ${active ? 't-rail-active' : ''}`}>
            {isAll ? 'All' : item.label}
          </span>
        </button>
        {active && (
          <motion.span
            layoutId="rail-underline"
            transition={spring.snappy}
            aria-hidden
            className="absolute right-2 bottom-0 left-2 block h-[2px] rounded-full"
            style={{ background: item?.color ? 'var(--brand-on-bg)' : accent }}
          />
        )}
      </li>
    );
  };

  return (
    <div className="relative flex items-center">
      {overflow.start && (
        <button
          type="button"
          onClick={() => nudge(-1)}
          aria-label="Scroll sectors left"
          className="absolute left-0 z-10 hidden h-full w-8 items-center justify-center md:flex"
          style={{
            background: 'linear-gradient(to right, var(--bg) 60%, transparent)',
            color: 'var(--ink-2)',
          }}
        >
          <ChevronLeft size={18} strokeWidth={1.5} aria-hidden />
        </button>
      )}

      <ul
        ref={scrollerRef}
        className={`no-scrollbar m-0 flex flex-1 list-none items-stretch overflow-x-auto p-0 ${
          overflow.start || overflow.end ? 'rail-mask' : ''
        }`}
      >
        {renderItem(null)}
        {items.map((item) => renderItem(item))}
      </ul>

      {overflow.end && (
        <button
          type="button"
          onClick={() => nudge(1)}
          aria-label="Scroll sectors right"
          className="absolute right-0 z-10 hidden h-full w-8 items-center justify-center md:flex"
          style={{
            background: 'linear-gradient(to left, var(--bg) 60%, transparent)',
            color: 'var(--ink-2)',
          }}
        >
          <ChevronRight size={18} strokeWidth={1.5} aria-hidden />
        </button>
      )}
    </div>
  );
}
