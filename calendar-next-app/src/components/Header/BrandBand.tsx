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
  city: string;
  /** H1 and meta line in the scrolling introduction. */
  title: ReactNode;
  meta: ReactNode;
  /** The search pill stays mounted in the sticky bar. */
  pill: ReactNode;
  onSubscribe: () => void;
};

/** Stable sticky navigation; the introduction scrolls independently. */
export function BrandBand({ city, title, meta, pill, onSubscribe }: BrandBandProps) {
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <>
    <header
      data-calendar-band
      className="calendar-brand-band sticky top-0 z-40 w-full"
      style={{ background: 'var(--brand)', color: 'var(--brand-ink)' }}
    >
      <div className="relative overflow-hidden">
        <HarborContours />

        {/* Row 1: identity and account, always present. */}
        <div className="relative mx-auto flex h-16 w-full max-w-[1440px] items-center gap-4 px-4 sm:px-6">
          <a href="https://codecollective.us/" aria-label="Code Collective home" className="calendar-wordmark t-body flex shrink-0 items-center gap-2 font-semibold">
            <img src="/images/favicons/favicon.png" alt="" width="28" height="28" />
            <span className="hidden lg:inline">Code Collective</span>
          </a>

          <div className="flex min-w-0 flex-1 justify-center px-2">{pill}</div>

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
            className="calendar-view-link t-meta rounded-full border px-3 py-1"
            style={{ color: label === 'Agenda' ? 'var(--brand)' : 'var(--brand-ink)', background: label === 'Agenda' ? 'var(--warm)' : 'transparent', borderColor: label === 'Agenda' ? 'var(--warm)' : 'var(--band-meta)', fontWeight: label === 'Agenda' ? 700 : undefined }}>
            {label}
          </a>
        ))}
      </nav>
    </header>
    <section className="calendar-intro" aria-label="Calendar introduction">
      <div className="mx-auto w-full max-w-[1440px] px-4 py-6 sm:px-6">
            <nav aria-label="Main" className="hidden flex-1 justify-center md:flex">
              <ul className="flex list-none items-center gap-6 p-0">
                {NAV.map((item) => (
                  <li key={item.label}>
                    <a
                      href={item.href}
                      aria-current={item.current ? 'page' : undefined}
                      className="t-meta"
                      style={{ color: 'var(--brand-soft-ink)' }}
                    >
                      {item.label}
                    </a>
                  </li>
                ))}
              </ul>
            </nav>

        <h1 className="t-h1 mt-5">{title}</h1>
        <p className="t-band-meta mt-2">{meta}</p>
      </div>
    </section>
    </>
  );
}
