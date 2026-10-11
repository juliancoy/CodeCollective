export type ThemeChoice = 'system' | 'light' | 'dark';

const KEY = 'cc-theme';

/**
 * v2 defaults to light: on white the brand band carries the depth and event
 * photography reads properly. `data-theme` is always one of the three values,
 * so the stylesheet can key the system branch off `[data-theme='system']`
 * rather than the absence of an attribute.
 */
export function readTheme(): ThemeChoice {
  try {
    const v = localStorage.getItem(KEY);
    if (v === 'light' || v === 'dark' || v === 'system') return v;
  } catch {
    /* blocked storage falls back to the light default */
  }
  return 'light';
}

export function applyTheme(choice: ThemeChoice): void {
  document.documentElement.dataset.theme = choice;
  try {
    localStorage.setItem(KEY, choice);
  } catch {
    /* the attribute on <html> is enough for this session */
  }
}

/** True when the page is currently painting the dark surfaces. */
export function isDarkNow(): boolean {
  const choice = document.documentElement.dataset.theme;
  if (choice === 'dark') return true;
  if (choice === 'light') return false;
  return window.matchMedia('(prefers-color-scheme: dark)').matches;
}
