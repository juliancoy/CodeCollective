import { MotionConfig } from 'motion/react';
import { NuqsAdapter } from 'nuqs/adapters/react';
import type { ReactNode } from 'react';
import { duration, ease } from '../motion/tokens';

/**
 * `reducedMotion="user"` makes every Motion animation respect the OS setting
 * without each component checking. The CSS side is handled in global.css.
 */
export function Providers({ children }: { children: ReactNode }) {
  return (
    <NuqsAdapter>
      <MotionConfig
        reducedMotion="user"
        transition={{ duration: duration.base, ease: ease.out }}
      >
        {children}
      </MotionConfig>
    </NuqsAdapter>
  );
}
