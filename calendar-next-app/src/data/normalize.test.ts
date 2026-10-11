import { describe, expect, it } from 'vitest';
import {
  decodeEntities,
  eventKey,
  fnv1a,
  normalizeEvent,
  normalizeEvents,
  toExcerpt,
} from './normalize';
import type { RawEvent } from './types';

const ET = 'America/New_York';
const NOW = new Date('2026-09-25T16:00:00Z'); // noon Eastern

function raw(over: Partial<RawEvent> = {}): RawEvent {
  return {
    name: 'Bmore on Rails',
    description: 'A monthly Ruby meetup.',
    startDate: '2026-09-26T22:00:00+00:00',
    endTime: '2026-09-27T01:00:00+00:00',
    url: 'https://luma.com/bmore-on-rails',
    status: 'ACTIVE',
    location: {
      name: 'Spark Baltimore',
      address: '8 Market Pl, Baltimore, MD, 21202',
      city: 'Baltimore',
      state: 'MD',
      latitude: 39.2879,
      longitude: -76.6055,
    },
    imageUrl: '/event_images/Bmore_on_Rails.webp',
    orgImageUrl: 'https://example.com/logo.png',
    recurring: true,
    scrapeTime: '2026-09-25T04:02:10-04:00',
    tags: ['Ruby', 'Tech Community'],
    source: 'https://luma.com/bmore-on-rails',
    source_url: 'https://luma.com/bmore-on-rails',
    source_group: 'Bmore on Rails',
    org_name: 'Bmore on Rails',
    orgName: 'Bmore on Rails',
    ...over,
  };
}

const opts = { tz: ET, now: NOW };

describe('keys', () => {
  it('builds on the upstream id when there is one', () => {
    expect(eventKey({ id: 'evt-123', name: 'x', startDate: 'y', source: 'z' })).toMatch(
      /^evt-123@[0-9a-z]+$/,
    );
  });

  it('separates occurrences that share one upstream id', () => {
    // 18 time.ly ids in the Baltimore feed are reused across every date in a
    // recurring series. Keying on the id alone dropped 161 real events.
    const series = { id: 'abc-time.ly', name: 'Public Ice Skating', source: 'https://t.fun' };
    const a = eventKey({ ...series, startDate: '2026-09-25T16:00:00+00:00' });
    const b = eventKey({ ...series, startDate: '2026-09-28T16:00:00+00:00' });
    expect(a).not.toBe(b);
  });

  it('treats a blank id as absent', () => {
    const blank = eventKey({ id: '   ', name: 'A', startDate: 'S', source: 'U' });
    const none = eventKey({ name: 'A', startDate: 'S', source: 'U' });
    expect(blank).toBe(none);
  });

  it('is stable for the same name, start and source', () => {
    const a = eventKey({ name: 'A', startDate: 'S', source: 'U' });
    const b = eventKey({ name: 'A', startDate: 'S', source: 'U' });
    expect(a).toBe(b);
    expect(a).toMatch(/^[0-9a-z]+$/);
  });

  it('differs when any input differs', () => {
    const base = { name: 'A', startDate: 'S', source: 'U' };
    expect(eventKey(base)).not.toBe(eventKey({ ...base, name: 'B' }));
    expect(eventKey(base)).not.toBe(eventKey({ ...base, startDate: 'T' }));
    expect(eventKey(base)).not.toBe(eventKey({ ...base, source: 'V' }));
  });

  it('hashes without collision over the empty string', () => {
    expect(fnv1a('')).toBe((0x811c9dc5).toString(36));
  });
});

describe('images', () => {
  it('makes a site-relative path absolute', () => {
    expect(normalizeEvent(raw(), opts)!.image).toBe(
      'https://codecollective.us/event_images/Bmore_on_Rails.webp',
    );
  });

  it('leaves an absolute logo alone', () => {
    expect(normalizeEvent(raw(), opts)!.orgLogo).toBe('https://example.com/logo.png');
  });

  it('turns an empty string into null', () => {
    const ev = normalizeEvent(raw({ imageUrl: '', orgImageUrl: null }), opts)!;
    expect(ev.image).toBeNull();
    expect(ev.orgLogo).toBeNull();
  });
});

