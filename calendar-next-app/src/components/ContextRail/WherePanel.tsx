import { motion } from 'motion/react';
import { Video } from 'lucide-react';
import { spring } from '../../motion/tokens';

export type WherePanelProps = {
  localities: Array<{ name: string; count: number }>;
  onlineCount: number;
  onPickLocality: (locality: string) => void;
  onPickOnline: () => void;
};

/**
 * The "where" answer when there is no map, and useful context when there is.
 *
 * Only 47% of the feed carries coordinates, so a map alone never tells the
 * whole location story. This does, for every filtered event that names a
 * place, and it keeps the rail from ever being empty.
 */
export function WherePanel({
  localities,
  onlineCount,
  onPickLocality,
  onPickOnline,
}: WherePanelProps) {
  const rows = [
    ...localities.map((l) => ({ key: l.name, label: l.name, count: l.count, online: false })),
    ...(onlineCount > 0
      ? [{ key: '__online__', label: 'Online', count: onlineCount, online: true }]
      : []),
  ];

  if (rows.length === 0) return null;

  const max = Math.max(...rows.map((r) => r.count), 1);

  return (
    <section
      aria-labelledby="where-heading"
      className="rounded-[var(--r-sheet)] p-4"
      style={{ background: 'var(--bg-soft)' }}
    >
      <h2 id="where-heading" className="t-section" style={{ color: 'var(--ink)' }}>
        Where it&rsquo;s happening
      </h2>

      <ul className="m-0 mt-3 list-none space-y-1 p-0">
        {rows.map((row) => (
          <li key={row.key}>
            <button
              type="button"
              onClick={() => (row.online ? onPickOnline() : onPickLocality(row.label))}
              className="where-row grid w-full grid-cols-[1fr_auto] items-center gap-x-3 gap-y-1 rounded-[var(--r-cell)] px-2 py-1.5 text-left"
              style={{ minHeight: 40 }}
            >
              <span
                className="t-meta flex min-w-0 items-center gap-1.5 truncate"
                style={{ color: 'var(--ink)' }}
              >
                {row.online && (
                  <Video
                    size={13}
                    strokeWidth={2}
                    aria-hidden
                    className="shrink-0"
                    style={{ color: 'var(--ink-2)' }}
                  />
                )}
                {row.label}
              </span>
              <span className="t-meta tnum shrink-0" style={{ color: 'var(--ink-2)' }}>
                {row.count}
              </span>
              <span
                aria-hidden
                className="col-span-2 block h-1.5 overflow-hidden rounded-full"
                style={{ background: 'color-mix(in srgb, var(--brand) 10%, transparent)' }}
              >
                <motion.span
                  className="block h-full rounded-full"
                  initial={false}
                  animate={{ width: `${Math.max(6, (row.count / max) * 100)}%` }}
                  transition={spring.snappy}
                  style={{ background: 'var(--brand-on-bg)' }}
                />
              </span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
