import {
  CircleDashed,
  Coins,
  Cpu,
  GraduationCap,
  HeartPulse,
  Landmark,
  LayoutGrid,
  Leaf,
  Megaphone,
  Palette,
  Rocket,
  Sun,
  TrendingUp,
  Wrench,
} from 'lucide-react';
import type { SectorId } from '../data/types';

/**
 * Crisp line icons, stroke 1.5. Faith deliberately uses a neutral mark: the
 * data covers mosques, churches and temples, so no symbol tied to one religion.
 */
const ICONS: Record<SectorId | 'all', typeof Cpu> = {
  all: LayoutGrid,
  technology: Cpu,
  entrepreneurship: Rocket,
  makerspace: Wrench,
  education: GraduationCap,
  economics: TrendingUp,
  finance: Coins,
  health: HeartPulse,
  environment: Leaf,
  culture: Palette,
  government: Landmark,
  politics: Megaphone,
  faith: Sun,
  other: CircleDashed,
};

export function SectorIcon({
  sector,
  size = 20,
  className,
}: {
  sector: SectorId | 'all';
  size?: number;
  className?: string;
}) {
  const Icon = ICONS[sector] ?? CircleDashed;
  return <Icon size={size} strokeWidth={1.5} aria-hidden className={className} />;
}