describe('end times', () => {
  it('prefers endTime over endDate', () => {
    const ev = normalizeEvent(
      raw({ endTime: '2026-09-27T01:00:00+00:00', endDate: '2026-09-27T03:00:00+00:00' }),
      opts,
    )!;
    expect(ev.end!.toISOString()).toBe('2026-09-27T01:00:00.000Z');
  });

  it('falls back to endDate when endTime is absent', () => {
    const r = raw();
    delete r.endTime;
    const ev = normalizeEvent({ ...r, endDate: '2026-09-27T02:00:00+00:00' }, opts)!;
    expect(ev.end!.toISOString()).toBe('2026-09-27T02:00:00.000Z');
  });

  it('drops an end that is not after the start', () => {
    const ev = normalizeEvent(raw({ endTime: '2026-09-26T21:00:00+00:00' }), opts)!;
    expect(ev.end).toBeNull();
  });

  it('drops an unparseable end', () => {
    const ev = normalizeEvent(raw({ endTime: 'not a date', endDate: undefined }), opts)!;
    expect(ev.end).toBeNull();
  });
});

describe('all day', () => {
  it('flags a span of 20 hours or more', () => {
    const ev = normalizeEvent(
      raw({ startDate: '2026-09-26T04:00:00+00:00', endTime: '2026-09-27T04:00:00+00:00' }),
      opts,
    )!;
    expect(ev.allDay).toBe(true);
  });

  it('flags a local-midnight start with no end', () => {
    // 04:00Z is midnight Eastern.
    const ev = normalizeEvent(
      raw({ startDate: '2026-09-26T04:00:00+00:00', endTime: undefined, endDate: undefined }),
      opts,
    )!;
    expect(ev.allDay).toBe(true);
  });

  it('does not flag a midnight-UTC concert, which is 8 PM Eastern', () => {
    const ev = normalizeEvent(
      raw({ startDate: '2026-09-27T00:00:00+00:00', endTime: undefined, endDate: undefined }),
      opts,
    )!;
    expect(ev.allDay).toBe(false);
    expect(ev.dayKey).toBe('2026-09-26');
  });
});

describe('dropping what has finished', () => {
  it('keeps an event still running', () => {
    const ev = normalizeEvent(
      raw({ startDate: '2026-09-25T15:00:00Z', endTime: '2026-09-25T17:00:00Z' }),
      opts,
    );
    expect(ev).not.toBeNull();
  });

  it('drops an event that ended before now', () => {
    const ev = normalizeEvent(
      raw({ startDate: '2026-09-25T12:00:00Z', endTime: '2026-09-25T14:00:00Z' }),
      opts,
    );
    expect(ev).toBeNull();
  });

  it('treats an event with no end as two hours long', () => {
    // Started 13:00Z, so it is over at 15:00Z, before the 16:00Z reference.
    expect(
      normalizeEvent(raw({ startDate: '2026-09-25T13:00:00Z', endTime: undefined, endDate: undefined }), opts),
    ).toBeNull();
    // Started 15:00Z, so it runs until 17:00Z and is still listed.
    expect(
      normalizeEvent(raw({ startDate: '2026-09-25T15:00:00Z', endTime: undefined, endDate: undefined }), opts),
    ).not.toBeNull();
  });

  it('drops a row with no usable start', () => {
    expect(normalizeEvent(raw({ startDate: 'nonsense' }), opts)).toBeNull();
  });
});

describe('location', () => {
  it('reads a structured location', () => {
    const ev = normalizeEvent(raw(), opts)!;
    expect(ev.venue).toBe('Spark Baltimore');
    expect(ev.address).toBe('8 Market Pl, Baltimore, MD, 21202');
    expect(ev.locality).toBe('Baltimore');
    expect(ev.coords).toEqual({ lat: 39.2879, lng: -76.6055 });
  });

  it('accepts a bare string as the venue', () => {
    const ev = normalizeEvent(raw({ location: 'Unallocated Space' }), opts)!;
    expect(ev.venue).toBe('Unallocated Space');
    expect(ev.address).toBeNull();
    expect(ev.coords).toBeNull();
  });

  it('shows the address once when it duplicates the name', () => {
    const ev = normalizeEvent(
      raw({ location: { name: '1 Main St', address: '1 Main St' } }),
      opts,
    )!;
    expect(ev.venue).toBe('1 Main St');
    expect(ev.address).toBeNull();
  });

  it('rejects non-finite coordinates', () => {
    for (const bad of [{ latitude: 39.3 }, { longitude: -76.6 }, { latitude: Number.NaN, longitude: -76.6 }]) {
      const ev = normalizeEvent(raw({ location: { name: 'X', ...bad } }), opts)!;
      expect(ev.coords).toBeNull();
    }
  });
});

