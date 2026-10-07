/** The shape the public Code Collective JSON actually ships. */
export type RawLocation = {
  name?: string;
  address?: string;
  city?: string;
  state?: string;
  country?: string;
  postalCode?: string;
  latitude?: number;
  longitude?: number;
  geocode_status?: string;
  geocode_query?: string;
};

export type RawEvent = {
  id?: string;
  name: string;
  description: string;
  /** ISO 8601 with offset. Most rows carry +00:00, so always convert to the city zone. */
  startDate: string;
  endDate?: string;
  endTime?: string;
  url: string;
  status: 'ACTIVE' | 'CANCELLED' | string;
  location: RawLocation | string;
  /** Site-relative, e.g. /event_images/Name.webp */
  imageUrl?: string | null;
  orgImageUrl?: string | null;
  recurring?: boolean;
  recurrence?: unknown;
  scrapeTime: string;
  tags: string[];
  source: string;
  source_url: string;
  source_group: string;
  org_name: string;
  orgName: string;
  eventType?: string;
  icsUrl?: string;
};

export type SectorId =
  | 'technology'
  | 'education'
  | 'entrepreneurship'
  | 'economics'
  | 'finance'
  | 'health'
  | 'politics'
  | 'government'
  | 'culture'
  | 'faith'
  | 'environment'
  | 'makerspace'
  | 'other';

export type CalEvent = {
  key: string;
  title: string;
  descriptionMd: string;
  /** Plain text, 160 chars, for meta descriptions and accessible summaries. */
  excerpt: string;
  start: Date;
  end: Date | null;
  allDay: boolean;
  /** YYYY-MM-DD in the city's time zone. */
  dayKey: string;
  /** Last day the event spans, when it runs past its start day. */
  endDayKey: string | null;
  url: string;
  cancelled: boolean;
  recurring: boolean;
  venue: string | null;
  address: string | null;
  locality: string | null;
  /** The location names a screen rather than a place; excluded from the map. */
  online: boolean;
  coords: { lat: number; lng: number } | null;
  image: string | null;
  orgName: string;
  orgLogo: string | null;
  /** Two letters for the avatar, derived from the organizer or the venue. */
  initials: string;
  /** In category-map order. */
  sectors: SectorId[];
  primarySector: SectorId;
  tags: string[];
  sourceGroup: string;
  featured: boolean;
  scrapedAt: Date | null;
};

export type CityId =
  | 'baltimore'
  | 'dc'
  | 'pittsburgh'
  | 'philadelphia'
  | 'westvirginia'
  | 'hawaii'
  | 'virtual';

export type LensId = 'community_sectors' | 'maslow_needs' | 'tech_only';

export type TimeOfDay = 'morning' | 'afternoon' | 'evening' | 'late';

export type DatePreset = 'any' | 'today' | 'tomorrow' | 'weekend' | 'next7' | 'custom';
