import { expect, test } from '@playwright/test';

test('sticky header remains stable across the former collapse boundary', async ({ page }) => {
  await page.goto('/?city=baltimore&map=0');
  await expect(page.locator('[data-day]').first()).toBeVisible();
  const band = page.locator('[data-calendar-band]');
  const initial = await band.boundingBox();
  expect(initial).not.toBeNull();
  // Track DOM identity as well as geometry: moving the search pill between
  // conditional branches used to remount its controls on every collapse.
  await band.evaluate(el => { (window as unknown as { originalBand: Element }).originalBand = el; });
  for (const y of [100, 119, 121, 140, 121, 119, 600, 120, 0]) {
    await page.evaluate(scroll => window.scrollTo({ top: scroll, behavior: 'instant' }), y);
    await page.waitForTimeout(80);
    const box = await band.boundingBox();
    expect(box!.y).toBeCloseTo(0, 0);
    expect(box!.height).toBeCloseTo(initial!.height, 0);
    expect(await band.evaluate(el => el === (window as unknown as { originalBand: Element }).originalBand)).toBe(true);
  }
  await page.evaluate(() => window.scrollTo({ top: 600, behavior: 'instant' }));
  await page.waitForTimeout(100);
  const header = (await band.boundingBox())!;
  const controls = (await page.locator('[data-calendar-controls]').boundingBox())!;
  expect(controls.y).toBeCloseTo(header.y + header.height, 0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: `/tmp/calendar-next-header-${test.info().project.name}.png` });
});
