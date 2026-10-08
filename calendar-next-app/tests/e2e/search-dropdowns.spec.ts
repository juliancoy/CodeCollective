import { expect, test, type Page } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

async function ready(page: Page) {
  await page.goto('/?city=baltimore&map=0');
  await expect(page.locator('[data-day]').first()).toBeVisible();
}

test('Where and When select independently after scrolling', async ({ page, isMobile }) => {
  await page.route('**/snapshot/dc.json', route => route.fulfill({
    contentType: 'application/json',
    body: readFileSync(resolve(import.meta.dirname, '../../public/snapshot/baltimore.json'), 'utf8'),
  }));
  await ready(page);
  await page.evaluate(() => window.scrollTo({ top: 600, behavior: 'instant' }));
  if (isMobile) await page.getByRole('button', { name: /Search Baltimore events/ }).click();
  else await page.getByRole('button', { name: /Where Baltimore/ }).click();
  await page.getByRole('button', { name: 'Washington DC', exact: true }).click();
  await expect.poll(() => new URL(page.url()).searchParams.get('city')).toBe('dc');
  if (!isMobile) {
    await expect(page.getByRole('dialog', { name: 'Choose a city' })).toBeHidden();
    await page.getByRole('button', { name: /When Any date/ }).click();
  }
  await page.getByRole('button', { name: 'Today', exact: true }).click();
  await expect.poll(() => new URL(page.url()).searchParams.get('when')).toBe('today');
  if (isMobile) await page.getByRole('button', { name: 'Close search' }).click();
  else {
    await expect(page.getByRole('dialog', { name: 'Choose when' })).toBeHidden();
    await expect(page.getByRole('button', { name: /When Today/ })).toBeFocused();
    await page.getByRole('button', { name: /Where Washington DC/ }).click();
    await page.keyboard.press('Escape');
    await expect(page.getByRole('button', { name: /Where Washington DC/ })).toBeFocused();
  }
});

test('custom dates remain editable and dropdowns fit a short viewport', async ({ page, isMobile }) => {
  await page.setViewportSize({ width: isMobile ? 390 : 1280, height: 500 });
  await ready(page);
  if (isMobile) await page.getByRole('button', { name: /Search Baltimore events/ }).click();
  else await page.getByRole('button', { name: /When Any date/ }).click();
  await page.getByRole('button', { name: 'Pick dates', exact: true }).click();
  await page.getByLabel('From', { exact: true }).fill('2026-10-12');
  await page.getByLabel('To', { exact: true }).fill('2026-10-16');
  await expect.poll(() => new URL(page.url()).searchParams.get('from')).toBe('2026-10-12');
  await expect.poll(() => new URL(page.url()).searchParams.get('to')).toBe('2026-10-16');
  const dialog = page.getByRole('dialog');
  const box = (await dialog.boundingBox())!;
  expect(box.y).toBeGreaterThanOrEqual(0);
  expect(box.y + box.height).toBeLessThanOrEqual(501);
  await page.keyboard.press('Escape');
  await expect(dialog).toBeHidden();
});

test('first click opens a lazily loaded dropdown and only one can stay open', async ({ page, isMobile }) => {
  test.skip(isMobile, 'Phones use the full-screen search sheet.');
  let release!: () => void;
  const gate = new Promise<void>(resolve => { release = resolve; });
  await page.route('**/PillSegments-*.js', async route => {
    await gate;
    await route.continue();
  });
  await ready(page);
  await page.getByRole('button', { name: /Where Baltimore/ }).click();
  release();
  await expect(page.getByRole('dialog', { name: 'Choose a city' })).toBeVisible();
  await page.getByRole('button', { name: /When Any date/ }).click();
  await expect(page.getByRole('dialog', { name: 'Choose when' })).toBeVisible();
  await expect(page.getByRole('dialog')).toHaveCount(1);
  await page.keyboard.press('Escape');
  await expect(page.getByRole('button', { name: /When Any date/ })).toBeFocused();
});
