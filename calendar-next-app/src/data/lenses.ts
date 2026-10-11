import communitySectors from './lenses/community_sectors.json';
import maslowNeeds from './lenses/maslow_needs.json';
import techOnly from './lenses/tech_only.json';
import { slugifyTag } from './sectors';
import type { LensId } from './types';

/**
 * The two non-default lenses stay data-driven: they re-group the same events
 * under different headings, so the rail shows colored dots rather than the
 * sector icon set.
 */
type RawLens = {
  id: string;
  label: string;
  categories: Array<{ label: string; color: string; text_color: string; matches: string[] }>;
};

export type LensCategory = {
  /** Slug of the label, used in the URL. */
  id: string;
  label: string;
  color: string;
  slugs: Set<string>;
};

export type Lens = {
  id: LensId;
  label: string;
  categories: LensCategory[];
};

function toLens(raw: RawLens): Lens {
  return {
    id: raw.id as LensId,
    label: raw.label,
    categories: raw.categories.map((c) => ({
      id: slugifyTag(c.label),
      label: c.label,
      color: c.color,
      slugs: new Set(c.matches.map(slugifyTag)),
    })),
  };
}

export const LENSES: Record<LensId, Lens> = {
  community_sectors: toLens(communitySectors as RawLens),
  maslow_needs: toLens(maslowNeeds as RawLens),
  tech_only: toLens(techOnly as RawLens),
};

export const LENS_LABEL: Record<LensId, string> = {
  community_sectors: 'Community sectors',
  maslow_needs: 'Maslow needs',
  tech_only: 'Tech meetups',
};

export function isLensId(v: unknown): v is LensId {
  return v === 'community_sectors' || v === 'maslow_needs' || v === 'tech_only';
}

/** Which categories of a non-default lens a tag list falls into. */
export function lensCategoriesForTags(lens: Lens, tags: readonly string[]): string[] {
  const slugs = tags.map(slugifyTag);
  const hit = lens.categories
    .filter((c) => c.slugs.size > 0 && slugs.some((s) => c.slugs.has(s)))
    .map((c) => c.id);
  if (hit.length > 0) return hit;
  const fallback = lens.categories.find((c) => c.slugs.size === 0);
  return fallback ? [fallback.id] : [];
}
