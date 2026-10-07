import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { isDarkNow } from './theme';

/** How far the page scrolls before the brand band collapses to its bar. */
const CONDENSE_AT = 120;

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

export function useCondensed(): boolean {
  const [condensed, setCondensed] = useState(false);
  useEffect(() => {
    const onScroll = () => setCondensed(window.scrollY > CONDENSE_AT);
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);
  return condensed;
}

/**
 * Publishes the measured tide-line height, and the total sticky chrome, so day
 * gutters stick directly beneath it and `scroll-padding-top` keeps focused
 * elements clear. Measured rather than guessed: the chrome changes height
 * between breakpoints and when the band condenses.
 */
export function useChromeHeight<T extends HTMLElement>() {
  const ref = useRef<T | null>(null);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const root = document.documentElement;
    const publish = () => {
      const tide = Math.round(el.getBoundingClientRect().height);
      const band = Number.parseInt(getComputedStyle(root).getPropertyValue('--band-h'), 10) || 64;
      const control =
        Number.parseInt(getComputedStyle(root).getPropertyValue('--control-h'), 10) || 64;
      root.style.setProperty('--tide-h', `${tide}px`);
      root.style.setProperty('--chrome-h', `${band + control + tide}px`);
    };
    publish();
    const ro = new ResizeObserver(publish);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
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