describe('sectors', () => {
  it('maps tags in category-map order', () => {
    // Ruby is Technology; Tech Community is also Technology.
    expect(normalizeEvent(raw(), opts)!.sectors).toEqual(['technology']);
  });

  it('keeps several sectors in map order, not tag order', () => {
    const ev = normalizeEvent(raw({ tags: ['Religion', 'Python'] }), opts)!;
    expect(ev.sectors).toEqual(['technology', 'faith']);
    expect(ev.primarySector).toBe('technology');
  });

  it('falls back to other when no tag matches', () => {
    const ev = normalizeEvent(raw({ tags: ['Food', 'Clothing'] }), opts)!;
    expect(ev.sectors).toEqual(['other']);
    expect(ev.primarySector).toBe('other');
  });

  it('falls back to other for an empty tag list', () => {
    expect(normalizeEvent(raw({ tags: [] }), opts)!.sectors).toEqual(['other']);
  });
});

describe('status and provenance', () => {
  it('reads a cancellation', () => {
    expect(normalizeEvent(raw({ status: 'CANCELLED' }), opts)!.cancelled).toBe(true);
    expect(normalizeEvent(raw({ status: 'ACTIVE' }), opts)!.cancelled).toBe(false);
  });

  it('flags a Code Collective source as featured', () => {
    expect(normalizeEvent(raw({ source: 'https://lu.ma/codecollective' }), opts)!.featured).toBe(true);
    expect(normalizeEvent(raw({ source: 'https://luma.com/codecollective' }), opts)!.featured).toBe(true);
    expect(normalizeEvent(raw({ source: 'https://luma.com/bmore-on-rails' }), opts)!.featured).toBe(false);
  });

  it('keeps a multi-day end key and clears a same-day one', () => {
    expect(normalizeEvent(raw(), opts)!.endDayKey).toBeNull();
    const multi = normalizeEvent(
      raw({ startDate: '2026-09-26T14:00:00Z', endTime: '2026-09-28T20:00:00Z' }),
      opts,
    )!;
    expect(multi.dayKey).toBe('2026-09-26');
    expect(multi.endDayKey).toBe('2026-09-28');
  });
});

describe('scrapeTime, which arrives in four shapes', () => {
  it('reads an offset-less stamp as Eastern, not as the viewer local zone', () => {
    // 1,422 of 1,695 rows look like this. Parsed as local time they would
    // resolve to a different instant for every visitor.
    const ev = normalizeEvent(raw({ scrapeTime: '2026-09-25 08:08:02.924000' }), opts)!;
    expect(ev.scrapedAt!.toISOString()).toBe('2026-09-25T12:08:02.924Z');
  });

  it('honours an explicit offset when there is one', () => {
    const ev = normalizeEvent(raw({ scrapeTime: '2026-09-25T04:02:10.681753-04:00' }), opts)!;
    expect(ev.scrapedAt!.toISOString()).toBe('2026-09-25T08:02:10.681Z');
  });

  it('handles a seconds-only stamp and a bare date', () => {
    expect(normalizeEvent(raw({ scrapeTime: '2026-05-22 00:00:00' }), opts)!.scrapedAt!.toISOString()).toBe(
      '2026-05-22T04:00:00.000Z',
    );
    expect(normalizeEvent(raw({ scrapeTime: '2026-05-22' }), opts)!.scrapedAt!.toISOString()).toBe(
      '2026-05-22T04:00:00.000Z',
    );
  });

  it('reads a winter stamp at the winter offset', () => {
    // -05:00 in January, so the same wall clock is an hour later in UTC.
    const ev = normalizeEvent(raw({ scrapeTime: '2026-01-15 08:00:00' }), opts)!;
    expect(ev.scrapedAt!.toISOString()).toBe('2026-01-15T13:00:00.000Z');
  });

  it('yields null for an unparseable stamp', () => {
    expect(normalizeEvent(raw({ scrapeTime: 'whenever' }), opts)!.scrapedAt).toBeNull();
  });
});

