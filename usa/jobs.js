const DATA_URL = './data/usajobs-lite.json.gz';
const FALLBACK_DATA_URL = './data/usajobs-lite.json';
const FILTERS_STORAGE_KEY = 'usajobsFiltersV1';

const billsTableBody = document.getElementById('bills-table-body');
const billFilterInput = document.getElementById('bill-filter');
const sponsorFilterInput = document.getElementById('sponsor-filter');
const categoryFilterInput = document.getElementById('category-filter');
const upcomingOnlyToggle = document.getElementById('upcoming-only-toggle');
const searchClearButtons = [...document.querySelectorAll('.search-clear')];
const sponsorTableBody = document.getElementById('sponsor-table-body');
const categoryTableBody = document.getElementById('category-table-body');
const categoryColumn = document.getElementById('category-column');
const categoryModeToggle = document.getElementById('category-mode-toggle');
const billCount = document.getElementById('bill-count');
const billUpdated = document.getElementById('bill-updated');
const statusMessage = document.getElementById('status-message');
const resetFiltersButton = document.getElementById('reset-filters');

const billModal = document.getElementById('bill-modal');
const billModalTitle = document.getElementById('bill-modal-title');
const billModalContent = document.getElementById('bill-modal-content');
const billModalClose = document.getElementById('bill-modal-close');
const hoverCard = document.getElementById('hover-card');
const billsTable = document.querySelector('.bills-table');
const billsTableWrap = document.querySelector('.bills-table-wrap');
const insightsGrid = document.querySelector('.insights-grid');

let allBills = [];
let preparedBills = [];
let activeSponsor = '';
let activeCategory = '';
let sortColumn = '';
let sortDirection = '';
let showUpcomingOnly = true;
let hoverSwapTimer = null;
let sponsorProfiles = new Map();
let resizeState = null;
let gridResizeState = null;
let copyToastTimer = null;
let categoryPanelMode = 'categories';
let advancedFilters = {
  gsMin: '',
  gsMax: '',
  clMin: '',
  clMax: '',
  location: '',
  securityClearance: '',
  remoteMode: 'all'
};
let filterCache = {
  baseKey: '',
  baseEntries: [],
  fullKey: '',
  fullEntries: []
};

const GRID_WIDTHS_STORAGE_KEY = 'usajobsGridWidthsV1';

const COLUMN_FONT_SIZE_CONFIG = {
  sponsor: { min: 12, max: 22, step: 1, default: 16, storageKey: 'usajobsFontSizeAgency' },
  category: { min: 12, max: 22, step: 1, default: 16, storageKey: 'usajobsFontSizeCategory' },
  bills: { min: 12, max: 22, step: 1, default: 16, storageKey: 'usajobsFontSizeJobs' }
};

