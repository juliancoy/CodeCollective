import { expect, test } from '@playwright/test';

/**
 * The map has a failure mode that looks like success: MapLibre resolves its
 * worker at runtime with `new URL('./maplibre-gl-worker.mjs', import.meta.url)`,
 * which no bundler can see. The file is never emitted, the worker 404s, and the
 * canvas still mounts — so asserting the canvas is visible proves nothing.
 * These tests assert the worker actually loaded and tiles were actually
 * fetched.
 */
test('the map worker loads and tiles are fetched', async ({ page }) => {
  const errors: string[] = [];
  page.on('console', (m) => {
    if (m.type() === 'error') errors.push(m.text());
  });
  page.on('pageerror', (e) => errors.push(String(e)));

  const failed: string[] = [];
  page.on('requestfailed', (r) => {
    const url = r.url();
    // Third-party organizer logos fail for their own reasons; only our own
    // assets matter here.
    if (url.startsWith(page.url().split('?')[0] ?? '') || url.includes('/assets/')) {
      failed.push(`${url} :: ${r.failure()?.errorText}`);
    }
  });

  // Desktop puts the map in the context rail, phones swap it for the list.
  // Either way `map=1` has to produce a canvas.
  await page.goto('/?city=baltimore&map=1');
  await expect(page.locator('canvas.maplibregl-canvas')).toBeVisible({ timeout: 60_000 });

  // Give the worker time to spin up and request its first tiles.
  await expect
    .poll(
      () =>
        page.evaluate(
          () =>
            performance
              .getEntriesByType('resource')
              .filter((r) => r.name.includes('maplibre-gl-worker')).length,
        ),
      { timeout: 20_000, message: 'the bundled worker chunk was never requested' },
    )
    .toBeGreaterThan(0);

  await expect
    .poll(
      () =>
        page.evaluate(
          () =>
            performance
              .getEntriesByType('resource')
              .filter((r) => r.name.includes('openfreemap')).length,
        ),
      { timeout: 30_000, message: 'no basemap tiles were requested' },
    )
    .toBeGreaterThan(0);

  expect(errors.filter((e) => /worker/i.test(e)), 'worker errors').toEqual([]);
  expect(failed, 'first-party asset requests that failed').toEqual([]);
});

test('the map note counts what cannot be placed', async ({ page }) => {
  // Desktop puts the map in the context rail, phones swap it for the list.
  // Either way `map=1` has to produce a canvas.
  await page.goto('/?city=baltimore&map=1');
  await expect(page.locator('canvas.maplibregl-canvas')).toBeVisible({ timeout: 60_000 });

  // 47% of the feed carries coordinates, so this is never zero in practice.
  const note = page.getByText(/Not on map: \d+ events without a mapped location/);
  await expect(note).toBeVisible({ timeout: 20_000 });
});

test('OpenStreetMap attribution stays visible', async ({ page }) => {
  // Desktop puts the map in the context rail, phones swap it for the list.
  // Either way `map=1` has to produce a canvas.
  await page.goto('/?city=baltimore&map=1');
  await expect(page.locator('canvas.maplibregl-canvas')).toBeVisible({ timeout: 60_000 });
  await expect(page.locator('.maplibregl-ctrl-attrib')).toContainText('OpenStreetMap');
});

test('a blocked tile host collapses the map card at once, not after the watchdog', async ({
  page,
}, testInfo) => {
  // The published preview runs in a sandbox that refuses every cross-origin
  // request, so this is the normal case there, not an edge case. A 12s
  // watchdog would still get there eventually, which is exactly why this
  // needs a test: the slow path and the fast path look identical at the end.
  test.skip(testInfo.project.name !== 'desktop', 'the context rail is a desktop arrangement');

  await page.route(/tiles\.openfreemap\.org/, (r) => r.abort());
  await page.goto('/?city=baltimore&map=1');

  const started = Date.now();
  await expect(page.getByText('Map unavailable here. Every event is in the list.')).toBeVisible({
    timeout: 10_000,
  });
  expect(Date.now() - started, 'the note should not wait out the style watchdog').toBeLessThan(
    10_000,
  );

  // The point of collapsing is that the agenda is unaffected.
  await expect(page.locator('[data-event-key]').first()).toBeVisible();
});