describe('html entities in plain-text fields', () => {
  it('decodes the entities the feed actually ships', () => {
    const ev = normalizeEvent(
      raw({ name: 'Full Body Sculpt: Strength &amp; Conditioning' }),
      opts,
    )!;
    expect(ev.title).toBe('Full Body Sculpt: Strength & Conditioning');
  });

  it('decodes zero-padded and named numeric references', () => {
    expect(decodeEntities('Rock &#038; Roll')).toBe('Rock & Roll');
    expect(decodeEntities('Sept &#8211; Oct')).toBe('Sept – Oct');
    expect(decodeEntities('It&#8217;s here')).toBe('It’s here');
    expect(decodeEntities('She said &quot;hi&quot;')).toBe('She said "hi"');
    expect(decodeEntities('caf&eacute;')).toBe('café');
    expect(decodeEntities('&#x2014;')).toBe('—');
  });

  it('decodes once, so text that reads &amp;amp; survives', () => {
    expect(decodeEntities('A &amp;amp; B')).toBe('A &amp; B');
  });

  it('leaves unknown or malformed references alone', () => {
    expect(decodeEntities('50 &widget; each')).toBe('50 &widget; each');
    expect(decodeEntities('a & b')).toBe('a & b');
    expect(decodeEntities('&#0;')).toBe('&#0;');
    expect(decodeEntities('&#xD800;')).toBe('&#xD800;');
  });

  it('decodes venue and locality too', () => {
    const ev = normalizeEvent(
      raw({ location: { name: 'Bar &amp; Grill', address: '1 Rock &#038; Roll Way', city: 'Towson' } }),
      opts,
    )!;
    expect(ev.venue).toBe('Bar & Grill');
    expect(ev.address).toBe('1 Rock & Roll Way');
  });
});

describe('excerpt', () => {
  it('strips html and markdown', () => {
    expect(toExcerpt('<p>Hello <strong>there</strong></p>')).toBe('Hello there');
    expect(toExcerpt('## Heading\n\n**bold** and [a link](https://x.com)')).toBe(
      'Heading bold and a link',
    );
  });

  it('truncates on a word boundary with an ellipsis', () => {
    const out = toExcerpt('word '.repeat(60));
    expect(out.length).toBeLessThanOrEqual(161);
    expect(out.endsWith('…')).toBe(true);
  });
});

describe('normalizeEvents', () => {
  it('sorts chronologically and de-duplicates by key', () => {
    const rows = [
      raw({ id: 'b', startDate: '2026-09-28T18:00:00Z', name: 'Later' }),
      raw({ id: 'a', startDate: '2026-09-26T18:00:00Z', name: 'Sooner' }),
      raw({ id: 'a', startDate: '2026-09-26T18:00:00Z', name: 'Sooner' }),
    ];
    const out = normalizeEvents(rows, opts);
    expect(out.map((e) => e.title)).toEqual(['Sooner', 'Later']);
  });

  it('skips malformed rows without throwing', () => {
    const rows = [null, undefined, 42, raw()] as unknown as RawEvent[];
    expect(normalizeEvents(rows, opts)).toHaveLength(1);
  });
});

describe('percent escapes in scraped titles', () => {
  const title = (name: string) => normalizeEvent(raw({ name }), opts)!.title;

  it('lands both encodings of the same event on the same title', () => {
    // The live feed carries this event twice, once with &#038; and once with
    // %26. They have to agree or no dedupe can see them as one event.
    const entity = title('From Crisis to Connection: A Lunch &#038; Learn');
    const percent = title('From Crisis to Connection: A Lunch %26 Learn');
    expect(percent).toBe(entity);
    expect(percent).toContain('Lunch & Learn');
  });

  it('leaves a literal percent sign alone', () => {
    // decodeURIComponent would throw on the first and mangle the second.
    expect(title('Save 50% on tickets')).toContain('50%');
    expect(title('Up to 20%25 off')).toContain('20%');
  });
});