const columnFontSizes = {
  sponsor: COLUMN_FONT_SIZE_CONFIG.sponsor.default,
  category: COLUMN_FONT_SIZE_CONFIG.category.default,
  bills: COLUMN_FONT_SIZE_CONFIG.bills.default
};

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function normalizePersonName(value) {
  return String(value || '')
    .toLowerCase()
    .replace(/\b(council vice-president|council vice president|vice president|council president|city council member|council member)\b/g, '')
    .replace(/,\s*district\s+\d+.*/g, '')
    .replace(/["“”]/g, '')
    .replace(/[^a-z0-9\s'-]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function asArray(value) {
  return Array.isArray(value) ? value : [];
}

function truncateText(text, maxLength) {
  const normalized = String(text || '').replace(/\s+/g, ' ').trim();
  if (!normalized || normalized.length <= maxLength) {
    return normalized;
  }
  return `${normalized.slice(0, Math.max(0, maxLength - 1)).trimEnd()}…`;
}

function normalizeText(value) {
  return String(value || '').trim().toLowerCase();
}

function isRemoteEligible(record) {
  if (record.remote_indicator === true) {
    return true;
  }
  const telework = normalizeText(record.telework_eligible);
  if (!telework) {
    return false;
  }
  if (['true', 'yes', 'eligible', 'remote', '100%'].includes(telework)) {
    return true;
  }
  if (telework.includes('eligible') || telework.includes('remote') || telework.includes('telework')) {
    return !telework.includes('not');
  }
  return false;
}

function getLocations(record) {
  const values = Array.isArray(record.locations) && record.locations.length
    ? record.locations
    : [record.location_display];
  return [...new Set(values.map((value) => String(value || '').trim()).filter(Boolean))];
}

function parseGradeNumber(value) {
  const text = String(value || '').trim();
  if (!text) {
    return null;
  }
  const match = text.match(/\d+/);
  if (!match) {
    return null;
  }
  const parsed = Number.parseInt(match[0], 10);
  return Number.isNaN(parsed) ? null : parsed;
}

function getGsLevels(record) {
  const low = parseGradeNumber(record.grade_low);
  const high = parseGradeNumber(record.grade_high);
  if (low !== null && high !== null) {
    const start = Math.min(low, high);
    const end = Math.max(low, high);
    return Array.from({ length: (end - start) + 1 }, (_, index) => start + index);
  }
  if (low !== null) {
    return [low];
  }
  if (high !== null) {
    return [high];
  }
  return [];
}

function formatGsLevel(value) {
  const numeric = Number.parseInt(String(value || ''), 10);
  if (Number.isNaN(numeric)) {
    return 'Any';
  }
  return `GS-${String(numeric).padStart(2, '0')}`;
}

function formatGradeLevel(system, value) {
  const numeric = Number.parseInt(String(value || ''), 10);
  if (Number.isNaN(numeric)) {
    return 'Any';
  }
  return `${system}-${String(numeric).padStart(2, '0')}`;
}

function describeGradeLevel(system, value) {
  const numeric = Number.parseInt(String(value || ''), 10);
  if (Number.isNaN(numeric)) {
    return '';
  }
  if (system === 'GS') {
    if (numeric <= 4) {
      return 'Typical entry-level or trainee federal support work.';
    }
    if (numeric <= 7) {
      return 'Typical early-career specialist or developmental professional work.';
    }
    if (numeric <= 10) {
      return 'Typical experienced administrative or technical support work.';
    }
    if (numeric <= 12) {
      return 'Typical mid-level professional or analyst work.';
    }
    if (numeric === 13) {
      return 'Typical senior specialist or advanced independent contributor work.';
    }
    if (numeric === 14) {
      return 'Typical expert, lead, or supervisory professional work.';
    }
    return 'Typical top-tier supervisory, managerial, or expert professional work.';
  }
  if (system === 'CL') {
    if (numeric <= 24) {
      return 'Typical judiciary administrative or operational support work.';
    }
    if (numeric <= 26) {
      return 'Typical judiciary specialist or officer-level work.';
    }
    if (numeric <= 29) {
      return 'Typical senior judiciary officer or highly experienced specialist work.';
    }
    return 'Typical judiciary leadership or very senior specialist work.';
  }
  return '';
}

function isSupportedGradeLevel(system, level) {
  const numeric = Number.parseInt(String(level || ''), 10);
  if (Number.isNaN(numeric)) {
    return false;
  }
  if (system === 'GS') {
    return numeric >= 1 && numeric <= 15;
  }
  if (system === 'CL') {
    return numeric >= 1;
  }
  return true;
}

function getGsBoundsFromLevels(levels) {
  if (!levels.length) {
    return null;
  }
  return {
    min: Math.min(...levels),
    max: Math.max(...levels)
  };
}

function getActiveRange(bounds, minKey, maxKey) {
  if (!bounds) {
    return null;
  }
  const parsedMin = Number.parseInt(advancedFilters[minKey], 10);
  const parsedMax = Number.parseInt(advancedFilters[maxKey], 10);
  const min = Number.isNaN(parsedMin) ? bounds.min : Math.max(bounds.min, Math.min(parsedMin, bounds.max));
  const max = Number.isNaN(parsedMax) ? bounds.max : Math.max(bounds.min, Math.min(parsedMax, bounds.max));
  return {
    min: Math.min(min, max),
    max: Math.max(min, max)
  };
}

function updateGradeRange(system, nextLevel) {
  const clickedLevel = Number.parseInt(String(nextLevel || ''), 10);
  if (Number.isNaN(clickedLevel)) {
    return;
  }
  const minKey = `${system.toLowerCase()}Min`;
  const maxKey = `${system.toLowerCase()}Max`;
  const currentMin = Number.parseInt(advancedFilters[minKey], 10);
  const currentMax = Number.parseInt(advancedFilters[maxKey], 10);
  if (Number.isNaN(currentMin) || Number.isNaN(currentMax)) {
    advancedFilters[minKey] = String(clickedLevel);
    advancedFilters[maxKey] = String(clickedLevel);
    return;
  }
  if (clickedLevel < currentMin) {
    advancedFilters[minKey] = String(clickedLevel);
    return;
  }
  if (clickedLevel > currentMax) {
    advancedFilters[maxKey] = String(clickedLevel);
    return;
  }
  advancedFilters[minKey] = String(clickedLevel);
  advancedFilters[maxKey] = String(clickedLevel);
}

function getSponsorProfile(name) {
  const normalized = normalizePersonName(name);
  if (!normalized) {
    return null;
  }
  if (sponsorProfiles.has(normalized)) {
    return sponsorProfiles.get(normalized);
  }
  const tokens = normalized.split(' ');
  if (tokens.length >= 2) {
    return sponsorProfiles.get(`${tokens[0]} ${tokens[tokens.length - 1]}`) || null;
  }
  return null;
}

function buildProfileImageMarkup(profile, caption = 'Official portrait') {
  if (!profile?.portrait_path) {
    return '';
  }
  return `
    <section class="hover-card-images">
      <figure>
        <img alt="${escapeHtml(profile.name || 'Official portrait')}" src="${escapeHtml(profile.portrait_path)}">
        <figcaption>${escapeHtml(caption)}</figcaption>
      </figure>
    </section>
  `;
}

function syncBillsDisplayFontSize() {
  document.documentElement.style.setProperty('--bills-font-size', `${columnFontSizes.bills}px`);
}

function loadColumnFontSizes() {
  for (const [column, config] of Object.entries(COLUMN_FONT_SIZE_CONFIG)) {
    try {
      const saved = localStorage.getItem(config.storageKey);
      if (!saved) {
        continue;
      }
      const parsed = parseInt(saved, 10);
      if (!Number.isNaN(parsed) && parsed >= config.min && parsed <= config.max) {
        columnFontSizes[column] = parsed;
      }
    } catch {
      // Ignore storage errors.
    }
  }
  applyColumnFontSizes();
}

function applyColumnFontSizes() {
  for (const [column, size] of Object.entries(columnFontSizes)) {
    const element = document.getElementById(`${column}-column`);
    if (element) {
      element.style.setProperty('--column-font-size', `${size}px`);
    }
  }
  syncBillsDisplayFontSize();
}

function adjustColumnFontSize(column, direction) {
  const config = COLUMN_FONT_SIZE_CONFIG[column];
  if (!config) {
    return;
  }
  const nextValue = columnFontSizes[column] + (direction * config.step);
  columnFontSizes[column] = Math.max(config.min, Math.min(config.max, nextValue));
  const element = document.getElementById(`${column}-column`);
  if (element) {
    element.style.setProperty('--column-font-size', `${columnFontSizes[column]}px`);
  }
  if (column === 'bills') {
    syncBillsDisplayFontSize();
  }
  try {
    localStorage.setItem(config.storageKey, String(columnFontSizes[column]));
  } catch {
    // Ignore storage errors.
  }
}

function loadPersistedFilters() {
  try {
    const raw = localStorage.getItem(FILTERS_STORAGE_KEY);
    if (!raw) {
      return {
        billQuery: '',
        sponsorQuery: '',
        categoryQuery: '',
        sponsor: '',
        category: '',
        upcomingOnly: true,
        categoryPanelMode: 'categories',
        gsMin: '',
        gsMax: '',
        clMin: '',
        clMax: '',
        location: '',
        securityClearance: '',
        remoteMode: 'all'
      };
    }
    const parsed = JSON.parse(raw);
    return {
      billQuery: String(parsed.billQuery || ''),
      sponsorQuery: String(parsed.sponsorQuery || ''),
      categoryQuery: String(parsed.categoryQuery || ''),
      sponsor: String(parsed.sponsor || ''),
      category: String(parsed.category || ''),
      upcomingOnly: parsed.upcomingOnly !== false,
      categoryPanelMode: parsed.categoryPanelMode === 'filters' ? 'filters' : 'categories',
      gsMin: String(parsed.gsMin || ''),
      gsMax: String(parsed.gsMax || ''),
      clMin: String(parsed.clMin || ''),
      clMax: String(parsed.clMax || ''),
      location: String(parsed.location || ''),
      securityClearance: String(parsed.securityClearance || ''),
      remoteMode: parsed.remoteMode === 'remote' || parsed.remoteMode === 'onsite' ? parsed.remoteMode : 'all'
    };
  } catch {
    return {
      billQuery: '',
      sponsorQuery: '',
      categoryQuery: '',
      sponsor: '',
      category: '',
      upcomingOnly: true,
      categoryPanelMode: 'categories',
      gsMin: '',
      gsMax: '',
      clMin: '',
      clMax: '',
      location: '',
      securityClearance: '',
      remoteMode: 'all'
    };
  }
}

function persistFilters() {
  try {
    localStorage.setItem(FILTERS_STORAGE_KEY, JSON.stringify({
      billQuery: billFilterInput.value || '',
      sponsorQuery: sponsorFilterInput.value || '',
      categoryQuery: categoryFilterInput.value || '',
      sponsor: activeSponsor,
      category: activeCategory,
      upcomingOnly: showUpcomingOnly,
      categoryPanelMode,
      gsMin: advancedFilters.gsMin,
      gsMax: advancedFilters.gsMax,
      clMin: advancedFilters.clMin,
      clMax: advancedFilters.clMax,
      location: advancedFilters.location,
      securityClearance: advancedFilters.securityClearance,
      remoteMode: advancedFilters.remoteMode
    }));
  } catch {
    // Ignore storage errors.
  }
}

function clearPersistedFilters() {
  try {
    localStorage.removeItem(FILTERS_STORAGE_KEY);
  } catch {
    // Ignore storage errors.
  }
}

function loadPersistedGridWidths() {
  try {
    const raw = localStorage.getItem(GRID_WIDTHS_STORAGE_KEY);
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed) || parsed.length !== 3) {
      return null;
    }
    return parsed.map((value) => Number(value)).filter((value) => Number.isFinite(value));
  } catch {
    return null;
  }
}

function persistGridWidths(widths) {
  try {
    localStorage.setItem(GRID_WIDTHS_STORAGE_KEY, JSON.stringify(widths.map((value) => Math.round(value))));
  } catch {
    // Ignore storage errors.
  }
}

function updateSearchClearButtons() {
  for (const button of searchClearButtons) {
    const target = document.getElementById(button.dataset.clearTarget || '');
    const targetId = button.dataset.clearTarget || '';
    const hasText = Boolean(target && target.value.trim());
    const hasSelection = (
      (targetId === 'sponsor-filter' && Boolean(activeSponsor))
      || (targetId === 'category-filter' && Boolean(activeCategory))
    );
    button.classList.toggle('visible', hasText || hasSelection);
  }
}

function formatDateTime(dateValue, timeValue = '') {
  const combined = [dateValue, timeValue].filter(Boolean).join(' ');
  if (!combined) {
    return '';
  }
  const parsed = new Date(combined);
  if (Number.isNaN(parsed.getTime())) {
    return combined;
  }
  return parsed.toLocaleString(undefined, {
    dateStyle: 'medium',
    timeStyle: timeValue ? 'short' : undefined
  });
}

function getHearingDate(record) {
  if (!record.close_date) {
    return null;
  }
  const parsed = new Date(record.close_date);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

function isUpcomingBill(record) {
  const hearingDate = getHearingDate(record);
  if (!hearingDate) {
    return false;
  }
  const now = new Date();
  return hearingDate.getTime() >= new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
}

function extractCategories(record) {
  const values = Array.isArray(record.categories) ? record.categories : [];
  return [...new Set(values.map((value) => String(value || '').trim()).filter(Boolean))];
}

function searchableText(record) {
  return [
    record.job_id,
    record.position_id,
    record.title,
    record.summary,
    record.status,
    record.organization_name,
    record.department_name,
    record.agency,
    record.location_display,
    ...(record.locations || []),
    ...(record.job_categories || []),
    ...(record.position_schedule || []),
    ...(record.position_offering_type || []),
    ...(record.hiring_paths || []),
    ...extractCategories(record),
    record.salary_summary,
    record.telework_eligible,
    record.who_may_apply,
    ...(record.major_duties || [])
  ]
    .filter(Boolean)
    .join(' ')
    .toLowerCase();
}

function buildPreparedBills(records) {
  return records.map((bill, index) => {
    const sponsor = String(bill.agency || bill.organization_name || 'Unknown agency').trim() || 'Unknown agency';
    const categories = extractCategories(bill);
    return {
      index,
      bill,
      sponsor,
      categories,
      categoriesWithFallback: categories.length ? categories : ['Uncategorized'],
      locations: getLocations(bill),
      payPlan: String(bill.pay_plan || '').trim().toUpperCase(),
      gsLevels: getGsLevels(bill),
      securityClearance: String(bill.security_clearance || '').trim(),
      remoteEligible: isRemoteEligible(bill),
      searchText: searchableText(bill),
      hearingDate: getHearingDate(bill),
      statusLower: String(bill.status || '').toLowerCase()
    };
  });
}

function resetFilterCache() {
  filterCache = {
    baseKey: '',
    baseEntries: [],
    fullKey: '',
    fullEntries: []
  };
}

function getBaseFilterState() {
  return {
    query: billFilterInput.value.trim().toLowerCase(),
    sponsor: activeSponsor,
    category: activeCategory,
    upcomingOnly: showUpcomingOnly
  };
}

function getFullFilterState() {
  return {
    ...getBaseFilterState(),
    gsMin: advancedFilters.gsMin,
    gsMax: advancedFilters.gsMax,
    clMin: advancedFilters.clMin,
    clMax: advancedFilters.clMax,
    location: advancedFilters.location,
    securityClearance: advancedFilters.securityClearance,
    remoteMode: advancedFilters.remoteMode
  };
}

function createFilterKey(state) {
  return JSON.stringify(state);
}

function matchesGradeRange(entry, system, minValue, maxValue) {
  const parsedMin = Number.parseInt(minValue, 10);
  const parsedMax = Number.parseInt(maxValue, 10);
  if (Number.isNaN(parsedMin) || Number.isNaN(parsedMax)) {
    return false;
  }
  if (entry.payPlan !== system || !entry.gsLevels.length) {
    return false;
  }
  const supportedLevels = entry.gsLevels.filter((level) => isSupportedGradeLevel(system, level));
  if (!supportedLevels.length) {
    return false;
  }
  const entryMin = supportedLevels[0];
  const entryMax = supportedLevels[supportedLevels.length - 1];
  return !(entryMax < parsedMin || entryMin > parsedMax);
}

function entryMatchesBaseFilters(entry, state, options = {}) {
  const { ignoreSponsor = false, ignoreCategory = false } = options;
  if (state.upcomingOnly && entry.statusLower !== 'open') {
    return false;
  }
  if (!ignoreSponsor && state.sponsor && entry.sponsor !== state.sponsor) {
    return false;
  }
  if (!ignoreCategory && state.category && !entry.categoriesWithFallback.includes(state.category)) {
    return false;
  }
  if (state.query && !entry.searchText.includes(state.query)) {
    return false;
  }
  return true;
}

function entryMatchesAdvancedFilters(entry, state) {
  const hasGsFilter = !Number.isNaN(Number.parseInt(state.gsMin, 10)) && !Number.isNaN(Number.parseInt(state.gsMax, 10));
  const hasClFilter = !Number.isNaN(Number.parseInt(state.clMin, 10)) && !Number.isNaN(Number.parseInt(state.clMax, 10));
  if (hasGsFilter || hasClFilter) {
    const matchesGs = hasGsFilter && matchesGradeRange(entry, 'GS', state.gsMin, state.gsMax);
    const matchesCl = hasClFilter && matchesGradeRange(entry, 'CL', state.clMin, state.clMax);
    if (!matchesGs && !matchesCl) {
      return false;
    }
  }
  if (state.location && !entry.locations.includes(state.location)) {
    return false;
  }
  if (state.securityClearance && entry.securityClearance !== state.securityClearance) {
    return false;
  }
  if (state.remoteMode === 'remote' && !entry.remoteEligible) {
    return false;
  }
  if (state.remoteMode === 'onsite' && entry.remoteEligible) {
    return false;
  }
  return true;
}

function getSponsorCountEntries() {
  const state = getFullFilterState();
  const entries = [];
  for (const entry of preparedBills) {
    if (!entryMatchesBaseFilters(entry, state, { ignoreSponsor: true })) {
      continue;
    }
    if (!entryMatchesAdvancedFilters(entry, state)) {
      continue;
    }
    entries.push(entry);
  }
  return entries;
}

function renderSponsorTable() {
  const sponsorQuery = sponsorFilterInput.value.trim().toLowerCase();
  const filteredCounts = new Map();
  const totalCounts = new Map();

  for (const entry of preparedBills) {
    totalCounts.set(entry.sponsor, (totalCounts.get(entry.sponsor) || 0) + 1);
  }

  for (const entry of getSponsorCountEntries()) {
    filteredCounts.set(entry.sponsor, (filteredCounts.get(entry.sponsor) || 0) + 1);
  }

  if (activeSponsor && !filteredCounts.has(activeSponsor)) {
    activeSponsor = '';
  }

  const rows = [...filteredCounts.entries()]
    .filter(([, count]) => count > 0)
    .filter(([name]) => !sponsorQuery || name.toLowerCase().includes(sponsorQuery))
    .sort((a, b) => (b[1] - a[1]) || a[0].localeCompare(b[0]))
    .map(([name, count]) => {
      const totalCount = totalCounts.get(name) || 0;
      const isFilteredCount = count < totalCount;
      return `
      <div class="list-row">
        <button type="button" class="sponsor-button${name === activeSponsor ? ' active' : ''}" data-sponsor="${escapeHtml(name)}">
          ${escapeHtml(name)}
        </button>
        <span class="list-count${isFilteredCount ? ' filtered' : ''}">${count.toLocaleString()}</span>
      </div>
    `;
    })
    .join('');

  sponsorTableBody.innerHTML = rows || '<div class="list-row"><span>No sponsor data available.</span><span class="list-count">0</span></div>';
}

function renderCategoryTable() {
  if (categoryPanelMode === 'filters') {
    renderAdvancedFilterPanel();
    return;
  }
  const categoryQuery = categoryFilterInput.value.trim().toLowerCase();
  const categoryCounts = new Map();

  for (const entry of preparedBills) {
    if (activeSponsor && entry.sponsor !== activeSponsor) {
      continue;
    }
    const categories = entry.categories.length ? entry.categories : ['Uncategorized'];
    for (const category of categories) {
      categoryCounts.set(category, (categoryCounts.get(category) || 0) + 1);
    }
  }

  if (activeCategory && !categoryCounts.has(activeCategory)) {
    activeCategory = '';
  }

  const rows = [...categoryCounts.entries()]
    .filter(([name]) => !categoryQuery || name.toLowerCase().includes(categoryQuery))
    .sort((a, b) => (b[1] - a[1]) || a[0].localeCompare(b[0]))
    .map(([name, count]) => `
      <div class="list-row">
        <button type="button" class="sponsor-button${name === activeCategory ? ' active' : ''}" data-category="${escapeHtml(name)}">
          ${escapeHtml(name)}
        </button>
        <span class="list-count">${count.toLocaleString()}</span>
      </div>
    `)
    .join('');

  categoryTableBody.innerHTML = rows || '<div class="list-row"><span>No category data available.</span><span class="list-count">0</span></div>';
}

function getBaseFilteredEntries() {
  const state = getBaseFilterState();
  const key = createFilterKey(state);
  if (filterCache.baseKey === key) {
    return filterCache.baseEntries;
  }

  const entries = [];
  for (const entry of preparedBills) {
    if (!entryMatchesBaseFilters(entry, state)) {
      continue;
    }
    entries.push(entry);
  }

  filterCache.baseKey = key;
  filterCache.baseEntries = entries;
  return entries;
}

function getFilteredEntries() {
  const state = getFullFilterState();
  const key = createFilterKey(state);
  if (filterCache.fullKey === key) {
    return filterCache.fullEntries;
  }

  const entries = [];
  for (const entry of getBaseFilteredEntries()) {
    if (!entryMatchesAdvancedFilters(entry, state)) {
      continue;
    }
    entries.push(entry);
  }

  filterCache.fullKey = key;
  filterCache.fullEntries = entries;
  return entries;
}

function getSortValue(entry, column) {
  switch (column) {
    case 'billNumber':
      return String(entry.bill.position_id || entry.bill.job_id || '').toLowerCase();
    case 'title':
      return String(entry.bill.title || '').toLowerCase();
    case 'sponsor':
      return String(entry.bill.agency || entry.bill.organization_name || '').toLowerCase();
    case 'status':
      return String(entry.bill.status || '').toLowerCase();
    case 'hearingDate':
      return entry.hearingDate ? entry.hearingDate.getTime() : Number.MAX_SAFE_INTEGER;
    default:
      return String(entry.bill.title || '').toLowerCase();
  }
}

function sortEntries(entries) {
  if (!sortColumn || !sortDirection) {
    return [...entries];
  }
  return [...entries].sort((a, b) => {
    const left = getSortValue(a, sortColumn);
    const right = getSortValue(b, sortColumn);
    if (left === right) {
      return String(a.bill.position_id || a.bill.job_id || a.bill.title || '').localeCompare(
        String(b.bill.position_id || b.bill.job_id || b.bill.title || '')
      );
    }
    if (typeof left === 'number' && typeof right === 'number') {
      return sortDirection === 'asc' ? left - right : right - left;
    }
    return sortDirection === 'asc'
      ? String(left).localeCompare(String(right))
      : String(right).localeCompare(String(left));
  });
}

function getJobNavigationUrl(bill) {
  // Use the official announcement, never an application-status endpoint.
  const jobId = String(bill.job_id || '').trim();
  return /^\d+$/.test(jobId) ? `https://www.usajobs.gov/job/${jobId}` : '';
}

function formatBillSalary(bill) {
  if (Array.isArray(bill.salary) && bill.salary.length) {
    const first = bill.salary[0] || {};
    const minimum = String(first.MinimumRange ?? '').trim();
    const maximum = String(first.MaximumRange ?? '').trim();
    const interval = String(first.Description || first.RateIntervalCode || '').trim();
    if (minimum && maximum) {
      return `$${minimum} - $${maximum} ${interval}`.trim();
    }
  }
  return String(bill.salary_summary || '').trim();
}

function buildGradeHistogramMarkup(system, options, activeRange) {
  if (!options.length || !activeRange) {
    return '';
  }
  const maxCount = Math.max(...options.map(([, count]) => count), 1);
  return `
    <div class="advanced-filter-group">
      <span class="advanced-filter-label">${system} Level</span>
      <div class="advanced-filter-histogram">
        <div class="advanced-filter-histogram-values">
          <span>Min ${escapeHtml(formatGradeLevel(system, activeRange.min))}</span>
          <span>Max ${escapeHtml(formatGradeLevel(system, activeRange.max))}</span>
        </div>
        <div class="advanced-filter-histogram-bars" style="--histogram-count:${options.length}">
          ${options.map(([level, count]) => {
            const isActive = level >= activeRange.min && level <= activeRange.max;
            const height = Math.max(10, Math.round((count / maxCount) * 72));
            return `
              <button
                type="button"
                class="advanced-filter-bar${isActive ? ' active' : ''}"
                data-grade-system="${system}"
                data-grade-level="${level}"
                aria-label="Set ${system} range using ${formatGradeLevel(system, level)}"
                title="${formatGradeLevel(system, level)}: ${count.toLocaleString()} jobs"
              >
                <span class="advanced-filter-bar-column" style="height:${height}px"></span>
              </button>
            `;
          }).join('')}
        </div>
        <div class="advanced-filter-histogram-axis" style="--histogram-count:${options.length}">
          ${options.map(([level]) => `
            <span class="advanced-filter-axis-label">${escapeHtml(String(level))}</span>
          `).join('')}
        </div>
      </div>
    </div>
  `;
}

function createBillRowMarkup(entry) {
  const { bill, index } = entry;
  const sponsor = String(bill.agency || bill.organization_name || 'Unknown agency').trim() || 'Unknown agency';
  const closingLabel = formatDateTime(bill.close_date);
  const positionId = bill.position_id || bill.job_id || 'N/A';
  const jobNavigationUrl = getJobNavigationUrl(bill);
  return `
    <tr>
      <td class="bill-number-cell">
        <button
          type="button"
          class="bill-number-copy"
          data-copy-value="${escapeHtml(positionId)}"
          aria-label="Copy position ID ${escapeHtml(positionId)}"
        >
          <span class="bill-number-label">Position ID</span>
          <span class="bill-number-value">${escapeHtml(positionId)}</span>
          <span class="bill-number-toast" aria-hidden="true">Copied</span>
        </button>
      </td>
      <td>
        <p class="bill-title">
          ${jobNavigationUrl
            ? `<a href="${escapeHtml(jobNavigationUrl)}" class="bill-title-button" data-bill-index="${index}" target="_blank" rel="noopener noreferrer">${escapeHtml(bill.title || 'Untitled job')}</a>`
            : `<span class="bill-title-button" data-bill-index="${index}" tabindex="0">${escapeHtml(bill.title || 'Untitled job')}</span>`}
        </p>
      </td>
      <td>
        <button type="button" class="bill-sponsor-button" data-sponsor-name="${escapeHtml(sponsor)}">
          ${escapeHtml(sponsor)}
        </button>
      </td>
      <td>${escapeHtml(bill.status || 'Status unavailable')}</td>
      <td>${escapeHtml(closingLabel || 'No close date listed')}</td>
    </tr>
  `;
}

function renderBills() {
  renderSponsorTable();
  const filteredEntries = sortEntries(getFilteredEntries());
  billsTableBody.innerHTML = filteredEntries.map(createBillRowMarkup).join('')
    || '<tr><td colspan="5">No USAJOBS records matched these filters.</td></tr>';

  const openCount = filteredEntries.filter((entry) => String(entry.bill.status || '').toLowerCase() === 'open').length;
  billCount.textContent = `${filteredEntries.length.toLocaleString()} jobs`;
  if (!allBills.length) {
    statusMessage.textContent = 'USAJOBS data file is empty. Run fetch_jobs.py with API credentials or --input-json to populate data/usajobs.json.';
    return;
  }
  statusMessage.textContent = openCount
    ? `${openCount.toLocaleString()} jobs are still open in the current filtered set.`
    : 'No open jobs in the current filtered set.';
}

function updateSortIndicators() {
  for (const header of document.querySelectorAll('th.sortable')) {
    header.classList.remove('sort-asc', 'sort-desc');
    if (header.dataset.sort === sortColumn) {
      header.classList.add(sortDirection === 'asc' ? 'sort-asc' : 'sort-desc');
    }
  }
}

function stringifyValue(value) {
  if (value === null || value === undefined || value === '') {
    return 'N/A';
  }
  if (Array.isArray(value)) {
    return value.length ? value.join(', ') : 'N/A';
  }
  return String(value);
}

async function copyTextToClipboard(value) {
  const text = String(value || '').trim();
  if (!text) {
    return false;
  }
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return true;
  }

  const textArea = document.createElement('textarea');
  textArea.value = text;
  textArea.setAttribute('readonly', '');
  textArea.style.position = 'absolute';
  textArea.style.left = '-9999px';
  document.body.append(textArea);
  textArea.select();
  const succeeded = document.execCommand('copy');
  textArea.remove();
  return succeeded;
}

function showCopyToast(button) {
  if (!button) {
    return;
  }
  if (copyToastTimer) {
    window.clearTimeout(copyToastTimer);
  }
  for (const activeButton of document.querySelectorAll('.bill-number-copy.is-copied')) {
    activeButton.classList.remove('is-copied');
  }
  button.classList.add('is-copied');
  copyToastTimer = window.setTimeout(() => {
    button.classList.remove('is-copied');
  }, 1000);
}

function renderAdvancedFilterPanel() {
  const baseEntries = getBaseFilteredEntries();
  const gsLevelCounts = new Map();
  const clLevelCounts = new Map();
  const locationCounts = new Map();
  const securityClearanceCounts = new Map();
  for (const entry of baseEntries) {
    let levelCounts = null;
    let system = '';
    if (entry.payPlan === 'GS') {
      levelCounts = gsLevelCounts;
      system = 'GS';
    } else if (entry.payPlan === 'CL') {
      levelCounts = clLevelCounts;
      system = 'CL';
    }
    if (levelCounts) {
      for (const gsLevel of entry.gsLevels) {
        if (!isSupportedGradeLevel(system, gsLevel)) {
          continue;
        }
        levelCounts.set(gsLevel, (levelCounts.get(gsLevel) || 0) + 1);
      }
    }
    for (const location of entry.locations) {
      locationCounts.set(location, (locationCounts.get(location) || 0) + 1);
    }
    if (entry.securityClearance) {
      securityClearanceCounts.set(entry.securityClearance, (securityClearanceCounts.get(entry.securityClearance) || 0) + 1);
    }
  }
  const gsLevelOptions = [...gsLevelCounts.entries()]
    .sort((a, b) => a[0] - b[0]);
  const clLevelOptions = [...clLevelCounts.entries()]
    .sort((a, b) => a[0] - b[0]);
  const gsBounds = getGsBoundsFromLevels(gsLevelOptions.map(([gsLevel]) => gsLevel));
  const clBounds = getGsBoundsFromLevels(clLevelOptions.map(([gsLevel]) => gsLevel));
  const activeGsRange = getActiveRange(gsBounds, 'gsMin', 'gsMax');
  const activeClRange = getActiveRange(clBounds, 'clMin', 'clMax');
  const locationOptions = [...locationCounts.entries()]
    .sort((a, b) => (b[1] - a[1]) || a[0].localeCompare(b[0]))
    .slice(0, 200);
  const securityClearanceOptions = [...securityClearanceCounts.entries()]
    .sort((a, b) => (b[1] - a[1]) || a[0].localeCompare(b[0]));
  const remoteCount = baseEntries.filter((entry) => entry.remoteEligible).length;
  const onsiteCount = Math.max(0, baseEntries.length - remoteCount);

  categoryTableBody.innerHTML = `
    <div class="category-advanced-filters">
      ${buildGradeHistogramMarkup('GS', gsLevelOptions, activeGsRange) || '<p class="advanced-filter-meta">No GS level data available in this filtered set.</p>'}
      ${buildGradeHistogramMarkup('CL', clLevelOptions, activeClRange) || '<p class="advanced-filter-meta">No CL level data available in this filtered set.</p>'}
      <div class="advanced-filter-group">
        <label class="advanced-filter-label" for="location-filter-select">Location</label>
        <select id="location-filter-select" class="advanced-filter-select">
          <option value="">All locations</option>
          ${locationOptions.map(([location, count]) => `
            <option value="${escapeHtml(location)}"${location === advancedFilters.location ? ' selected' : ''}>
              ${escapeHtml(location)} (${count.toLocaleString()})
            </option>
          `).join('')}
        </select>
      </div>
      <div class="advanced-filter-group">
        <span class="advanced-filter-label">Security Clearance</span>
        <div class="advanced-filter-chips">
          <button type="button" class="advanced-filter-chip${advancedFilters.securityClearance === '' ? ' active' : ''}" data-security-clearance="">Any (${baseEntries.length.toLocaleString()})</button>
          ${securityClearanceOptions.map(([value, count]) => `
            <button type="button" class="advanced-filter-chip${value === advancedFilters.securityClearance ? ' active' : ''}" data-security-clearance="${escapeHtml(value)}">
              ${escapeHtml(value)} (${count.toLocaleString()})
            </button>
          `).join('')}
        </div>
      </div>
      <div class="advanced-filter-group">
        <span class="advanced-filter-label">Remote Eligible</span>
        <div class="advanced-filter-chips">
          <button type="button" class="advanced-filter-chip${advancedFilters.remoteMode === 'all' ? ' active' : ''}" data-remote-mode="all">Any (${baseEntries.length.toLocaleString()})</button>
          <button type="button" class="advanced-filter-chip${advancedFilters.remoteMode === 'remote' ? ' active' : ''}" data-remote-mode="remote">Remote Eligible (${remoteCount.toLocaleString()})</button>
          <button type="button" class="advanced-filter-chip${advancedFilters.remoteMode === 'onsite' ? ' active' : ''}" data-remote-mode="onsite">Not Remote (${onsiteCount.toLocaleString()})</button>
        </div>
      </div>
      <p class="advanced-filter-meta">These filters apply on top of agency, category, open-status, and keyword search.</p>
      <button type="button" class="advanced-filter-reset" id="advanced-filter-reset">Clear extra filters</button>
    </div>
  `;
}

function syncCategoryPanelMode() {
  const isFiltersOpen = categoryPanelMode === 'filters';
  categoryColumn.classList.toggle('filters-open', isFiltersOpen);
  categoryModeToggle.setAttribute('aria-expanded', String(isFiltersOpen));
  const label = categoryModeToggle.querySelector('.panel-mode-label');
  if (label) {
    label.textContent = isFiltersOpen ? 'Additional Filters' : 'Category / Hiring Path';
  }
  renderCategoryTable();
}

function resetAdvancedFilters() {
  advancedFilters = {
    gsMin: '',
    gsMax: '',
    clMin: '',
    clMax: '',
    location: '',
    securityClearance: '',
    remoteMode: 'all'
  };
}

function renderLinks(items) {
  if (!items || !items.length) {
    return 'N/A';
  }
  return items.map((item) => {
    const label = item.name || item.label || item.url;
    return `<a href="${escapeHtml(item.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(label)}</a>`;
  }).join('<br>');
}

function renderBillModal(bill) {
  const fields = [
    ['USAJOBS ID', bill.job_id],
    ['Position ID', bill.position_id],
    ['Title', bill.title],
    ['Summary', bill.summary],
    ['Status', bill.status],
    ['Agency', bill.agency],
    ['Organization', bill.organization_name],
    ['Department', bill.department_name],
    ['Published', formatDateTime(bill.publication_date)],
    ['Closes', formatDateTime(bill.close_date)],
    ['Location', bill.location_display],
    ['All Locations', bill.locations],
    ['Who May Apply', bill.who_may_apply],
    ['Salary', bill.salary_summary],
    ['Schedule', bill.position_schedule],
    ['Remote', bill.remote_indicator ? 'Yes' : 'No'],
    ['Telework Eligible', bill.telework_eligible],
    ['Categories', bill.categories],
    ['Hiring Paths', bill.hiring_paths],
    ['Major Duties', bill.major_duties],
    ['Qualifications', bill.qualification_summary],
    ['Requirements', bill.requirements],
    ['Required Documents', bill.required_documents],
    ['Benefits', bill.benefits],
    ['How To Apply', bill.how_to_apply]
  ];

  billModalTitle.textContent = bill.position_id
    ? `${bill.position_id} Details`
    : 'Job Details';
  billModalContent.innerHTML = `
    <table class="bill-detail-table">
      <tbody>
        ${fields.map(([label, value]) => `
          <tr>
            <th>${escapeHtml(label)}</th>
            <td>${escapeHtml(stringifyValue(value))}</td>
          </tr>
        `).join('')}
        <tr>
          <th>Job Detail</th>
          <td>${getJobNavigationUrl(bill) ? `<a href="${escapeHtml(getJobNavigationUrl(bill))}" target="_blank" rel="noopener noreferrer">Open USAJOBS listing</a>` : 'N/A'}</td>
        </tr>
        <tr>
          <th>Apply Link</th>
          <td>${getJobNavigationUrl(bill) ? `<a href="${escapeHtml(getJobNavigationUrl(bill))}" target="_blank" rel="noopener noreferrer">View official application instructions</a>` : 'N/A'}</td>
        </tr>
      </tbody>
    </table>
  `;
}

function openBillModal(bill) {
  renderBillModal(bill);
  billModal.classList.add('open');
  billModalClose.focus();
}

function closeBillModal() {
  billModal.classList.remove('open');
}

function buildSponsorHoverMarkup(name) {
  const entries = preparedBills.filter((entry) => entry.sponsor === name);
  const openCount = entries.filter((entry) => String(entry.bill.status || '').toLowerCase() === 'open').length;
  const locations = [...new Set(entries.map((entry) => entry.bill.location_display).filter(Boolean))].slice(0, 6);
  return `
    <p class="hover-card-kicker">Agency</p>
    <h3>${escapeHtml(name)}</h3>
    <p class="hover-card-meta">Jobs: ${entries.length.toLocaleString()}</p>
    <p class="hover-card-meta">Open now: ${openCount.toLocaleString()}</p>
    ${locations.length ? `<p class="hover-card-meta">Locations: ${escapeHtml(locations.join(' | '))}</p>` : ''}
  `;
}

function buildCategoryHoverMarkup(name) {
  const entries = preparedBills.filter((entry) => (entry.categories.length ? entry.categories : ['Uncategorized']).includes(name));
  const items = entries.slice(0, 6).map((entry) => ({
    fileNumber: entry.bill.position_id || entry.bill.job_id || 'N/A',
    title: entry.bill.title || 'Untitled job',
    hearing: formatDateTime(entry.bill.close_date) || 'No close date listed'
  }));
  return `
    <p class="hover-card-kicker">Category</p>
    <h3>${escapeHtml(name)}</h3>
    <p class="hover-card-meta">Records: ${entries.length.toLocaleString()}</p>
    ${items.length ? `
      <p class="hover-card-meta hover-card-meta-accent">Sample items</p>
      <ul class="hover-card-list">
        ${items.map((item) => `
          <li>
            <span class="hover-card-list-file">${escapeHtml(item.fileNumber)}</span>
            <span class="hover-card-list-title">${escapeHtml(item.title)}</span>
            <span class="hover-card-list-meta">${escapeHtml(item.hearing)}</span>
          </li>
        `).join('')}
      </ul>
    ` : ''}
  `;
}

function buildGradeHistogramHoverMarkup(system, level) {
  const numericLevel = Number.parseInt(String(level || ''), 10);
  if (Number.isNaN(numericLevel)) {
    return '';
  }
  const levelDescription = describeGradeLevel(system, numericLevel);
  const entries = getBaseFilteredEntries()
    .filter((entry) => entry.payPlan === system && entry.gsLevels.includes(numericLevel));
  const agencies = [...new Set(entries.map((entry) => entry.sponsor).filter(Boolean))].slice(0, 5);
  const items = entries.slice(0, 6).map((entry) => ({
    fileNumber: entry.bill.position_id || entry.bill.job_id || 'N/A',
    title: entry.bill.title || 'Untitled job',
    agency: entry.sponsor || 'Unknown agency'
  }));
  return `
    <p class="hover-card-kicker">${escapeHtml(system)} Level</p>
    <h3>${escapeHtml(formatGradeLevel(system, numericLevel))}</h3>
    <p class="hover-card-meta">Jobs: ${entries.length.toLocaleString()}</p>
    ${levelDescription ? `<p class="hover-card-meta">${escapeHtml(levelDescription)}</p>` : ''}
    ${agencies.length ? `<p class="hover-card-meta">Agencies: ${escapeHtml(agencies.join(' | '))}</p>` : ''}
    ${items.length ? `
      <p class="hover-card-meta hover-card-meta-accent">Sample jobs</p>
      <ul class="hover-card-list">
        ${items.map((item) => `
          <li>
            <span class="hover-card-list-file">${escapeHtml(item.fileNumber)}</span>
            <span class="hover-card-list-title">${escapeHtml(item.title)}</span>
            <span class="hover-card-list-meta">${escapeHtml(item.agency)}</span>
          </li>
        `).join('')}
      </ul>
    ` : ''}
  `;
}

function buildBillHoverMarkup(bill) {
  const hearingLabel = formatDateTime(bill.close_date) || 'No close date listed';
  const salaryLabel = formatBillSalary(bill);
  return `
    <p class="hover-card-kicker">USAJOBS Listing</p>
    <h3>${escapeHtml(bill.position_id || bill.job_id || 'N/A')} ${escapeHtml(bill.title || '')}</h3>
    <p class="hover-card-meta">Agency: ${escapeHtml(bill.agency || 'Unknown agency')}</p>
    <p class="hover-card-meta">Status: ${escapeHtml(bill.status || 'Status unavailable')}</p>
    <p class="hover-card-meta">Closes: ${escapeHtml(hearingLabel)}</p>
    ${salaryLabel ? `<p class="hover-card-meta">Salary: ${escapeHtml(salaryLabel)}</p>` : ''}
    ${bill.location_display ? `<p class="hover-card-meta hover-card-meta-accent">Location: ${escapeHtml(bill.location_display)}</p>` : ''}
    ${bill.summary ? `<p>${escapeHtml(bill.summary)}</p>` : ''}
  `;
}

function positionHoverCard(clientX, clientY) {
  const rect = hoverCard.getBoundingClientRect();
  let left = clientX + 12;
  let top = clientY + 12;
  if (left + rect.width > window.innerWidth - 8) {
    left = clientX - rect.width - 12;
  }
  if (top + rect.height > window.innerHeight - 8) {
    top = clientY - rect.height - 12;
  }
  hoverCard.style.left = `${Math.max(8, left)}px`;
  hoverCard.style.top = `${Math.max(8, top)}px`;
}

function positionLeftOverlayCard() {
  const left = 10;
  const top = 84;
  const height = Math.max(220, window.innerHeight - top - 10);
  hoverCard.style.left = `${left}px`;
  hoverCard.style.top = `${top}px`;
  hoverCard.style.height = `${height}px`;
  hoverCard.style.maxHeight = `${height}px`;
}

function positionRightOverlayCard() {
  const top = 84;
  const gap = 10;
  const width = Math.min(Math.max(window.innerWidth * 0.5, 380), 760);
  const left = Math.max(10, window.innerWidth - width - gap);
  const height = Math.max(220, window.innerHeight - top - 10);
  hoverCard.style.left = `${left}px`;
  hoverCard.style.top = `${top}px`;
  hoverCard.style.height = `${height}px`;
  hoverCard.style.maxHeight = `${height}px`;
}

function showHoverCard(markup, clientX, clientY) {
  const nextMarkup = `<div class="hover-card-content">${markup}</div>`;
  if (hoverCard.classList.contains('open') && hoverCard.innerHTML !== nextMarkup) {
    window.clearTimeout(hoverSwapTimer);
    const preserveLeftOverlay = hoverCard.classList.contains('left-overlay');
    const preserveRightOverlay = hoverCard.classList.contains('right-overlay');
    hoverCard.classList.add('is-swapping');
    hoverSwapTimer = window.setTimeout(() => {
      hoverCard.innerHTML = nextMarkup;
      hoverCard.classList.remove('is-swapping');
      if (preserveLeftOverlay) {
        hoverCard.classList.add('left-overlay');
        hoverCard.classList.remove('right-overlay');
        positionLeftOverlayCard();
      } else if (preserveRightOverlay) {
        hoverCard.classList.add('right-overlay');
        hoverCard.classList.remove('left-overlay');
        positionRightOverlayCard();
      } else {
        positionHoverCard(clientX, clientY);
      }
    }, 60);
  } else {
    hoverCard.innerHTML = nextMarkup;
    hoverCard.classList.remove('left-overlay', 'right-overlay');
    hoverCard.style.height = '';
    hoverCard.style.maxHeight = '';
  }
  hoverCard.classList.add('open');
  hoverCard.setAttribute('aria-hidden', 'false');
  if (!hoverCard.classList.contains('left-overlay') && !hoverCard.classList.contains('right-overlay')) {
    positionHoverCard(clientX, clientY);
  }
}

function showSponsorHover(name, side = 'right') {
  showHoverCard(buildSponsorHoverMarkup(name), 14, 120);
  if (side === 'left') {
    hoverCard.classList.add('left-overlay');
    positionLeftOverlayCard();
    return;
  }
  hoverCard.classList.add('right-overlay');
  positionRightOverlayCard();
}

function showCategoryHover(name) {
  showHoverCard(buildCategoryHoverMarkup(name), 14, 120);
  hoverCard.classList.add('right-overlay');
  positionRightOverlayCard();
}

function showGradeHistogramHover(system, level) {
  showHoverCard(buildGradeHistogramHoverMarkup(system, level), 14, 120);
  hoverCard.classList.add('right-overlay');
  positionRightOverlayCard();
}

function showBillHover(bill) {
  showHoverCard(buildBillHoverMarkup(bill), 14, 120);
  hoverCard.classList.add('left-overlay');
  positionLeftOverlayCard();
}

function hideHoverCard() {
  window.clearTimeout(hoverSwapTimer);
  hoverCard.classList.remove('open', 'is-swapping', 'left-overlay', 'right-overlay');
  hoverCard.style.height = '';
  hoverCard.style.maxHeight = '';
  hoverCard.setAttribute('aria-hidden', 'true');
}

function pointerLeftElement(event, selector) {
  const current = event.target.closest(selector);
  if (!current) {
    return false;
  }
  const related = event.relatedTarget;
  return !related || !current.contains(related);
}

function updateActiveSponsor(nextSponsor) {
  activeSponsor = activeSponsor === nextSponsor ? '' : nextSponsor;
  renderSponsorTable();
  renderCategoryTable();
  renderBills();
  persistFilters();
  updateSearchClearButtons();
}

function updateActiveCategory(nextCategory) {
  activeCategory = activeCategory === nextCategory ? '' : nextCategory;
  renderCategoryTable();
  renderBills();
  persistFilters();
  updateSearchClearButtons();
}

function resetFilters() {
  billFilterInput.value = '';
  sponsorFilterInput.value = '';
  categoryFilterInput.value = '';
  activeSponsor = '';
  activeCategory = '';
  showUpcomingOnly = true;
  categoryPanelMode = 'categories';
  resetAdvancedFilters();
  upcomingOnlyToggle.checked = true;
  clearPersistedFilters();
  updateSearchClearButtons();
  renderSponsorTable();
  syncCategoryPanelMode();
  renderBills();
}

async function loadData() {
  if (typeof DecompressionStream !== 'undefined') {
    const response = await fetch(DATA_URL, { cache: 'no-store' });
    if (response.ok && response.body) {
      const stream = response.body.pipeThrough(new DecompressionStream('gzip'));
      const text = await new Response(stream).text();
      return JSON.parse(text);
    }
  }

  const fallbackResponse = await fetch(FALLBACK_DATA_URL, { cache: 'no-store' });
  if (!fallbackResponse.ok) {
    throw new Error(`Failed to load ${FALLBACK_DATA_URL}: ${fallbackResponse.status}`);
  }
  return fallbackResponse.json();
}

function applyPersistedState(records, payload) {
  allBills = records;
  preparedBills = buildPreparedBills(records);
  resetFilterCache();
  sponsorProfiles = new Map();

  const persisted = loadPersistedFilters();
  billFilterInput.value = persisted.billQuery;
  sponsorFilterInput.value = persisted.sponsorQuery;
  categoryFilterInput.value = persisted.categoryQuery;
  activeSponsor = persisted.sponsor;
  activeCategory = persisted.category;
  showUpcomingOnly = persisted.upcomingOnly;
  categoryPanelMode = persisted.categoryPanelMode;
  advancedFilters = {
    gsMin: persisted.gsMin,
    gsMax: persisted.gsMax,
    clMin: persisted.clMin,
    clMax: persisted.clMax,
    location: persisted.location,
    securityClearance: persisted.securityClearance,
    remoteMode: persisted.remoteMode
  };
  upcomingOnlyToggle.checked = showUpcomingOnly;

  const sponsorSet = new Set(preparedBills.map((entry) => entry.sponsor));
  if (activeSponsor && !sponsorSet.has(activeSponsor)) {
    activeSponsor = '';
  }

  billUpdated.textContent = payload.fetched_at ? `Data retrieved ${formatDateTime(payload.fetched_at)}` : 'Retrieval date unavailable';

  renderSponsorTable();
  syncCategoryPanelMode();
  renderBills();
  updateSortIndicators();
  updateSearchClearButtons();
}

function getGridPanels() {
  return [
    document.getElementById('sponsor-column'),
    document.getElementById('category-column'),
    document.getElementById('bills-column')
  ];
}

function applyGridWidths(widths) {
  if (!insightsGrid || window.innerWidth <= 700 || !Array.isArray(widths) || widths.length !== 3) {
    return;
  }
  insightsGrid.style.gridTemplateColumns = [
    `${Math.round(widths[0])}px`,
    '14px',
    `${Math.round(widths[1])}px`,
    '14px',
    `${Math.round(widths[2])}px`
  ].join(' ');
}

function syncGridWidthsFromLayout() {
  if (!insightsGrid || window.innerWidth <= 700) {
    return;
  }
  const panels = getGridPanels();
  if (panels.some((panel) => !panel)) {
    return;
  }
  const widths = panels.map((panel) => panel.getBoundingClientRect().width);
  applyGridWidths(widths);
}

function initializeGridWidths() {
  if (!insightsGrid) {
    return;
  }
  if (window.innerWidth <= 700) {
    insightsGrid.style.gridTemplateColumns = '';
    return;
  }
  const persisted = loadPersistedGridWidths();
  if (persisted && persisted.length === 3) {
    applyGridWidths(persisted);
  } else {
    syncGridWidthsFromLayout();
  }
}

function stopGridResize() {
  if (!gridResizeState) {
    return;
  }
  gridResizeState.handle.classList.remove('resizing');
  document.body.classList.remove('is-resizing-columns');
  window.removeEventListener('mousemove', handleGridResizeMove);
  window.removeEventListener('mouseup', stopGridResize);
  persistGridWidths(gridResizeState.widths);
  gridResizeState = null;
}

function handleGridResizeMove(event) {
  if (!gridResizeState) {
    return;
  }
  const delta = event.clientX - gridResizeState.startX;
  const nextWidths = [...gridResizeState.startWidths];
  const leftIndex = gridResizeState.leftIndex;
  const rightIndex = gridResizeState.rightIndex;
  const proposedLeft = gridResizeState.startWidths[leftIndex] + delta;
  const proposedRight = gridResizeState.startWidths[rightIndex] - delta;
  nextWidths[leftIndex] = Math.max(gridResizeState.minWidth, proposedLeft);
  nextWidths[rightIndex] = Math.max(gridResizeState.minWidth, proposedRight);

  const totalPair = gridResizeState.startWidths[leftIndex] + gridResizeState.startWidths[rightIndex];
  if (nextWidths[leftIndex] + nextWidths[rightIndex] !== totalPair) {
    if (nextWidths[leftIndex] === gridResizeState.minWidth) {
      nextWidths[rightIndex] = totalPair - nextWidths[leftIndex];
    } else if (nextWidths[rightIndex] === gridResizeState.minWidth) {
      nextWidths[leftIndex] = totalPair - nextWidths[rightIndex];
    }
  }

  gridResizeState.widths = nextWidths;
  applyGridWidths(nextWidths);
}

function startGridResize(event) {
  const handle = event.target.closest('[data-grid-resize]');
  if (!handle || !insightsGrid || window.innerWidth <= 700) {
    return;
  }
  event.preventDefault();
  const currentWidths = getGridPanels().map((panel) => panel.getBoundingClientRect().width);
  const leftIndex = handle.dataset.gridResize === 'sponsor' ? 0 : 1;
  const rightIndex = leftIndex + 1;
  gridResizeState = {
    handle,
    startX: event.clientX,
    startWidths: currentWidths,
    widths: currentWidths,
    leftIndex,
    rightIndex,
    minWidth: 220
  };
  handle.classList.add('resizing');
  document.body.classList.add('is-resizing-columns');
  window.addEventListener('mousemove', handleGridResizeMove);
  window.addEventListener('mouseup', stopGridResize);
}

function getResizableHeaders() {
  return [...document.querySelectorAll('.bills-table th.resizable')];
}

function syncTableColumnWidths() {
  if (!billsTable || !billsTableWrap) {
    return;
  }
  const headers = getResizableHeaders();
  if (!headers.length) {
    return;
  }
  const widths = headers.map((header) => header.getBoundingClientRect().width);
  headers.forEach((header, index) => {
    header.style.width = `${Math.round(widths[index])}px`;
  });
  const totalWidth = widths.reduce((sum, width) => sum + width, 0);
  const wrapWidth = billsTableWrap.getBoundingClientRect().width;
  billsTable.style.width = `${Math.round(Math.max(totalWidth, wrapWidth))}px`;
  billsTable.style.minWidth = '100%';
}

function stopColumnResize() {
  if (!resizeState) {
    return;
  }
  resizeState.handle.classList.remove('resizing');
  document.body.classList.remove('is-resizing-columns');
  window.removeEventListener('mousemove', handleColumnResizeMove);
  window.removeEventListener('mouseup', stopColumnResize);
  resizeState = null;
}

function handleColumnResizeMove(event) {
  if (!resizeState || !billsTable || !billsTableWrap) {
    return;
  }
  const delta = event.clientX - resizeState.startX;
  const nextPrimaryWidth = Math.max(
    resizeState.minPrimaryWidth,
    Math.min(resizeState.maxPrimaryWidth, resizeState.startPrimaryWidth + delta)
  );
  const nextSecondaryWidth = resizeState.combinedWidth - nextPrimaryWidth;
  resizeState.primaryHeader.style.width = `${Math.round(nextPrimaryWidth)}px`;
  resizeState.secondaryHeader.style.width = `${Math.round(nextSecondaryWidth)}px`;
  billsTable.style.width = `${Math.round(resizeState.tableWidth)}px`;
  billsTable.style.minWidth = '100%';
}

function startColumnResize(event) {
  const handle = event.target.closest('.resize-handle');
  if (!handle || !billsTable || !billsTableWrap) {
    return;
  }
  event.preventDefault();
  event.stopPropagation();
  const header = handle.closest('th');
  if (!header) {
    return;
  }
  syncTableColumnWidths();
  const headers = getResizableHeaders();
  const headerIndex = headers.indexOf(header);
  const nextHeader = headers[headerIndex + 1];
  if (!nextHeader) {
    return;
  }
  const primaryWidth = header.getBoundingClientRect().width;
  const secondaryWidth = nextHeader.getBoundingClientRect().width;
  const tableWidth = billsTableWrap.getBoundingClientRect().width;
  const minPrimaryWidth = Math.max(90, Math.min(primaryWidth, 120));
  const minSecondaryWidth = Math.max(90, Math.min(secondaryWidth, 120));
  resizeState = {
    handle,
    primaryHeader: header,
    secondaryHeader: nextHeader,
    startX: event.clientX,
    startPrimaryWidth: primaryWidth,
    combinedWidth: primaryWidth + secondaryWidth,
    minPrimaryWidth,
    maxPrimaryWidth: (primaryWidth + secondaryWidth) - minSecondaryWidth,
    tableWidth
  };
  handle.classList.add('resizing');
  document.body.classList.add('is-resizing-columns');
  window.addEventListener('mousemove', handleColumnResizeMove);
  window.addEventListener('mouseup', stopColumnResize);
}

async function init() {
  loadColumnFontSizes();
  initializeGridWidths();
  try {
    const payload = await loadData();
    const records = Array.isArray(payload.records) ? payload.records : [];
    applyPersistedState(records, payload);
  } catch (error) {
    console.error(error);
    billCount.textContent = 'No jobs loaded';
    statusMessage.textContent = 'Unable to load USAJOBS data.';
    billsTableBody.innerHTML = '<tr><td colspan="5">The local USAJOBS cache is missing or unreadable.</td></tr>';
  }
}

billFilterInput.addEventListener('input', () => {
  if (categoryPanelMode === 'filters') {
    renderCategoryTable();
  }
  renderBills();
  persistFilters();
  updateSearchClearButtons();
});
sponsorFilterInput.addEventListener('input', () => {
  renderSponsorTable();
  persistFilters();
  updateSearchClearButtons();
});
categoryFilterInput.addEventListener('input', () => {
  renderCategoryTable();
  persistFilters();
  updateSearchClearButtons();
});
upcomingOnlyToggle.addEventListener('change', () => {
  showUpcomingOnly = upcomingOnlyToggle.checked;
  if (categoryPanelMode === 'filters') {
    renderCategoryTable();
  }
  renderBills();
  persistFilters();
});
resetFiltersButton.addEventListener('click', resetFilters);
categoryModeToggle.addEventListener('click', () => {
  categoryPanelMode = categoryPanelMode === 'filters' ? 'categories' : 'filters';
  syncCategoryPanelMode();
  persistFilters();
});

document.addEventListener('click', (event) => {
  const clearButton = event.target.closest('.search-clear');
  if (clearButton) {
    const targetId = clearButton.dataset.clearTarget || '';
    const target = document.getElementById(targetId);
    if (target) {
      target.value = '';
      if (targetId === 'sponsor-filter') {
        activeSponsor = '';
        renderSponsorTable();
        renderCategoryTable();
        renderBills();
        persistFilters();
      } else if (targetId === 'category-filter') {
        activeCategory = '';
        renderCategoryTable();
        renderBills();
        persistFilters();
      }
      target.dispatchEvent(new Event('input', { bubbles: true }));
      target.focus();
    }
  }
});

sponsorTableBody.addEventListener('click', (event) => {
  const button = event.target.closest('.sponsor-button');
  if (button) {
    updateActiveSponsor(button.dataset.sponsor || '');
  }
});

categoryTableBody.addEventListener('click', (event) => {
  const gradeBar = event.target.closest('.advanced-filter-bar');
  if (gradeBar && gradeBar.dataset.gradeSystem !== undefined && gradeBar.dataset.gradeLevel !== undefined) {
    updateGradeRange(gradeBar.dataset.gradeSystem || '', gradeBar.dataset.gradeLevel || '');
    renderCategoryTable();
    renderBills();
    persistFilters();
    return;
  }
  const remoteChip = event.target.closest('.advanced-filter-chip');
  if (remoteChip && remoteChip.dataset.remoteMode !== undefined) {
    advancedFilters.remoteMode = remoteChip.dataset.remoteMode || 'all';
    renderCategoryTable();
    renderBills();
    persistFilters();
    return;
  }
  const securityClearanceChip = event.target.closest('.advanced-filter-chip');
  if (securityClearanceChip && securityClearanceChip.dataset.securityClearance !== undefined) {
    advancedFilters.securityClearance = securityClearanceChip.dataset.securityClearance || '';
    renderCategoryTable();
    renderBills();
    persistFilters();
    return;
  }
  const resetButton = event.target.closest('#advanced-filter-reset');
  if (resetButton) {
    resetAdvancedFilters();
    renderCategoryTable();
    renderBills();
    persistFilters();
    return;
  }
  const button = event.target.closest('.sponsor-button');
  if (button) {
    updateActiveCategory(button.dataset.category || '');
  }
});

categoryTableBody.addEventListener('change', (event) => {
  const locationSelect = event.target.closest('#location-filter-select');
  if (locationSelect) {
    advancedFilters.location = locationSelect.value || '';
    renderBills();
    persistFilters();
  }
});

billsTableBody.addEventListener('click', (event) => {
  const numberButton = event.target.closest('.bill-number-copy');
  if (numberButton) {
    copyTextToClipboard(numberButton.dataset.copyValue || '')
      .then((copied) => {
        if (copied) {
          showCopyToast(numberButton);
        }
      })
      .catch((error) => {
        console.error('Unable to copy position ID.', error);
      });
    return;
  }
  const sponsorButton = event.target.closest('.bill-sponsor-button');
  if (sponsorButton) {
    updateActiveSponsor(sponsorButton.dataset.sponsorName || '');
  }
});

for (const header of document.querySelectorAll('th.sortable')) {
  const applySort = () => {
    if (resizeState) {
      return;
    }
    const nextColumn = header.dataset.sort || 'title';
    if (sortColumn !== nextColumn) {
      sortColumn = nextColumn;
      sortDirection = 'asc';
    } else if (sortDirection === 'asc') {
      sortDirection = 'desc';
    } else if (sortDirection === 'desc') {
      sortColumn = '';
      sortDirection = '';
    } else {
      sortColumn = nextColumn;
      sortDirection = 'asc';
    }
    updateSortIndicators();
    renderBills();
  };
  header.addEventListener('click', applySort);
  header.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      applySort();
    }
  });
}

