import { Monitor, Moon, Sun } from 'lucide-react';
import { useEffect, useState } from 'react';
import { applyTheme, readTheme, type ThemeChoice } from '../app/theme';

const CHOICES: Array<{ id: ThemeChoice; label: string; Icon: typeof Sun }> = [
  { id: 'system', label: 'System', Icon: Monitor },
  { id: 'light', label: 'Light', Icon: Sun },
  { id: 'dark', label: 'Dark', Icon: Moon },
];

export function Footer({ organizers }: { organizers: number }) {
  const [theme, setTheme] = useState<ThemeChoice>('system');

  // Read after mount: the inline script in index.html has already applied it.
  useEffect(() => setTheme(readTheme()), []);

  const pick = (choice: ThemeChoice) => {
    setTheme(choice);
    applyTheme(choice);
  };

  return (
    <footer
      className="mx-auto w-full max-w-[1440px] border-t px-4 py-8 sm:px-6"
      style={{ borderColor: 'var(--line)' }}
    >
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
          <span className="t-meta font-semibold" style={{ color: 'var(--ink)' }}>
            Code Collective
          </span>
          <a
            href="mailto:julian@codecollective.us"
            className="t-meta inline-flex items-center"
            style={{ color: 'var(--ink-2)', minHeight: 24 }}
          >
            Contact
          </a>
          <span className="t-meta tnum" style={{ color: 'var(--ink-2)' }}>
            Events from {organizers} organizers
          </span>
          <a
            href="https://github.com/juliancoy/CodeCollective"
            target="_blank"
            rel="noopener noreferrer"
            className="t-meta inline-flex items-center"
            style={{ color: 'var(--ink-2)', minHeight: 24 }}
          >
            GitHub
          </a>
        </div>

        <fieldset className="m-0 flex items-center gap-1 border-0 p-0">
          <legend className="sr-only">Theme</legend>
          {CHOICES.map(({ id, label, Icon }) => (
            <button
              key={id}
              type="button"
              aria-pressed={theme === id}
              onClick={() => pick(id)}
              className="t-caption flex items-center gap-2 rounded-[var(--r-pill)] border px-3"
              style={{
                minHeight: 44,
                borderColor: theme === id ? 'var(--brand)' : 'var(--line)',
                background: theme === id ? 'var(--brand-soft)' : 'transparent',
                color: 'var(--ink)',
              }}
            >
              <Icon size={15} strokeWidth={1.5} aria-hidden />
              {label}
            </button>
          ))}
        </fieldset>
      </div>
    </footer>
  );
}
