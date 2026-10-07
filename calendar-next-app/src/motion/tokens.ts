/**
 * One orchestrated moment on load; everything else answers a visitor action
 * and shows what changed. Only transform and opacity are ever animated.
 */
export const duration = {
  instant: 0.1,
  quick: 0.16,
  base: 0.24,
  calm: 0.36,
  slow: 0.56,
} as const;

export const ease = {
  /** Entering. */
  out: [0.2, 0.8, 0.2, 1] as const,
  /** Moving between two states. */
  inOut: [0.65, 0, 0.35, 1] as const,
};

export const spring = {
  snappy: { type: 'spring', visualDuration: 0.3, bounce: 0.1 },
  gentle: { type: 'spring', visualDuration: 0.5, bounce: 0.15 },
} as const;

/** Tide-line bars rise left to right on first load. */
export const TIDE_STAGGER = 0.018;
/** Agenda rows fade in behind them. */
export const ROW_STAGGER = 0.03;
