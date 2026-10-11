import type { DatePreset } from '../../data/types';

export const WHEN_OPTIONS: ReadonlyArray<{ id: DatePreset; label: string }> = [
  { id: 'any', label: 'Any date' },
  { id: 'today', label: 'Today' },
  { id: 'tomorrow', label: 'Tomorrow' },
  { id: 'weekend', label: 'This weekend' },
  { id: 'next7', label: 'Next 7 days' },
  { id: 'custom', label: 'Pick dates' },
];

export const segmentClass = 'flex min-w-0 flex-col justify-center px-4 py-2 text-left';

export function whenLabel(preset: DatePreset, from: string | null, to: string | null): string {
  if (preset === 'custom') {
    if (from && to) return `${from} to ${to}`;
    if (from) return `From ${from}`;
    if (to) return `Until ${to}`;
    return 'Pick dates';
  }
  return WHEN_OPTIONS.find((o) => o.id === preset)?.label ?? 'Any date';
}
