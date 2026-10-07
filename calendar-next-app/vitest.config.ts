import { defineConfig } from 'vitest/config';

// Kept separate from vite.config.ts: Vite 8's UserConfig no longer carries a
// `test` key, so the test runner owns its own config file.
export default defineConfig({
  test: {
    environment: 'node',
    include: ['src/**/*.test.ts'],
  },
});
