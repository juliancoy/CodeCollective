import { useState } from 'react';
import type { CalEvent } from '../../data/types';

/**
 * The row visual, in fallback order: the event image, the organizer's logo,
 * then an initials avatar.
 *
 * v1 ended every image-less row with a generic sector-icon tile. Across a
 * screen of rows that repetition read as a template rather than a listing,
 * and 32% of the feed has no image, so it was not rare. Initials vary by
 * organizer and carry real information.
 */
export function EventVisual({ event, size = 44 }: { event: CalEvent; size?: number }) {
  const [imageFailed, setImageFailed] = useState(false);
  const [logoFailed, setLogoFailed] = useState(false);

  const showImage = event.image !== null && !imageFailed;
  const showLogo = !showImage && event.orgLogo !== null && !logoFailed;

  if (showImage) {
    return (
      <img
        src={event.image!}
        alt=""
        width={size}
        height={size}
        loading="lazy"
        decoding="async"
        fetchPriority="low"
        onError={() => setImageFailed(true)}
        className="rounded-[var(--r-thumb)] object-cover"
        style={{ width: size, height: size, background: 'var(--bg-soft)' }}
      />
    );
  }

  if (showLogo) {
    return (
      <img
        src={event.orgLogo!}
        alt=""
        width={size}
        height={size}
        loading="lazy"
        decoding="async"
        fetchPriority="low"
        onError={() => setLogoFailed(true)}
        className="rounded-full object-contain p-1"
        style={{
          width: size,
          height: size,
          background: 'var(--bg)',
          border: '1px solid var(--line)',
        }}
      />
    );
  }

  return (
    <span
      aria-hidden
      className="flex items-center justify-center rounded-full"
      style={{
        width: size,
        height: size,
        background: `var(--sector-${event.primarySector}-tint)`,
        // Ink, not the sector colour: sector-on-tint measures about 4.4:1,
        // just under the threshold. The tint still carries the sector.
        color: 'var(--ink)',
        fontSize: Math.round(size * 0.34),
        fontWeight: 600,
        letterSpacing: '0.01em',
      }}
    >
      {event.initials}
    </span>
  );
}
