import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

// `base` comes from the environment so the same build can mount at the domain
// root, at /calendar-next/, or on a static host that needs relative URLs.
export default defineConfig({
  base: process.env.VITE_BASE ?? '/calendar-next/',
  // MapLibre ships its own web worker. Pre-bundling it in dev rewrites the
  // worker URL and the map fails to start, so it is left alone.
  optimizeDeps: { exclude: ['maplibre-gl'] },
  plugins: [react(), tailwindcss()],
  // MapLibre's worker is an ES module and imports a sibling chunk.
  worker: { format: 'es' },
  build: {
    target: 'es2022',
    // maplibre is dynamically imported; keep it in its own chunk so the
    // initial payload stays under the 170 KB budget.
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('maplibre-gl')) return 'maplibre';
          return undefined;
        },
      },
    },
  },
});
