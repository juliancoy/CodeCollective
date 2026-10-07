import type { SectorId } from './types';

/**
 * The community_sectors category map, vendored from
 * https://codecollective.us/data/category_maps/community_sectors.json
 * (that path is not in the site's CORS allowlist, so it cannot be fetched).
 *
 * `matches` are the upstream tag names. Order matters twice over:
 *  - MAP_ORDER decides `sectors[]` and therefore `primarySector`
 *  - RAIL_ORDER decides what the visitor sees, tech and builder sectors first
 */
export type SectorDef = {
  id: SectorId;
  label: string;
  matches: string[];
};

export const SECTORS: SectorDef[] = [
  {
    id: 'technology',
    label: 'Technology',
    matches: [
      'Technology', 'Tech Skills', 'AI', 'Data Science', 'Cybersecurity', 'Cloud',
      'Platform', 'DevOps', 'Software Development', 'Web Development', 'JavaScript',
      'Python', 'Ruby', 'Product', 'UX', 'Game Development', 'Technical Writing',
      'Open Source', 'Tech Community',
    ],
  },
  { id: 'education', label: 'Education', matches: ['Education', 'Science', 'Lifelong Learning', 'Youth Education'] },
  { id: 'entrepreneurship', label: 'Entrepreneurship', matches: ['Entrepreneurship', 'Business', 'Startup', 'Career Growth', 'Professional Networking'] },
  { id: 'economics', label: 'Economics', matches: ['Economics', 'Economic Development'] },
  { id: 'finance', label: 'Finance', matches: ['Finance', 'Crypto', 'Web3'] },
  { id: 'health', label: 'Health', matches: ['Health', 'Wellness'] },
  { id: 'politics', label: 'Politics', matches: ['Politics', 'Civic Tech', 'Policy'] },
  { id: 'government', label: 'Government', matches: ['Government', 'MarylandGov'] },
  { id: 'culture', label: 'Culture', matches: ['Culture', 'Community', 'Community Organizing', 'Code Collective', 'Partners'] },
  { id: 'faith', label: 'Faith', matches: ['Faith', 'Religion', 'Spirituality'] },
  { id: 'environment', label: 'Environment', matches: ['Environment', 'Water', 'Climate', 'Energy', 'Infrastructure', 'Safety', 'Stability'] },
  { id: 'makerspace', label: 'Makerspace', matches: ['Makerspace', 'Robotics'] },
  { id: 'other', label: 'Other', matches: [] },
];

/** Category-map order, used for `sectors[]` and `primarySector`. */
export const MAP_ORDER: SectorId[] = SECTORS.map((s) => s.id);

/**
 * Rail order, mission first rather than by volume. Technology is 4% of the
 * listings but it is why someone opens a calendar branded for technologists.
 */
export const RAIL_ORDER: SectorId[] = [
  'technology', 'entrepreneurship', 'makerspace', 'education', 'economics',
  'finance', 'health', 'environment', 'culture', 'government', 'politics',
  'faith', 'other',
];

export const SECTOR_LABEL: Record<SectorId, string> = Object.fromEntries(
  SECTORS.map((s) => [s.id, s.label]),
) as Record<SectorId, string>;

const rank = new Map(MAP_ORDER.map((id, i) => [id, i]));

/** Sort a set of sector ids into category-map order. */
export function inMapOrder(ids: Iterable<SectorId>): SectorId[] {
  return [...new Set(ids)].sort((a, b) => (rank.get(a) ?? 99) - (rank.get(b) ?? 99));
}

/**
 * Slugify a tag the way the current site does, so the vendored `matches`
 * keep matching: lowercase, & to and, non-alphanumerics to dashes, trim.
 */
export function slugifyTag(tag: string): string {
  return String(tag)
    .toLowerCase()
    .replace(/&/g, 'and')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

const MATCH_INDEX: Array<{ id: SectorId; slugs: Set<string> }> = SECTORS.map((s) => ({
  id: s.id,
  slugs: new Set(s.matches.map(slugifyTag)),
}));

/** Every sector a tag list maps to, in category-map order. `other` when none. */
export function sectorsForTags(tags: readonly string[]): SectorId[] {
  const slugs = tags.map(slugifyTag);
  const hit: SectorId[] = [];
  for (const entry of MATCH_INDEX) {
    if (entry.slugs.size === 0) continue;
    if (slugs.some((s) => entry.slugs.has(s))) hit.push(entry.id);
  }
  return hit.length > 0 ? hit : ['other'];
}

export function isSectorId(v: unknown): v is SectorId {
  return typeof v === 'string' && rank.has(v as SectorId);
}

/** CSS custom-property references, so both themes resolve automatically. */
export function sectorColor(id: SectorId): string {
  return `var(--sector-${id})`;
}
export function sectorTint(id: SectorId): string {
  return `var(--sector-${id}-tint)`;
}
