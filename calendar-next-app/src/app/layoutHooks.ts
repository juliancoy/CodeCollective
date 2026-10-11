import { useCallback, useEffect, useLayoutEffect, useState } from 'react';
import { isDarkNow } from './theme';

export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(() =>
    typeof window === 'undefined' ? false : window.matchMedia(query).matches,
  );
  useEffect(() => {
    const mq = window.matchMedia(query);
    const onChange = () => setMatches(mq.matches);
    onChange();
    mq.addEventListener('change', onChange);
    return () => mq.removeEventListener('change', onChange);
  }, [query]);
  return matches;
}

/**
 * Publishes the measured tide-line height, and the total sticky chrome, so day
 * gutters stick directly beneath it and `scroll-padding-top` keeps focused
 * elements clear. Measured rather than guessed: the chrome changes height
 * between breakpoints and when the mobile menu opens.
 */
export function useChromeHeight<T extends HTMLElement>() {
  const [el, setElement] = useState<T | null>(null);
  const ref = useCallback((node: T | null) => setElement(node), []);
  useLayoutEffect(() => {
    const root = document.documentElement;
    const band = document.querySelector<HTMLElement>('[data-calendar-band]');
    const controls = document.querySelector<HTMLElement>('[data-calendar-controls]');
    const publish = () => {
      const tide = Math.ceil(el?.getBoundingClientRect().height ?? 0);
      const bandHeight = Math.ceil(band?.getBoundingClientRect().height ?? 64);
      const control = Math.ceil(controls?.getBoundingClientRect().height ?? 64);
      root.style.setProperty('--band-h', `${bandHeight}px`);
      root.style.setProperty('--control-h', `${control}px`);
      root.style.setProperty('--tide-h', `${tide}px`);
      root.style.setProperty('--chrome-h', `${bandHeight + control + tide}px`);
    };
    publish();
    const ro = new ResizeObserver(publish);
    for (const node of [el, band, controls]) if (node) ro.observe(node);
    return () => ro.disconnect();
  }, [el]);
  return ref;
}

export function useDarkTheme(): boolean {
  const [dark, setDark] = useState(() => (typeof window === 'undefined' ? false : isDarkNow()));
  useEffect(() => {
    const update = () => setDark(isDarkNow());
    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    mq.addEventListener('change', update);
    const mo = new MutationObserver(update);
    mo.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
    return () => {
      mq.removeEventListener('change', update);
      mo.disconnect();
    };
  }, []);
  return dark;
}
