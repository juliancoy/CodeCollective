import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const root = resolve(import.meta.dirname, '../../..');

test('legacy calendar renders every category with readable titles and selected/unselected chips', async ({ page }) => {
  await page.setContent('<html lang="en"><head><title>Calendar contrast</title></head><body style="background:#000"><main></main></body></html>');
  for (const file of ['css/master.css', 'css/calendar.css']) {
    await page.addStyleTag({ content: readFileSync(resolve(root, file), 'utf8') });
  }
  const maps = ['community_sectors', 'maslow_needs', 'tech_only'].map(id =>
    JSON.parse(readFileSync(resolve(root, `data/category_maps/${id}.json`), 'utf8')) as {
      categories: { label: string; color: string; text_color: string }[];
    });
  await page.evaluate(categories => {
    const main = document.querySelector('main')!;
    for (const c of categories) {
      const holder = document.createElement('section');
      holder.style.setProperty('--tag-color', c.color);
      holder.style.setProperty('--tag-text-color', c.text_color);
      holder.style.setProperty('--tag-chip-bg', c.color);
      holder.style.setProperty('--tag-chip-fg', c.text_color);
      holder.innerHTML = '<h3 class="card-title tagged"></h3><a href="#" class="fc-event-title tagged"></a><span class="event-hover-tag"></span>';
      for (const element of holder.children) element.textContent = c.label;
      for (const checked of [true, false]) {
        const label = document.createElement('label');
        label.className = 'legend-item legend-tag-chip';
        const input = document.createElement('input');
        input.type = 'checkbox';
        input.checked = checked;
        const text = document.createElement('span');
        text.className = 'legend-text';
        text.textContent = c.label;
        label.append(input, text);
        holder.append(label);
      }
      main.append(holder);
    }
  }, maps.flatMap(map => map.categories));
  const result = await new AxeBuilder({ page }).withRules(['color-contrast']).analyze();
  expect(result.violations, JSON.stringify(result.violations, null, 2)).toEqual([]);
});
