import { expect, test } from '@playwright/test';

/** Every cell's load bar is the last child of the cell. */
const BARS = '[role="gridcell"] span[class*="mt-auto"]';

function barColours(page: import('@playwright/test').Page) {
  return page.evaluate(
    (sel) => [...document.querySelectorAll(sel)].map((el) => getComputedStyle(el).backgroundColor),
    BARS,
  );
}

test.describe('the month grid', () => {
  test('answers the sector rail, the way the tide line does', async ({ page }) => {
    // The grid shipped without this: the tide line took the selected sector
    // and the month view did not, so the two views disagreed about colour
    // while showing the same filtered events. It cannot be caught by looking
    // at one view — only by comparing them under the same filter.
    await page.goto('/?city=baltimore&view=month');
    await expect(page.locator('[role="gridcell"]').first()).toBeVisible({ timeout: 60_000 });

    const unfiltered = await barColours(page);
    expect(unfiltered.length, 'the grid should draw load bars').toBeGreaterThan(3);
    expect(
      new Set(unfiltered).size,
      'with no sector selected each day shows its own busiest sector',
    ).toBeGreaterThan(1);

    // `lt` is the sector parameter the current site already uses.
    await page.goto('/?city=baltimore&view=month&lt=health');
    await expect(page.locator('[role="gridcell"]').first()).toBeVisible({ timeout: 60_000 });

    const filtered = await barColours(page);
    expect(filtered.length, 'Health runs events every week').toBeGreaterThan(3);
    expect([...new Set(filtered)], 'one sector selected, one colour across the grid').toHaveLength(
      1,
    );
  });

  test('names real events rather than the feed’s broken titles', async ({ page }) => {
    await page.goto('/?city=baltimore&view=month');
    await expect(page.locator('[role="gridcell"]').first()).toBeVisible({ timeout: 60_000 });

    const grid = page.getByRole('grid');
    // These are verbatim titles in the live feed. Ranking them last is the
    // only thing keeping them out of the grid, so assert on the real strings.
    await expect(grid).not.toContainText('Start Date and Time');
    await expect(grid).not.toContainText('There were no events found');
    await expect(grid, 'a raw ISO stamp used as a title').not.toContainText(/\d{4}-\d{2}-\d{2}T/);
  });

  test('drops the event names on a phone instead of truncating them to nothing', async ({
    page,
  }, testInfo) => {
    test.skip(testInfo.project.name !== 'phone', 'about the phone layout');

    await page.goto('/?city=baltimore&view=month');
    await expect(page.locator('[role="gridcell"]').first()).toBeVisible({ timeout: 60_000 });

    // A 48px cell cannot hold a title. The numeral, the count and the bar can.
    const cell = page.locator('[role="gridcell"][data-count]').filter({ hasNotText: 'x' }).first();
    const box = await cell.boundingBox();
    expect(box!.width, 'phone cells really are this narrow').toBeLessThan(60);
    await expect(page.locator(BARS).first()).toBeVisible();
  });
});
