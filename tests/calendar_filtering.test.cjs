const test = require('node:test');
const assert = require('node:assert/strict');
const filterUtils = require('../js/calendarFilterUtils.js');

const communityMap = {
  id: 'community_sectors',
  categories: [
    { label: 'Technology', color: '#2563eb', text_color: '#ffffff', matches: ['Tech Skills', 'AI'] },
    { label: 'Culture', color: '#7c3aed', text_color: '#ffffff', matches: ['Culture', 'Community'] },
    { label: 'Other', color: '#6b7280', text_color: '#ffffff', matches: [] },
  ],
};

const techOnlyMap = {
  id: 'tech_only',
  categories: [
    { label: 'AI & ML', matches: ['AI', 'Technology'] },
    { label: 'General Tech', matches: [] },
  ],
};

test('unmapped events are hidden when excluded toggle is off', () => {
  const matched = filterUtils.eventMatchesTags({
    tags: ['Unknown Tag'],
    categoryMap: { ...communityMap, categories: communityMap.categories.filter((c) => c.label !== 'Other') },
    activeTagSlugs: new Set(['technology', 'culture']),
    showExcludedEvents: false,
  });
  assert.equal(matched, false);
});

test('unmapped events are shown when excluded toggle is on', () => {
  const matched = filterUtils.eventMatchesTags({
    tags: ['Unknown Tag'],
    categoryMap: { ...communityMap, categories: communityMap.categories.filter((c) => c.label !== 'Other') },
    activeTagSlugs: new Set(['technology', 'culture']),
    showExcludedEvents: true,
  });
  assert.equal(matched, true);
});

test('fallback Other events are treated as excluded unless Other is selected or excluded events are shown', () => {
  assert.equal(filterUtils.isExcludedFromActiveMap(['Unknown Tag'], communityMap), true);

  assert.equal(filterUtils.eventMatchesTags({
    tags: ['Unknown Tag'],
    categoryMap: communityMap,
    activeTagSlugs: new Set(['technology', 'culture']),
    showExcludedEvents: false,
  }), false);

  assert.equal(filterUtils.eventMatchesTags({
    tags: ['Unknown Tag'],
    categoryMap: communityMap,
    activeTagSlugs: new Set(['other']),
    showExcludedEvents: false,
  }), true);

  assert.equal(filterUtils.eventMatchesTags({
    tags: ['Unknown Tag'],
    categoryMap: communityMap,
    activeTagSlugs: new Set(['technology', 'culture']),
    showExcludedEvents: true,
  }), true);
});

test('mapped event matches selected legend category', () => {
  const matched = filterUtils.eventMatchesTags({
    tags: ['AI'],
    categoryMap: communityMap,
    activeTagSlugs: new Set(['technology']),
    showExcludedEvents: false,
  });
  assert.equal(matched, true);
});

test('no selected legend categories means no mapped events are shown', () => {
  const matched = filterUtils.eventMatchesTags({
    tags: ['AI'],
    categoryMap: communityMap,
    activeTagSlugs: new Set(),
    showExcludedEvents: false,
  });
  assert.equal(matched, false);
});

test('individual Tags lens collects unique tags and reuses event tag colors', () => {
  const tagMap = filterUtils.buildIndividualTagsMap([
    { tags: ['AI', 'Community'] },
    { tags: ['AI', '  New Topic  ', ''] },
  ], communityMap);

  assert.equal(tagMap.id, 'tags');
  assert.equal(tagMap.label, 'Tags');
  assert.equal(tagMap.individualTags, true);
  assert.deepEqual(tagMap.categories.map((category) => category.label), ['AI', 'Community', 'New Topic']);
  assert.equal(tagMap.categories.find((category) => category.label === 'AI').color, '#2563eb');
  assert.equal(tagMap.categories.find((category) => category.label === 'Community').color, '#7c3aed');
  assert.equal(tagMap.categories.find((category) => category.label === 'New Topic').color, '#6b7280');
  assert.deepEqual(tagMap.categories.find((category) => category.label === 'AI').matches, ['AI']);
});

test('individual Tags lens preserves the configured readable text color', () => {
  const tagMap = filterUtils.buildIndividualTagsMap([
    { tags: ['Economics', 'Finance'] },
  ], {
    categories: [
      { label: 'Economics', color: '#ffffff', text_color: '#000000', matches: ['Economics'] },
      { label: 'Finance', color: '#facc15', text_color: '#111827', matches: ['Finance'] },
    ],
  });

  assert.deepEqual(
    tagMap.categories.map(({ label, color, text_color }) => ({ label, color, text_color })),
    [
      { label: 'Economics', color: '#ffffff', text_color: '#000000' },
      { label: 'Finance', color: '#facc15', text_color: '#111827' },
    ]
  );
});

