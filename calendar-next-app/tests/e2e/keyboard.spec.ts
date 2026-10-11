import { expect, test, type Page } from '@playwright/test';

/**
 * The list is the accessible equivalent of the map, so everything has to be
 * reachable and operable from the keyboard alone.
 */
async function ready(page: Page) {
  await expect(page.locator('[data-day]').first()).toBeVisible({ timeout: 45_000 });
}

test.describe('keyboard', () => {
  test('the tide line is a roving-tabindex toolbar with arrow keys', async ({ page }) => {
    await page.goto('/?city=baltimore&map=0');
    await ready(page);

    const toolbar = page.getByRole('toolbar', { name: 'Choose a day' });
    await expect(toolbar).toBeVisible();

    // Exactly one day is tabbable at a time.
    const tabbable = toolbar.locator('button[tabindex="0"]');
    await expect(tabbable).toHaveCount(1);

    // The days carry no aria-label on purpose: WCAG 2.5.3 wants the
    // accessible name to contain the visible text, so the name is composed
    // from the weekday, the numeral and a visually hidden count.
    const focusedDay = () =>
      page.evaluate(() => document.activeElement?.getAttribute('data-tide-day'));

    await tabbable.focus();
    const first = await focusedDay();
    expect(first).not.toBeNull();

    await page.keyboard.press('ArrowRight');
    expect(await focusedDay()).not.toBe(first);

    await page.keyboard.press('Home');
    expect(await focusedDay()).toBe(first);

    await page.keyboard.press('End');
    expect(await focusedDay()).not.toBe(first);

    // The name a screen reader hears still carries the weekday and the count.
    const name = await page.evaluate(() => document.activeElement?.textContent ?? '');
    expect(name).toMatch(/\d/);
    expect(name).toMatch(/event/);
  });

  test('every event row is a real link with a visible focus ring', async ({ page }) => {
    await page.goto('/?city=baltimore&map=0');
    await ready(page);

    const row = page.locator('[data-event-key]').first();
    await expect(row).toHaveAttribute('href', /\?event=/);
    await row.focus();

    const outline = await row.evaluate((el) => {
      const cs = getComputedStyle(el);
      return { width: cs.outlineWidth, style: cs.outlineStyle };
    });
    expect(outline.style).not.toBe('none');
    expect(Number.parseFloat(outline.width)).toBeGreaterThanOrEqual(2);
  });

  test('a focused row is never hidden under the sticky chrome', async ({ page }) => {
    await page.goto('/?city=baltimore&map=0');
    await ready(page);

    // Walk a long way down the list by keyboard alone.
    const row = page.locator('[data-event-key]').nth(12);
    await row.scrollIntoViewIfNeeded();
    await row.focus();

    const clear = await page.evaluate(() => {
      const el = document.activeElement as HTMLElement | null;
      if (!el) return false;
      const chrome = Number.parseInt(
        getComputedStyle(document.documentElement).getPropertyValue('--chrome-h'),
        10,
      );
      return el.getBoundingClientRect().top >= (Number.isFinite(chrome) ? chrome : 0) - 1;
    });
    expect(clear).toBe(true);
  });

  test('the detail sheet opens, closes on Escape and returns focus', async ({ page }) => {
    await page.goto('/?city=baltimore&map=0');
    await ready(page);

    const row = page.locator('[data-event-key]').first();
    const key = await row.getAttribute('data-event-key');
    await row.click();

    await expect(page.getByRole('dialog')).toBeVisible();
    expect(new URL(page.url()).searchParams.get('event')).toBe(key);

    await page.keyboard.press('Escape');
    await expect(page.getByRole('dialog')).toBeHidden();
    expect(new URL(page.url()).searchParams.get('event')).toBeNull();

    const focusedKey = await page.evaluate(() =>
      document.activeElement?.getAttribute('data-event-key'),
    );
    expect(focusedKey).toBe(key);
  });

  test('the back button closes the sheet', async ({ page }) => {
    await page.goto('/?city=baltimore&map=0');
    await ready(page);
    await page.locator('[data-event-key]').first().click();
    await expect(page.getByRole('dialog')).toBeVisible();

    await page.goBack();
    await expect(page.getByRole('dialog')).toBeHidden();
  });

  test('slash focuses the search field, but not while typing', async ({ page }) => {
    await page.goto('/?city=baltimore&map=0');
    await ready(page);

    await page.keyboard.press('/');
    // On a phone the shortcut opens the full-screen sheet, which is a lazy
    // chunk, so the field arrives a tick later.
    await expect
      .poll(() => page.evaluate(() => document.activeElement?.getAttribute('type')), {
        timeout: 10_000,
      })
      .toBe('search');

    // Typing a slash inside the field must insert it, not re-trigger.
    await page.keyboard.type('a/b');
    const value = await page.evaluate(() => (document.activeElement as HTMLInputElement)?.value);
    expect(value).toBe('a/b');
  });

  test('the month grid is arrow-navigable', async ({ page }) => {
    await page.goto('/?city=baltimore&map=0&view=month');
    const grid = page.getByRole('grid');
    await expect(grid).toBeVisible({ timeout: 45_000 });

    const cell = grid.locator('[role="gridcell"][tabindex="0"]');
    await expect(cell).toHaveCount(1);
    await cell.focus();

    // The grid moves focus inside a requestAnimationFrame, so poll rather
    // than reading straight after the keypress.
    const focused = () =>
      page.evaluate(() => document.activeElement?.getAttribute('data-cell'));

    const before = await focused();
    await page.keyboard.press('ArrowRight');
    await expect.poll(focused).not.toBe(before);

    const after = await focused();
    await page.keyboard.press('ArrowDown');
    await expect.poll(focused).not.toBe(after);
  });

  test('filter chips expose their pressed state', async ({ page }) => {
    await page.goto('/?city=baltimore&map=0');
    await ready(page);

    const all = page.getByRole('button', { name: 'All', exact: true });
    await expect(all).toHaveAttribute('aria-pressed', 'true');

    const tech = page.locator('.rail-item', { hasText: 'Technology' }).first();
    await tech.click();
    await expect(tech).toHaveAttribute('aria-pressed', 'true');
    await expect(all).toHaveAttribute('aria-pressed', 'false');
  });
});

