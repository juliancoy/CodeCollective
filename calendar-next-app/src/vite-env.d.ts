/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** live (default) reads the public feed; snapshot reads the bundled copy. */
  readonly VITE_DATA_SOURCE?: 'live' | 'snapshot';
  /** "1" adds the concept banner to the hosted preview build only. */
  readonly VITE_DEMO_NOTE?: string;
  /** "1" falls back to the bundled snapshot when the live feed is unreachable. */
  readonly VITE_SNAPSHOT_FALLBACK?: string;
  /** Human-readable date the bundled snapshot was taken, for the banner. */
  readonly VITE_SNAPSHOT_DATE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