test('individual Tags lens expects upstream-normalized tags', () => {
  const tagMap = filterUtils.buildIndividualTagsMap([
    { tags: ['Crypto', 'Web3'] },
  ], {
    categories: [
      { label: 'Finance', color: '#facc15', text_color: '#111827', matches: ['Crypto', 'Web3'] },
    ],
  });

  assert.deepEqual(
    tagMap.categories.map(({ label, color, text_color, matches }) => ({ label, color, text_color, matches })),
    [
      { label: 'Crypto', color: '#facc15', text_color: '#111827', matches: ['Crypto'] },
      { label: 'Web3', color: '#facc15', text_color: '#111827', matches: ['Web3'] },
    ]
  );
  assert.equal(filterUtils.eventMatchesTags({
    tags: ['Crypto', 'Web3'],
    categoryMap: tagMap,
    activeTagSlugs: new Set(['crypto']),
  }), true);
});

test('individual Tags lens filters by an exact selected event tag', () => {
  const tagMap = filterUtils.buildIndividualTagsMap([
    { tags: ['AI', 'Community'] },
    { tags: ['Culture'] },
  ], communityMap);

  assert.equal(filterUtils.eventMatchesTags({
    tags: ['AI', 'Community'],
    categoryMap: tagMap,
    activeTagSlugs: new Set(['ai']),
  }), true);
  assert.equal(filterUtils.eventMatchesTags({
    tags: ['Culture'],
    categoryMap: tagMap,
    activeTagSlugs: new Set(['ai']),
  }), false);
});

test('tech_only map excludes non-tech dominant events', () => {
  const categories = filterUtils.getEffectiveMappedCategories(['Business', 'Community'], techOnlyMap);
  assert.equal(categories.length, 0);
});

test('tech_only map includes clear tech events', () => {
  const categories = filterUtils.getEffectiveMappedCategories(['AI'], techOnlyMap);
  assert.ok(categories.length > 0);
});

test('tech_only map includes events tagged as technology even with environment tags', () => {
  const categories = filterUtils.getEffectiveMappedCategories(
    ['Water', 'Tech Community', 'Environment', 'Technology', 'Belonging'],
    techOnlyMap
  );
  assert.ok(categories.length > 0);
});

test('distanceMiles calculates nearby coordinates in miles', () => {
  const distance = filterUtils.distanceMiles(
    { latitude: 39.2904, longitude: -76.6122 },
    { latitude: 39.292, longitude: -76.61 }
  );
  assert.ok(distance > 0);
  assert.ok(distance < 1);
});

test('parseLatLongQuery accepts comma-separated latitude and longitude', () => {
  assert.deepEqual(filterUtils.parseLatLongQuery('39.2904, -76.6122'), {
    latitude: 39.2904,
    longitude: -76.6122,
  });
});

test('resolveProximityQuery averages ZIP-matched event coordinates', () => {
  const resolved = filterUtils.resolveProximityQuery('21201', [
    {
      location: {
        address: '1 N Charles St, Baltimore, MD 21201',
        latitude: 39,
        longitude: -76,
      },
    },
    {
      location: {
        address: '2 W Baltimore St, Baltimore, MD 21201',
        latitude: 40,
        longitude: -77,
      },
    },
  ], {});

  assert.equal(resolved.source, 'zip');
  assert.equal(resolved.matchedCandidates, 2);
  assert.equal(resolved.latitude, 39.5);
  assert.equal(resolved.longitude, -76.5);
});

test('resolveProximityQuery matches cached address identifiers', () => {
  const resolved = filterUtils.resolveProximityQuery('Station North', [], {
    'Station North, Baltimore, MD': { latitude: 39.308, longitude: -76.616 },
  });

  assert.equal(resolved.source, 'address');
  assert.equal(resolved.latitude, 39.308);
  assert.equal(resolved.longitude, -76.616);
});

test('eventMatchesTimeFilters applies date and clock-time windows', () => {
  assert.equal(filterUtils.eventMatchesTimeFilters(
    { startDate: '2026-06-10T15:30:00-04:00' },
    {
      dateFrom: '2026-06-01',
      dateTo: '2026-06-30',
      timeStart: '09:00',
      timeEnd: '17:00',
      timeZone: 'America/New_York',
    }
  ), true);

  assert.equal(filterUtils.eventMatchesTimeFilters(
    { startDate: '2026-06-10T20:30:00-04:00' },
    {
      dateFrom: '2026-06-01',
      dateTo: '2026-06-30',
      timeStart: '09:00',
      timeEnd: '17:00',
      timeZone: 'America/New_York',
    }
  ), false);
});

test('eventMatchesTimeFilters treats matching start and end dates as inclusive', () => {
  assert.equal(filterUtils.eventMatchesTimeFilters(
    { startDate: '2026-06-10T00:01:00-04:00' },
    {
      dateFrom: '2026-06-10',
      dateTo: '2026-06-10',
      timeZone: 'America/New_York',
    }
  ), true);

  assert.equal(filterUtils.eventMatchesTimeFilters(
    { startDate: '2026-06-10T23:59:00-04:00' },
    {
      dateFrom: '2026-06-10',
      dateTo: '2026-06-10',
      timeZone: 'America/New_York',
    }
  ), true);

  assert.equal(filterUtils.eventMatchesTimeFilters(
    { startDate: '2026-06-11T00:01:00-04:00' },
    {
      dateFrom: '2026-06-10',
      dateTo: '2026-06-10',
      timeZone: 'America/New_York',
    }
  ), false);
});