test.describe('URL contract', () => {
  test('the old long link still loads with All active', async ({ page }) => {
    const legacy =
      '/?city=baltimore&lm=community_sectors&lt=technology.education.entrepreneurship.economics.finance.health.politics.government.culture.faith.environment.makerspace.other&lx=0&lh=1&lc=1&li=1&ls=0&lw=0&la=open_page';
    const errors: string[] = [];
    page.on('pageerror', (e) => errors.push(String(e)));

    await page.goto(legacy);
    await ready(page);

    await expect(page.getByRole('button', { name: 'All', exact: true })).toHaveAttribute(
      'aria-pressed',
      'true',
    );

    // The unhandled display parameters survive the round trip.
    const params = new URL(page.url()).searchParams;
    for (const key of ['lx', 'lh', 'lc', 'li', 'ls', 'la']) {
      expect(params.has(key), `${key} preserved`).toBe(true);
    }
    expect(errors).toEqual([]);
  });

  test('map=1 shows the map and map=0 hides it', async ({ page }) => {
    // The contract spells these 1 and 0, not "true" and "false". The map lives
    // in the context rail, which needs 1280 or more.
    await page.setViewportSize({ width: 1400, height: 900 });
    await page.goto('/?city=baltimore&map=1');
    await expect(page.getByRole('complementary', { name: 'Event context' })).toBeVisible({
      timeout: 60_000,
    });
    await expect(page.locator('canvas.maplibregl-canvas')).toBeVisible({ timeout: 60_000 });

    await page.goto('/?city=baltimore&map=0');
    await ready(page);
    // The rail stays, because "Where it's happening" still belongs there.
    await expect(page.getByRole('complementary', { name: 'Event context' })).toBeVisible();
    await expect(page.locator('canvas.maplibregl-canvas')).toHaveCount(0);
  });

  test('lw=1 hides weekday daytime events', async ({ page }) => {
    // Read the live region, not the rendered rows: only three day sections
    // render at first paint, and which three they are changes with the filter,
    // so the row count can go up while the result set shrinks.
    const total = async () => {
      const text = (await page.locator('[role="status"]').first().textContent()) ?? '';
      return Number.parseInt(text.replace(/[^0-9]/g, ''), 10);
    };

    await page.goto('/?city=baltimore&map=0&lw=0');
    await ready(page);
    const before = await total();

    await page.goto('/?city=baltimore&map=0&lw=1');
    await ready(page);
    const after = await total();

    // The filter has to actually remove something, and the chip has to show.
    expect(after).toBeLessThan(before);
    await expect(page.getByRole('button', { name: /Filters/ })).toContainText('1');
  });

  test('a sector choice is written to the URL and survives a reload', async ({ page }) => {
    await page.goto('/?city=baltimore&map=0');
    await ready(page);

    await page.locator('.rail-item', { hasText: 'Technology' }).first().click();
    await expect.poll(() => new URL(page.url()).searchParams.get('lt')).toBe('technology');

    await page.reload();
    await ready(page);
    await expect(page.locator('.rail-item', { hasText: 'Technology' }).first()).toHaveAttribute(
      'aria-pressed',
      'true',
    );
  });
});