for (const handle of document.querySelectorAll('.resize-handle')) {
  handle.addEventListener('mousedown', startColumnResize);
}

for (const handle of document.querySelectorAll('[data-grid-resize]')) {
  handle.addEventListener('mousedown', startGridResize);
}

for (const button of document.querySelectorAll('.font-size-btn')) {
  button.addEventListener('click', () => {
    const column = button.dataset.column;
    const direction = button.dataset.action === 'up' ? 1 : -1;
    adjustColumnFontSize(column, direction);
  });
}

sponsorTableBody.addEventListener('mouseover', (event) => {
  const button = event.target.closest('.sponsor-button');
  if (button) {
    showSponsorHover(button.dataset.sponsor || '');
  }
});
sponsorTableBody.addEventListener('mouseout', (event) => {
  if (pointerLeftElement(event, '.sponsor-button')) {
    hideHoverCard();
  }
});
categoryTableBody.addEventListener('mouseover', (event) => {
  const gradeBar = event.target.closest('.advanced-filter-bar');
  if (gradeBar && gradeBar.dataset.gradeSystem !== undefined && gradeBar.dataset.gradeLevel !== undefined) {
    showGradeHistogramHover(gradeBar.dataset.gradeSystem || '', gradeBar.dataset.gradeLevel || '');
    return;
  }
  const button = event.target.closest('.sponsor-button');
  if (button) {
    showCategoryHover(button.dataset.category || '');
  }
});
categoryTableBody.addEventListener('mouseout', (event) => {
  if (pointerLeftElement(event, '.advanced-filter-bar') || pointerLeftElement(event, '.sponsor-button')) {
    hideHoverCard();
  }
});
billsTableBody.addEventListener('mouseover', (event) => {
  const sponsorButton = event.target.closest('.bill-sponsor-button');
  if (sponsorButton) {
    showSponsorHover(sponsorButton.dataset.sponsorName || '', 'left');
    return;
  }
  const rowButton = event.target.closest('.bill-title-button');
  if (!rowButton) {
    return;
  }
  const entry = preparedBills[Number(rowButton.dataset.billIndex)];
  if (entry) {
    showBillHover(entry.bill);
  }
});
billsTableBody.addEventListener('mouseout', (event) => {
  if (pointerLeftElement(event, '.bill-title-button') || pointerLeftElement(event, '.bill-sponsor-button')) {
    hideHoverCard();
  }
});
sponsorTableBody.addEventListener('mouseleave', hideHoverCard);
categoryTableBody.addEventListener('mouseleave', hideHoverCard);
billsTableBody.addEventListener('mouseleave', hideHoverCard);

window.addEventListener('resize', () => {
  initializeGridWidths();
  if (!hoverCard.classList.contains('open')) {
    return;
  }
  if (hoverCard.classList.contains('left-overlay')) {
    positionLeftOverlayCard();
  } else if (hoverCard.classList.contains('right-overlay')) {
    positionRightOverlayCard();
  }
});

billModalClose.addEventListener('click', closeBillModal);
billModal.addEventListener('click', (event) => {
  if (event.target === billModal) {
    closeBillModal();
  }
});
document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape') {
    hideHoverCard();
    closeBillModal();
  }
});

init();
