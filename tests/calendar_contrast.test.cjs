const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '..');

function luminance(hex) {
  const channels = [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16) / 255)
    .map(c => c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
  return channels.reduce((sum, c, i) => sum + c * [0.2126, 0.7152, 0.0722][i], 0);
}
function contrast(foreground, background) {
  const [low, high] = [luminance(foreground), luminance(background)].sort((a, b) => a - b);
  return (high + 0.05) / (low + 0.05);
}
function check(fg, bg, label, minimum = 4.5) {
  const ratio = contrast(fg, bg);
  assert.ok(ratio >= minimum, `${label}: ${fg} on ${bg} = ${ratio.toFixed(2)}:1 (requires ${minimum}:1)`);
}

test('every calendar lens and fallback uses WCAG AA normal-text contrast', () => {
  const files = ['data/category_maps.json'];
  for (const dir of ['data/category_maps', 'calendar-next-app/src/data/lenses']) {
    files.push(...fs.readdirSync(path.join(root, dir)).filter(f => f.endsWith('.json')).map(f => `${dir}/${f}`));
  }
  for (const file of files) {
    const data = JSON.parse(fs.readFileSync(path.join(root, file), 'utf8'));
    for (const map of data.maps || [data]) {
      for (const category of [...(map.categories || []), ...(map.other ? [map.other] : [])]) {
        check(category.text_color || '#ffffff', category.color, `${file}: ${category.label || 'fallback'}`);
      }
    }
  }
});

test('light, dark and system themes retain readable text on every calendar surface', () => {
  const css = fs.readFileSync(path.join(root, 'calendar-next-app/src/styles/tokens.css'), 'utf8');
  const themes = [...css.matchAll(/:root[^\{]*\{([^}]+)/g)];
  assert.equal(themes.length, 3);
  const defaults = Object.fromEntries([...themes[0][1].matchAll(/--([\w-]+): (#[\da-fA-F]{6});/g)].map(m => [m[1], m[2]]));
  for (const theme of themes) {
    const tokens = { ...defaults, ...Object.fromEntries([...theme[1].matchAll(/--([\w-]+): (#[\da-fA-F]{6});/g)].map(m => [m[1], m[2]])) };
    const pairs = [['brand-ink', 'brand'], ['band-meta', 'brand'], ['sky', 'brand'],
      ['brand-soft-ink', 'brand-soft'], ['brand-on-bg', 'bg'], ['gold-ink', 'gold'],
      ['brand-soft-ink', 'intro-bg'], ['brand', 'warm'],
      ['danger', 'sector-politics-tint']];
    const surfaces = ['bg', 'bg-soft', 'brand-soft', ...Object.keys(tokens).filter(k => k.endsWith('-tint'))];
    for (const surface of surfaces) {
      pairs.push(['ink', surface], ['ink-2', surface]);
    }
    for (const sector of Object.keys(tokens).filter(k => k.startsWith('sector-') && !k.endsWith('-tint'))) {
      pairs.push([sector, 'bg'], [sector, `${sector}-tint`]);
    }
    for (const [fg, bg] of pairs) check(tokens[fg], tokens[bg], `${tokens.bg}: ${fg}/${bg}`);
    for (const surface of ['bg', 'bg-soft', 'brand-soft']) {
      check(tokens['brand-on-bg'], tokens[surface], `focus ring on ${surface}`, 3);
    }
  }
});
