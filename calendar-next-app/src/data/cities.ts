import type { CityId } from './types';

export type City = {
  id: CityId;
  label: string;
  /** IANA zone, or null to mean "use the viewer's own zone". */
  tz: string | null;
  /** Human name of the zone, for the meta line. */
  tzLabel: string;
  /** Map centre, used to exclude far-flung outliers from fitBounds. */
  center: { lat: number; lng: number };
};

export const CITIES: City[] = [
  { id: 'baltimore', label: 'Baltimore', tz: 'America/New_York', tzLabel: 'Eastern Time', center: { lat: 39.2904, lng: -76.6122 } },
  { id: 'dc', label: 'Washington DC', tz: 'America/New_York', tzLabel: 'Eastern Time', center: { lat: 38.9072, lng: -77.0369 } },
  { id: 'philadelphia', label: 'Philadelphia', tz: 'America/New_York', tzLabel: 'Eastern Time', center: { lat: 39.9526, lng: -75.1652 } },
  { id: 'pittsburgh', label: 'Pittsburgh', tz: 'America/New_York', tzLabel: 'Eastern Time', center: { lat: 40.4406, lng: -79.9959 } },
  { id: 'westvirginia', label: 'West Virginia', tz: 'America/New_York', tzLabel: 'Eastern Time', center: { lat: 38.3498, lng: -81.6326 } },
  { id: 'hawaii', label: 'Hawaii', tz: 'Pacific/Honolulu', tzLabel: 'Hawaii Time', center: { lat: 21.3069, lng: -157.8583 } },
  { id: 'virtual', label: 'Virtual', tz: null, tzLabel: 'your time', center: { lat: 39.2904, lng: -76.6122 } },
];

const byId = new Map(CITIES.map((c) => [c.id, c]));

export const DEFAULT_CITY: CityId = 'baltimore';

export function getCity(id: string | null | undefined): City {
  return byId.get((id ?? DEFAULT_CITY) as CityId) ?? byId.get(DEFAULT_CITY)!;
}

export function isCityId(v: unknown): v is CityId {
  return typeof v === 'string' && byId.has(v as CityId);
}

/** The zone to render an event in: the city's, or the viewer's for `virtual`. */
export function cityZone(city: City): string {
  return city.tz ?? Intl.DateTimeFormat().resolvedOptions().timeZone;
}
