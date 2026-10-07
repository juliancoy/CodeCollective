import { CalendarPlus, Menu as MenuIcon } from 'lucide-react';
import { useState, type ReactNode } from 'react';
import { HarborContours } from './HarborContours';

const NAV = [
  { label: 'Home', href: 'https://codecollective.us/' },
  { label: 'Platform', href: 'https://codecollective.us/platform' },
  { label: 'Calendar', href: 'https://codecollective.us/calendar', current: true },
  { label: 'Projects', href: 'https://codecollective.us/projects' },
];

export type BrandBandProps = {
  /** True once the page has scrolled past the title block. */
  condensed: boolean;
  city: string;
  /** H1 and meta line, shown only while expanded. */
  title: ReactNode;
  meta: ReactNode;
  /** The search pill. Row 2 when expanded, row 1 when condensed. */
  pill: ReactNode;
  onSubscribe: () => void;
};

/**
 * Layer 1 of three. Identity, place and search, on Collective Blue.
 *
 * v1 spent five equal full-width bands before the first event. Everything that
 * used to sit in its own row — nav, the H1, the meta line, the data banner and
 * the search pill — lives here now, and the whole band scrolls away into a
 * 64px bar. The navy is what makes the calm white content below read as
 * deliberate rather than empty.
 */
export function BrandBand({ condensed, city, title, meta, pill, onSubscribe }: BrandBandProps) {
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <header
      className="sticky top-0 z-40 w-full"
      style={{ background: 'var(--brand)', color: 'var(--brand-ink)' }}
    >
      <div className="relative overflow-hidden">
        <HarborContours />

        {/* Row 1: identity and account, always present. */}
        <div className="relative mx-auto flex h-16 w-full max-w-[1440px] items-center gap-4 px-4 sm:px-6">
          <a href="https://codecollective.us/" className="t-body shrink-0 font-semibold">
            Code Collective
          </a>

          {condensed ? (
            <div className="flex min-w-0 flex-1 justify-center px-2">{pill}</div>
          ) : (
            <nav aria-label="Main" className="hidden flex-1 justify-center md:flex">
              <ul className="flex list-none items-center gap-6 p-0">
                {NAV.map((item) => (
                  <li key={item.label}>
                    <a
                      href={item.href}
                      aria-current={item.current ? 'page' : undefined}
                      className="t-meta"
                      style={{ color: item.current ? 'var(--brand-ink)' : 'var(--band-meta)' }}
                    >
                      {item.label}
                    </a>
                  </li>
                ))}
              </ul>
            </nav>
          )}

          <div className="ml-auto flex shrink-0 items-center gap-2 sm:gap-3">
            <button
              type="button"
              onClick={onSubscribe}
              aria-label="Subscribe"
              className="t-meta flex items-center justify-center gap-2 rounded-[var(--r-pill)] border px-3"
              style={{
                borderColor: 'var(--sky)',
                color: 'var(--sky)',
                minWidth: 44,
                minHeight: 40,
              }}
            >
              <CalendarPlus size={16} strokeWidth={1.5} aria-hidden />
              <span className="hidden sm:inline">Subscribe</span>
            </button>
            <a
              href="https://orgportal.cc/"
              className="t-meta hidden sm:inline"
              style={{ color: 'var(--band-meta)' }}
            >
              Log in
            </a>
            <button
              type="button"
              onClick={() => setMenuOpen((v) => !v)}
              aria-expanded={menuOpen}
              aria-controls="mobile-nav"
              aria-label="Menu"
              className="flex items-center justify-center rounded-[var(--r-pill)] border md:hidden"
              style={{ borderColor: 'rgb(135 206 235 / 0.4)', color: 'var(--brand-ink)', minWidth: 44, minHeight: 44 }}
            >
              <MenuIcon size={18} strokeWidth={1.5} aria-hidden />
            </button>
          </div>
        </div>

        {/* Row 2: the title block and the search pill. */}
        {!condensed && (
          <div className="relative mx-auto w-full max-w-[1440px] px-4 pb-7 sm:px-6">
            <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between lg:gap-8">
              <div className="min-w-0">
                <h1 className="t-h1" style={{ color: 'var(--brand-ink)' }}>
                  {title}
                </h1>
                <p className="t-band-meta mt-2" style={{ color: 'var(--band-meta)' }}>
                  {meta}
                </p>
              </div>
              <div className="w-full lg:w-auto lg:min-w-[520px] lg:shrink-0">{pill}</div>
            </div>
          </div>
        )}
      </div>

      {menuOpen && (
        <nav
          id="mobile-nav"
          aria-label="Main"
          className="relative border-t md:hidden"
          style={{ borderColor: 'rgb(135 206 235 / 0.25)' }}
        >
          <ul className="m-0 list-none p-2">
            {[...NAV, { label: 'Log in', href: 'https://orgportal.cc/', current: false }].map(
              (item) => (
                <li key={item.label}>
                  <a
                    href={item.href}
                    aria-current={item.current ? 'page' : undefined}
                    className="t-body block rounded-[var(--r-cell)] px-3 py-3"
                    style={{
                      color: item.current ? 'var(--brand-ink)' : 'var(--band-meta)',
                      minHeight: 44,
                    }}
                  >
                    {item.label}
                  </a>
                </li>
              ),
            )}
          </ul>
        </nav>
      )}
      <nav aria-label="Calendar views" className="relative flex flex-wrap justify-center gap-2 px-4 py-2">
        {[
          { label: 'Calendar', path: '/calendar.html', query: '&view=calendar' },
          { label: 'Cards', path: '/calendar_cards.html', query: '' },
          { label: 'Simple', path: '/simplecalendar.html', query: '' },
          { label: 'Agenda', path: '/calendar-next/', query: '' },
        ].map(({ label, path, query }) => (
          <a key={label} href={`${path}?city=${encodeURIComponent(city)}${query}`}
            aria-current={label === 'Agenda' ? 'page' : undefined}
            className="t-meta rounded-full border px-4 py-2"
            style={{ color: 'var(--brand-ink)', borderColor: 'var(--band-meta)', fontWeight: label === 'Agenda' ? 700 : undefined }}>
            {label}
          </a>
        ))}
      </nav>
    </header>
  );
}
