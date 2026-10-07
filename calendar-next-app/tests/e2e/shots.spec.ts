import { expect, test, type Page } from '@playwright/test';

/**
 * Verification screenshots at the three widths the v2 brief asks for, in both
 * themes, plus the states that only exist after an interaction. Run with:
 *   npx playwright test --project=desktop tests/e2e/shots.spec.ts
 */
const WIDTHS = [390, 1280, 1440];

async function ready(page: Page) {
  await expect(page.locator('[data-day]').first()).toBeVisible({ timeout: 60_000 });
  await page.waitForTimeout(2500);
}

async function setTheme(page: Page, theme: 'light' | 'dark') {
  await page.evaluate((t) => {
    document.documentElement.dataset['theme'] = t;
  }, theme);
  await page.waitForTimeout(400);
}

for (const width of WIDTHS) {
  for (const theme of ['light', 'dark'] as const) {
    test(`agenda ${width} ${theme}`, async ({ page }) => {
      await page.setViewportSize({ width, height: width < 768 ? 844 : 900 });
      await page.goto('/?city=baltimore');
      await ready(page);
      await setTheme(page, theme);
      if (width >= 1280) {
        await page.locator('canvas.maplibregl-canvas').waitFor({ timeout: 45_000 }).catch(() => {});
        await page.waitForTimeout(5000);
      }
      await page.screenshot({ path: `shots/v2-agenda-${width}-${theme}.png` });
    });
  }
}

test('condensed band after scrolling', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/?city=baltimore');
  await ready(page);
  await page.mouse.wheel(0, 600);
  await page.waitForTimeout(900);
  await page.screenshot({ path: 'shots/v2-condensed-1440.png' });
});

test('sector selected, tide bars recoloured', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/?city=baltimore');
  await ready(page);
  await page.locator('.rail-item', { hasText: 'Health' }).first().click();
  await page.waitForTimeout(1200);
  await page.screenshot({ path: 'shots/v2-sector-health-1440.png' });
});

test('month view', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto('/?city=baltimore&view=month');
  await expect(page.getByRole('grid')).toBeVisible({ timeout: 60_000 });
  await page.waitForTimeout(1200);
  await page.screenshot({ path: 'shots/v2-month-1280.png' });
});

test('event sheet', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/?city=baltimore');
  await ready(page);
  await page.locator('[data-event-key]').first().click();
  await expect(page.getByRole('dialog')).toBeVisible({ timeout: 60_000 });
  await page.waitForTimeout(1500);
  await page.screenshot({ path: 'shots/v2-event-sheet-1440.png' });
});

test('filters sheet', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto('/?city=baltimore');
  await ready(page);
  await page.getByRole('button', { name: 'Filters' }).click();
  await expect(page.getByRole('dialog')).toBeVisible({ timeout: 60_000 });
  await page.waitForTimeout(800);
  await page.screenshot({ path: 'shots/v2-filters-1280.png' });
});

test('phone search sheet', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/?city=baltimore');
  await ready(page);
  await page.getByRole('button', { name: /Search Baltimore events/ }).click();
  await expect(page.getByRole('dialog')).toBeVisible({ timeout: 60_000 });
  await page.waitForTimeout(800);
  await page.screenshot({ path: 'shots/v2-phone-search-390.png' });
});

test('empty state with relaxations', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto('/?city=baltimore&lt=finance&when=today&q=zzzzqqq');
  await expect(page.getByText(/No events match/)).toBeVisible({ timeout: 60_000 });
  await page.waitForTimeout(600);
  await page.screenshot({ path: 'shots/v2-empty-1280.png' });
});

test('map unavailable collapses to a note', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  // Exactly what a sandboxed frame does to the tile host.
  await page.route('https://tiles.openfreemap.org/**', (r) => r.abort('failed'));
  await page.goto('/?city=baltimore');
  await ready(page);
  await expect(page.getByText(/Map unavailable here/)).toBeVisible({ timeout: 45_000 });
  await page.screenshot({ path: 'shots/v2-map-unavailable-1440.png' });
});
