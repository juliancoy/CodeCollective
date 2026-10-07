/**
 * The one decoration on the page: depth contours off a nautical chart, the
 * kind printed across the Patapsco on a harbor map. Static, 8% Sky, right
 * third of the brand band only.
 */
export function HarborContours() {
  return (
    <svg
      aria-hidden
      focusable="false"
      viewBox="0 0 520 300"
      preserveAspectRatio="xMaxYMid slice"
      className="pointer-events-none absolute inset-y-0 right-0 hidden h-full w-[46%] md:block"
      style={{ color: 'var(--sky)', opacity: 0.08 }}
    >
      <g fill="none" stroke="currentColor" strokeWidth="1.25" strokeLinecap="round">
        <path d="M520 18C447 30 402 62 377 104c-25 42-63 66-118 72-55 6-93 28-114 66" />
        <path d="M520 54C455 65 414 94 391 133c-23 39-58 61-109 67-51 6-86 26-105 61" />
        <path d="M520 90C463 100 426 126 405 162c-21 36-53 56-100 62-47 6-79 24-96 56" />
        <path d="M520 126C471 135 438 158 419 191c-19 33-48 51-91 57-43 6-72 22-87 51" />
        <path d="M520 162C479 170 450 190 433 220c-17 30-43 46-82 52-39 6-65 20-78 46" />
        <path d="M520 198C487 205 462 222 447 249c-15 27-38 41-73 47-35 6-58 18-69 41" />
        <path d="M520 234C495 240 474 254 461 278c-13 24-33 36-64 42" />
      </g>
    </svg>
  );
}
