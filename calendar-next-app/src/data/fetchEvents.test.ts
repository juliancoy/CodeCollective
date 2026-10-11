import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

/**
 * The data path has three sources and has to be honest about which one it
 * used. This matters beyond offline handling: the hosted preview runs in a
 * sandboxed frame that cannot always reach codecollective.us, and handing
 * someone an error state when a saved copy is sitting right there is a poor
 * way to show them a redesign.
 */
const LIVE = 'https://codecollective.us/baltimore/upcoming_events.json';

type Row = { name: string };

function jsonResponse(body: unknown, ok = true, status = 200) {
  return {
    ok,
    status,
    json: async () => body,
  } as unknown as Response;
}

/** Load a fresh copy of the module with a given env, so its caches are clean. */
async function loadModule(env: Record<string, string>) {
  vi.resetModules();
  for (const [k, v] of Object.entries(env)) vi.stubEnv(k, v);
  return import('./fetchEvents');
}

const liveRows: Row[] = [{ name: 'from the live feed' }];
const snapshotRows: Row[] = [{ name: 'from the snapshot' }];

beforeEach(() => {
  const store = new Map<string, string>();
  vi.stubGlobal('sessionStorage', {
    getItem: (k: string) => store.get(k) ?? null,
    setItem: (k: string, v: string) => void store.set(k, v),
    removeItem: (k: string) => void store.delete(k),
    clear: () => store.clear(),
  });
});

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('source selection', () => {
  it('uses the live feed when it answers', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) =>
        url === LIVE ? jsonResponse(liveRows) : jsonResponse(snapshotRows),
      ),
    );
    const { eventsPromise } = await loadModule({ VITE_SNAPSHOT_FALLBACK: '1' });
    const result = await eventsPromise('baltimore');
    expect(result.source).toBe('live');
    expect(result.rows).toEqual(liveRows);
    expect(result.snapshotDate).toBeNull();
  });

  it('never touches the network in an explicit snapshot build', async () => {
    const fetchSpy = vi.fn(async (_url: string) => jsonResponse(snapshotRows));
    vi.stubGlobal('fetch', fetchSpy);
    const { eventsPromise } = await loadModule({ VITE_DATA_SOURCE: 'snapshot' });
    const result = await eventsPromise('baltimore');
    expect(result.source).toBe('snapshot');
    const urls = fetchSpy.mock.calls.map((call) => String(call[0]));
    expect(urls.some((u) => u.startsWith('http'))).toBe(false);
  });

  it('prefers this browser’s own copy over a bundled one', async () => {
    // Warm the session cache from a successful live load.
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse(liveRows)));
    const first = await loadModule({ VITE_SNAPSHOT_FALLBACK: '1' });
    await first.eventsPromise('baltimore');

    // Now the live feed is gone, but the session copy survives.
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        if (url === LIVE) throw new TypeError('Failed to fetch');
        return jsonResponse(snapshotRows);
      }),
    );
    const second = await loadModule({ VITE_SNAPSHOT_FALLBACK: '1' });
    const result = await second.eventsPromise('baltimore');
    expect(result.source).toBe('session');
    expect(result.rows).toEqual(liveRows);
  });

  it('falls back to the bundled snapshot when the live origin is unreachable', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        if (url === LIVE) throw new TypeError('Failed to fetch');
        return jsonResponse(snapshotRows);
      }),
    );
    const { eventsPromise } = await loadModule({
      VITE_SNAPSHOT_FALLBACK: '1',
      VITE_SNAPSHOT_DATE: '25 September 2026',
    });
    const result = await eventsPromise('baltimore');
    expect(result.source).toBe('snapshot');
    expect(result.rows).toEqual(snapshotRows);
    expect(result.snapshotDate).toBe('25 September 2026');
  });

  it('still shows the error state when the fallback is off', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        if (url === LIVE) throw new TypeError('Failed to fetch');
        return jsonResponse(snapshotRows);
      }),
    );
    const { eventsPromise } = await loadModule({});
    await expect(eventsPromise('baltimore')).rejects.toThrow();
  });

  it('surfaces the original failure when even the fallback is missing', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => {
        throw new TypeError('Failed to fetch');
      }),
    );
    const { eventsPromise } = await loadModule({ VITE_SNAPSHOT_FALLBACK: '1' });
    await expect(eventsPromise('baltimore')).rejects.toThrow(/Failed to fetch/);
  });

  it('rejects a feed that is not a JSON array', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse({ events: [] })));
    const { eventsPromise } = await loadModule({});
    await expect(eventsPromise('baltimore')).rejects.toThrow(/not a JSON array/);
  });

  it('treats a non-200 as a failure', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse(null, false, 503)));
    const { eventsPromise } = await loadModule({});
    await expect(eventsPromise('baltimore')).rejects.toThrow(/503/);
  });
});

describe('caching', () => {
  it('reuses one promise per city and starts fresh after invalidation', async () => {
    const fetchSpy = vi.fn(async () => jsonResponse(liveRows));
    vi.stubGlobal('fetch', fetchSpy);
    const { eventsPromise, invalidateEvents } = await loadModule({});

    await Promise.all([eventsPromise('baltimore'), eventsPromise('baltimore')]);
    expect(fetchSpy).toHaveBeenCalledTimes(1);

    invalidateEvents('baltimore');
    await eventsPromise('baltimore');
    expect(fetchSpy).toHaveBeenCalledTimes(2);
  });

  it('keeps cities apart', async () => {
    const fetchSpy = vi.fn(async () => jsonResponse(liveRows));
    vi.stubGlobal('fetch', fetchSpy);
    const { eventsPromise } = await loadModule({});
    await eventsPromise('baltimore');
    await eventsPromise('dc');
    expect(fetchSpy).toHaveBeenCalledTimes(2);
  });
});
