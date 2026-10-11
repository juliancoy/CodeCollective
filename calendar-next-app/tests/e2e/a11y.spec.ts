import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';

/**
 * Zero serious or critical axe violations across the agenda, the month grid,
 * the open detail sheet, the open filters sheet and the map, in both themes.
 *
 * Two things keep this affordable.
 *
 * `content-visibility: auto` on the day sections is a real rendering win worth
 * keeping, but axe queries geometry for every element and each query forces
 * layout on a skipped subtree. Measured on this suite, one scan took 201s with
 * it and 70s without. It is neutralised for the scan only, which changes no
 * markup, no roles and no colours.
 *
 * And each scan is scoped to the surface under test. The agenda scan already
 * covers the chrome and the rows; re-walking all of it behind an open sheet
 * adds no signal and costs minutes, because colour-contrast has to resolve a
 * background for every text node.
 */
const SERIOUS = new Set(['serious', 'critical']);

type ScanOptions = {
  /** Restrict the scan to this selector. Defaults to the whole document. */
  include?: string;
  /** Cap how many of the repeated day sections are walked. */
  maxDays?: number;
};

async function scan(page: Page, label: string, options: ScanOptions = {}) {
  await page.addStyleTag({ content: '.day-section { content-visibility: visible !important; }' });

  const builder = new AxeBuilder({ page }).withTags([
    'wcag2a',
    'wcag2aa',
    'wcag21a',
    'wcag21aa',
    'wcag22aa',
  ]);

  if (options.include) builder.include(options.include);

  if (options.maxDays !== undefined) {
    // Every day section is the same component with different text in it.
    const days = await page.locator('[data-day]').count();
    for (let i = options.maxDays; i < days; i++) {
      builder.exclude(`[data-day]:nth-of-type(${i + 1})`);
    }
  }

  const results = await builder.analyze();
  const bad = results.violations.filter((v) => SERIOUS.has(v.impact ?? ''));

  if (bad.length > 0) {
    const detail = bad
      .map(
        (v) =>
          `${v.impact}: ${v.id} — ${v.help}\n   ${v.nodes
            .slice(0, 3)
            .map((n) => n.target.join(' '))
            .join('\n   ')}`,
      )
      .join('\n');
    throw new Error(`${label} has ${bad.length} serious/critical violations:\n${detail}`);
  }
  expect(bad, label).toEqual([]);
}

async function ready(page: Page) {
  await expect(page.locator('[data-day]').first()).toBeVisible({ timeout: 60_000 });
}

async function setTheme(page: Page, theme: 'light' | 'dark') {
  await page.evaluate((t) => {
    document.documentElement.dataset['theme'] = t;
  }, theme);
}

for (const theme of ['light', 'dark'] as const) {
  test.describe(`${theme} theme`, () => {
    test('agenda', async ({ page }) => {
      await page.goto('/?city=baltimore&map=0');
      await ready(page);
      await setTheme(page, theme);
      await scan(page, `agenda (${theme})`, { maxDays: 2 });
    });

    test('month view', async ({ page }) => {
      await page.goto('/?city=baltimore&map=0&view=month');
      await expect(page.getByRole('grid')).toBeVisible({ timeout: 60_000 });
      await setTheme(page, theme);
      await scan(page, `month (${theme})`);
    });

    test('event detail sheet', async ({ page }) => {
      await page.goto('/?city=baltimore&map=0');
      await ready(page);
      await setTheme(page, theme);
      await page.locator('[data-event-key]').first().click();
      // The sheet is a lazy chunk, so allow for a slow fetch and parse.
      await expect(page.getByRole('dialog')).toBeVisible({ timeout: 60_000 });
      // The agenda behind it is covered by the agenda test.
      await scan(page, `event sheet (${theme})`, { include: '[role="dialog"]' });
    });

    test('filters sheet', async ({ page }) => {
      await page.goto('/?city=baltimore&map=0');
      await ready(page);
      await setTheme(page, theme);
      await page.getByRole('button', { name: 'Filters' }).click();
      await expect(page.getByRole('dialog')).toBeVisible({ timeout: 60_000 });
      await scan(page, `filters (${theme})`, { include: '[role="dialog"]' });
    });
  });
}

test('context rail, with the map in it', async ({ page }) => {
  // The rail needs room: it only exists from 1280 up, and a scrollbar can put
  // a nominal 1280 viewport just under that.
  await page.setViewportSize({ width: 1400, height: 900 });
  await page.goto('/?city=baltimore&map=1');
  const rail = page.getByRole('complementary', { name: 'Event context' });
  await expect(rail).toBeVisible({ timeout: 60_000 });
  await scan(page, 'context rail', { include: 'aside[aria-label="Event context"]' });
});

test('the page chrome, with no agenda behind it', async ({ page }) => {
  // An empty result leaves only the header, search pill, sector rail, tide
  // line and footer, so this scans all of them with nothing else in the way.
  await page.goto('/?city=baltimore&map=0&q=zzzzqqqnothing');
  await expect(page.getByText(/No events match/)).toBeVisible({ timeout: 60_000 });
  await scan(page, 'chrome');
});
