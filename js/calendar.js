// Store all events globally
let allEvents = [];
let filteredEvents = [];
let rawEvents = [];
let eventGroups = new Set();
let calendar;
let currentView = 'dayGridMonth';
let isMobile = false;
let forceCardView = false;
let activeTagSlugs = new Set();
let calendarDisplayEvents = [];
let hoverPreviewPanel = null;
let eventInfoModal = null;
let showExcludedEvents = false;
let textSearchQuery = '';
let searchUrlSyncTimer = null;
let filterApplyTimer = null;
let useLocalTime = true;
let selectedTimeZone = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
let dayImageByDate = new Map();
let geocodeLookupCache = {};
let proximityFilter = {
  query: '',
  radiusMiles: 25,
  center: null,
  pending: false,
  error: ''
};
let timeFilter = {
  dateFrom: '',
  dateTo: '',
  timeStart: '',
  timeEnd: ''
};
let advancedFilterApplyTimer = null;
let proximityResolutionSequence = 0;
const remoteZipLookupCache = new Map();
const calendarSearchBlobCache = new WeakMap();
const rawSearchBlobCache = new WeakMap();
const TIMEZONE_PREFS_KEY = 'calendarTimezonePrefs';
const filterUtils = window.CalendarFilterUtils || null;
const SEARCH_QUERY_PARAM = 'q';
const PROXIMITY_QUERY_PARAM = 'near';
const RADIUS_QUERY_PARAM = 'radius';
const DATE_FROM_QUERY_PARAM = 'from';
const DATE_TO_QUERY_PARAM = 'to';
const TIME_START_QUERY_PARAM = 'start';
const TIME_END_QUERY_PARAM = 'end';
const LEGEND_MAP_QUERY_PARAM = 'lm';
const LEGEND_TAGS_QUERY_PARAM = 'lt';
const LEGEND_EXCLUDED_QUERY_PARAM = 'lx';
const LEGEND_HIDDEN_QUERY_PARAM = 'lh';
const LEGEND_TAG_COLORS_QUERY_PARAM = 'lc';
const LEGEND_DAY_IMAGES_QUERY_PARAM = 'li';
const LEGEND_CLICK_ACTION_QUERY_PARAM = 'la';
const LEGEND_TAGS_SEPARATOR = '.';
const FEATURED_SOURCE_URLS = new Set([
  'https://luma.com/codecollective',
  'https://lu.ma/codecollective'
]);
const CATEGORY_MAPS_INDEX_URL = window.CALENDAR_CATEGORY_MAPS_INDEX_URL || '/data/category_maps/index.json';
const DEFAULT_CATEGORY_MAP_ID = window.CALENDAR_DEFAULT_CATEGORY_MAP || 'community_sectors';
const LEGEND_PREFS_KEY = 'calendarLegendPrefs';
const IMAGE_PREFETCH_LIMIT = 24;
let categoryMapConfig = { default_map: DEFAULT_CATEGORY_MAP_ID, maps: [] };
let activeCategoryMap = null;

function parseBooleanQueryFlag(value) {
  if (value == null) return null;
  const normalized = String(value).trim().toLowerCase();
  if (normalized === '1' || normalized === 'true' || normalized === 'yes' || normalized === 'on') return true;
  if (normalized === '0' || normalized === 'false' || normalized === 'no' || normalized === 'off') return false;
  return null;
}

function parseCompactTagList(rawValue) {
  if (!rawValue) return [];
  return String(rawValue)
    .split(LEGEND_TAGS_SEPARATOR)
    .map(value => value.trim())
    .filter(Boolean);
}

function serializeCompactTagList(tags) {
  return Array.isArray(tags) ? tags.filter(Boolean).join(LEGEND_TAGS_SEPARATOR) : '';
}

function getLegendQueryStateFromUrl() {
  const params = new URLSearchParams(window.location.search);
  const clickAction = (params.get(LEGEND_CLICK_ACTION_QUERY_PARAM) || '').trim();
  return {
    mapId: (params.get(LEGEND_MAP_QUERY_PARAM) || '').trim() || null,
    selectedTags: parseCompactTagList(params.get(LEGEND_TAGS_QUERY_PARAM)),
    showExcludedEvents: parseBooleanQueryFlag(params.get(LEGEND_EXCLUDED_QUERY_PARAM)),
    hidden: parseBooleanQueryFlag(params.get(LEGEND_HIDDEN_QUERY_PARAM)),
    useTagColors: parseBooleanQueryFlag(params.get(LEGEND_TAG_COLORS_QUERY_PARAM)),
    showDayBackgrounds: parseBooleanQueryFlag(params.get(LEGEND_DAY_IMAGES_QUERY_PARAM)),
    eventClickAction: clickAction || null
  };
}

function syncLegendStateToUrl(state) {
  if (!window.history || typeof window.history.replaceState !== 'function') return;
  const url = new URL(window.location.href);
  const nextState = state || {};

  if (nextState.mapId) url.searchParams.set(LEGEND_MAP_QUERY_PARAM, String(nextState.mapId));
  else url.searchParams.delete(LEGEND_MAP_QUERY_PARAM);

  const tagList = serializeCompactTagList(nextState.selectedTags || []);
  if (tagList) url.searchParams.set(LEGEND_TAGS_QUERY_PARAM, tagList);
  else url.searchParams.delete(LEGEND_TAGS_QUERY_PARAM);

  if (typeof nextState.showExcludedEvents === 'boolean') {
    url.searchParams.set(LEGEND_EXCLUDED_QUERY_PARAM, nextState.showExcludedEvents ? '1' : '0');
  } else {
    url.searchParams.delete(LEGEND_EXCLUDED_QUERY_PARAM);
  }

  if (typeof nextState.hidden === 'boolean') {
    url.searchParams.set(LEGEND_HIDDEN_QUERY_PARAM, nextState.hidden ? '1' : '0');
  } else {
    url.searchParams.delete(LEGEND_HIDDEN_QUERY_PARAM);
  }

  if (typeof nextState.useTagColors === 'boolean') {
    url.searchParams.set(LEGEND_TAG_COLORS_QUERY_PARAM, nextState.useTagColors ? '1' : '0');
  } else {
    url.searchParams.delete(LEGEND_TAG_COLORS_QUERY_PARAM);
  }

  if (typeof nextState.showDayBackgrounds === 'boolean') {
    url.searchParams.set(LEGEND_DAY_IMAGES_QUERY_PARAM, nextState.showDayBackgrounds ? '1' : '0');
  } else {
    url.searchParams.delete(LEGEND_DAY_IMAGES_QUERY_PARAM);
  }

  if (nextState.eventClickAction) url.searchParams.set(LEGEND_CLICK_ACTION_QUERY_PARAM, String(nextState.eventClickAction));
  else url.searchParams.delete(LEGEND_CLICK_ACTION_QUERY_PARAM);

  window.history.replaceState({}, '', `${url.pathname}${url.search}${url.hash}`);
}

async function loadCategoryMapConfig() {
  try {
    const indexResponse = await fetch(CATEGORY_MAPS_INDEX_URL, { cache: 'no-store' });
    if (!indexResponse.ok) throw new Error(`Category map index HTTP ${indexResponse.status}`);

    const indexData = await indexResponse.json();
    const mapRefs = Array.isArray(indexData.maps) ? indexData.maps : [];
    if (mapRefs.length === 0) throw new Error('Category map index has no maps');

    const loadedMaps = await Promise.all(
      mapRefs.map(async (ref) => {
        if (!ref?.path) return null;
        const response = await fetch(ref.path, { cache: 'no-store' });
        if (!response.ok) throw new Error(`Category map ${ref.id || ref.path} HTTP ${response.status}`);
        const mapData = await response.json();
        return {
          ...mapData,
          id: mapData.id || ref.id,
          label: mapData.label || ref.label || mapData.id || 'Unnamed Map'
        };
      })
    );

    const maps = loadedMaps.filter(Boolean);
    if (maps.length === 0) throw new Error('No category maps could be loaded');

    return {
      default_map: indexData.default_map || maps[0].id,
      maps
    };
  } catch (error) {
    console.error('Failed to load category maps:', error);
    throw error;
  }
}

// Utility helpers ---------------------------------------------------------
function getTodayStart() {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return today;
}

function getDefaultUserTimeZone() {
  return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
}

function getActiveTimeZone() {
  return useLocalTime ? getDefaultUserTimeZone() : selectedTimeZone;
}

function getDatePartsInTimeZone(dateInput, timeZone = getActiveTimeZone()) {
  const date = dateInput instanceof Date ? dateInput : new Date(dateInput);
  if (isNaN(date)) return null;
  const formatter = new Intl.DateTimeFormat('en-CA', {
    timeZone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit'
  });
  const parts = formatter.formatToParts(date);
  const values = {};
  parts.forEach(part => {
    if (part.type !== 'literal') values[part.type] = part.value;
  });
  if (!values.year || !values.month || !values.day) return null;
  return values;
}

function getDateKeyInTimeZone(dateInput, timeZone = getActiveTimeZone()) {
  const values = getDatePartsInTimeZone(dateInput, timeZone);
  if (!values) return '';
  return `${values.year}-${values.month}-${values.day}`;
}

function formatDateWithTimeZone(dateInput, options) {
  const date = dateInput instanceof Date ? dateInput : new Date(dateInput);
  if (isNaN(date)) return '';
  const formatOptions = { ...options };
  if (!useLocalTime) {
    formatOptions.timeZone = selectedTimeZone;
  }
  return new Intl.DateTimeFormat('en-US', formatOptions).format(date);
}

function saveTimezonePrefs() {
  const payload = {
    useLocalTime: useLocalTime !== false,
    selectedTimeZone: selectedTimeZone || getDefaultUserTimeZone()
  };
  try {
    localStorage.setItem(TIMEZONE_PREFS_KEY, JSON.stringify(payload));
  } catch (error) {
    // Ignore storage failures.
  }
}

function loadTimezonePrefs() {
  const fallback = {
    useLocalTime: true,
    selectedTimeZone: getDefaultUserTimeZone()
  };
  try {
    const stored = localStorage.getItem(TIMEZONE_PREFS_KEY);
    if (!stored) return fallback;
    const parsed = JSON.parse(stored);
    return {
      useLocalTime: parsed.useLocalTime !== false,
      selectedTimeZone: String(parsed.selectedTimeZone || fallback.selectedTimeZone)
    };
  } catch (error) {
    return fallback;
  }
}

function getTimezoneOptions() {
  const defaults = [
    'UTC',
    'America/New_York',
    'America/Chicago',
    'America/Denver',
    'America/Los_Angeles',
    'Pacific/Honolulu',
    'America/Phoenix',
    'Europe/London',
    'Europe/Paris',
    'Europe/Berlin',
    'Asia/Tokyo',
    'Asia/Kolkata',
    'Australia/Sydney'
  ];
  const dynamic = (typeof Intl.supportedValuesOf === 'function')
    ? Intl.supportedValuesOf('timeZone')
    : [];
  const merged = new Set([...defaults, getDefaultUserTimeZone(), ...dynamic]);
  return Array.from(merged).sort((a, b) => a.localeCompare(b));
}

function refreshCalendarForTimezoneChange() {
  if (!allEvents.length) return;
  applyTagFilters();
  if (!isMobile) {
    destroyCalendar();
    initializeCalendar(calendarDisplayEvents);
    addTodayStyles();
    highlightToday();
  }
}

function setupTimezoneControls() {
  const checkbox = document.getElementById('use-local-time-checkbox');
  const select = document.getElementById('timezone-select');
  if (!checkbox || !select) return;

  const prefs = loadTimezonePrefs();
  useLocalTime = prefs.useLocalTime;
  selectedTimeZone = prefs.selectedTimeZone || getDefaultUserTimeZone();

  const timezoneOptions = getTimezoneOptions();
  select.innerHTML = timezoneOptions.map(tz => `<option value="${tz}">${tz}</option>`).join('');
  if (!timezoneOptions.includes(selectedTimeZone)) {
    const option = document.createElement('option');
    option.value = selectedTimeZone;
    option.textContent = selectedTimeZone;
    select.appendChild(option);
  }

  checkbox.checked = useLocalTime;
  select.value = selectedTimeZone;
  select.disabled = useLocalTime;

  checkbox.addEventListener('change', () => {
    useLocalTime = checkbox.checked;
    select.disabled = useLocalTime;
    saveTimezonePrefs();
    refreshCalendarForTimezoneChange();
  });

  select.addEventListener('change', () => {
    selectedTimeZone = select.value || getDefaultUserTimeZone();
    saveTimezonePrefs();
    if (!useLocalTime) {
      refreshCalendarForTimezoneChange();
    }
  });
}

// Compare only the calendar date so events stay visible all day
function isEventOnOrAfterToday(dateInput, todayStart = getTodayStart()) {
  if (!dateInput) return false;

  const eventDate = new Date(dateInput);
  if (isNaN(eventDate)) return false;
  const todayKey = getDateKeyInTimeZone(todayStart, getActiveTimeZone());
  const eventKey = getDateKeyInTimeZone(eventDate, getActiveTimeZone());
  if (!todayKey || !eventKey) return false;
  return eventKey >= todayKey;
}

// Check if device is mobile
function isMobileDevice() {
  return window.matchMedia('(max-width: 768px)').matches;
  //return false;
}

function slugifyTag(tag) {
  return String(tag || '')
    .toLowerCase()
    .replace(/&/g, 'and')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

function normalizeSourceUrl(url) {
  return String(url || '')
    .trim()
    .toLowerCase()
    .replace(/\/+$/, '');
}

function isFeaturedSource(url) {
  return FEATURED_SOURCE_URLS.has(normalizeSourceUrl(url));
}

function escapeHtml(value) {
  return String(value || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function escapeAttr(value) {
  return escapeHtml(value);
}

function safeUrl(url) {
  try {
    const parsed = new URL(String(url || ''), window.location.origin);
    if (parsed.protocol === 'http:' || parsed.protocol === 'https:') {
      return parsed.href;
    }
  } catch (error) {
    return '';
  }
  return '';
}

function getPreferredEventImage(eventLike) {
  if (!eventLike) return '';

  const directImage = eventLike.imageUrl || eventLike.orgImageUrl || '';
  if (typeof directImage === 'string' && directImage) {
    return directImage;
  }

  const extendedProps = eventLike.extendedProps || {};
  return extendedProps.imageUrl || extendedProps.orgImageUrl || '';
}

function getPreferredOrgImage(eventLike) {
  if (!eventLike) return '';
  const extendedProps = eventLike.extendedProps || {};
  const title = String(eventLike.title || eventLike.name || '').toLowerCase();
  const orgName = String(extendedProps.orgName || extendedProps.org_name || extendedProps.sourceGroup || '').toLowerCase();
  const source = String(extendedProps.source || extendedProps.source_url || '').toLowerCase();
  const orgImage = String(extendedProps.orgImageUrl || eventLike.orgImageUrl || '');

  const codeCollectiveSignal =
    title.includes('code collective') ||
    orgName.includes('code collective') ||
    source.includes('codecollective');
  if (codeCollectiveSignal) {
    return '/images/codecollective.webp';
  }
  return orgImage;
}

function sanitizeHtmlFragment(htmlString) {
  const parser = new DOMParser();
  const doc = parser.parseFromString(`<div>${htmlString || ''}</div>`, 'text/html');
  const root = doc.body.firstElementChild;
  if (!root) return '';

  const blockedTags = new Set(['script', 'style', 'iframe', 'object', 'embed', 'form']);
  const walker = doc.createTreeWalker(root, NodeFilter.SHOW_ELEMENT);
  const nodes = [];
  while (walker.nextNode()) {
    nodes.push(walker.currentNode);
  }

  nodes.forEach(node => {
    const tagName = node.tagName.toLowerCase();
    if (blockedTags.has(tagName)) {
      node.remove();
      return;
    }

    Array.from(node.attributes).forEach(attr => {
      const name = attr.name.toLowerCase();
      const value = attr.value || '';
      if (name.startsWith('on')) {
        node.removeAttribute(attr.name);
        return;
      }
      if ((name === 'href' || name === 'src') && !safeUrl(value)) {
        node.removeAttribute(attr.name);
        return;
      }
      if (name === 'style') {
        node.removeAttribute(attr.name);
      }
    });

    if (tagName === 'a') {
      node.setAttribute('target', '_blank');
      node.setAttribute('rel', 'noopener');
    }
  });

  return root.innerHTML;
}

function renderRichText(text) {
  const value = String(text || '').trim();
  if (!value) return '';

  const looksLikeHtml = /<\s*[a-z][\s\S]*>/i.test(value);
  if (looksLikeHtml) {
    return sanitizeHtmlFragment(value);
  }

  if (window.marked && typeof window.marked.parse === 'function') {
    return sanitizeHtmlFragment(marked.parse(value));
  }

  return `<p>${escapeHtml(value).replace(/\n+/g, '<br>')}</p>`;
}

function formatSourceLabel(url, fallback = 'Unknown source') {
  try {
    const parsed = new URL(url);
    const host = parsed.hostname.replace(/^www\./, '');
    const segments = parsed.pathname.split('/').filter(Boolean);

    if (host.includes('meetup.com') && segments[0]) {
      return segments[0].replace(/[-_]+/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
    }
    if ((host.includes('lu.ma') || host.includes('luma.com')) && parsed.pathname === '/user/profile/events-hosting') {
      return fallback;
    }
    if ((host.includes('lu.ma') || host.includes('luma.com')) && segments[0]) {
      return segments[segments.length - 1].replace(/[-_]+/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
    }
    if (host.includes('eventbrite.') && segments[0] === 'o' && segments[1]) {
      return segments[1].replace(/[-_]+/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
    }

    return host;
  } catch (error) {
    return fallback;
  }
}

function ensureHoverPreviewPanel() {
  if (hoverPreviewPanel) return hoverPreviewPanel;

  const panel = document.createElement('aside');
  panel.className = 'event-hover-panel';
  panel.setAttribute('hidden', '');
  panel.innerHTML = `
    <div class="event-hover-inner">
      <div class="event-hover-media-wrap" hidden>
        <img class="event-hover-media" alt="" />
      </div>
      <div class="event-hover-copy">
        <div class="event-hover-kicker"></div>
        <h3 class="event-hover-title"></h3>
        <div class="event-hover-source-row">
          <div class="event-hover-source-icon-wrap" hidden>
            <img class="event-hover-source-icon" alt="" />
          </div>
          <div class="event-hover-source"></div>
        </div>
        <div class="event-hover-location" hidden></div>
        <div class="event-hover-tags"></div>
        <div class="event-hover-description"></div>
      </div>
    </div>
  `;
  document.body.appendChild(panel);
  hoverPreviewPanel = panel;
  return panel;
}

function setHoverPanelSide(clientX) {
  const panel = ensureHoverPreviewPanel();
  const showOnLeft = clientX > (window.innerWidth / 2);
  panel.classList.toggle('align-left', showOnLeft);
  panel.classList.toggle('align-right', !showOnLeft);
}

function showHoverPreview(eventInfo, mouseEvent) {
  if (isMobile && !document.body.classList.contains('calendar-filter-page')) return;

  const panel = ensureHoverPreviewPanel();
  const event = eventInfo.event;
  const sourceUrl = event.extendedProps?.source || event.url || '';
  const sourceLabel = formatSourceLabel(sourceUrl, event.extendedProps?.sourceGroup || event.extendedProps?.group || 'Unknown source');
  const imageUrl = safeUrl(getPreferredEventImage(event));
  const orgImageUrl = safeUrl(getPreferredOrgImage(event));
  const mediaWrap = panel.querySelector('.event-hover-media-wrap');
  const media = panel.querySelector('.event-hover-media');
  const kicker = panel.querySelector('.event-hover-kicker');
  const title = panel.querySelector('.event-hover-title');
  const source = panel.querySelector('.event-hover-source');
  const sourceIconWrap = panel.querySelector('.event-hover-source-icon-wrap');
  const sourceIcon = panel.querySelector('.event-hover-source-icon');
  const location = panel.querySelector('.event-hover-location');
  const tags = panel.querySelector('.event-hover-tags');
  const description = panel.querySelector('.event-hover-description');
  const rawTags = Array.isArray(event.extendedProps?.tags) ? event.extendedProps.tags : [];
  const eventLocation = event.extendedProps?.location || event.location || null;
  const locationText = [
    eventLocation?.name,
    eventLocation?.address
  ]
    .filter(Boolean)
    .join(' · ');

  kicker.textContent = formatEventDate(event.start, event.end);
  title.textContent = event.title || 'Untitled';
  source.textContent = sourceLabel;
  if (orgImageUrl) {
    sourceIconWrap.hidden = false;
    sourceIcon.src = orgImageUrl;
    sourceIcon.alt = `${sourceLabel} logo`;
  } else {
    sourceIconWrap.hidden = true;
    sourceIcon.removeAttribute('src');
    sourceIcon.alt = '';
  }
  if (locationText) {
    location.hidden = false;
    location.textContent = locationText;
  } else {
    location.hidden = true;
    location.textContent = '';
  }
  tags.innerHTML = rawTags.map(tag => {
    const mapped = getMappedCategoriesForTags([tag])[0];
    const background = mapped?.color || '#334155';
    const textColor = mapped?.textColor || '#ffffff';
    return `<span class="event-hover-tag" style="--tag-chip-bg: ${escapeAttr(background)}; --tag-chip-fg: ${escapeAttr(textColor)};">${escapeHtml(tag)}</span>`;
  }).join('');
  description.innerHTML = renderRichText(event.extendedProps?.description || event.description || '');

  if (imageUrl) {
    mediaWrap.hidden = false;
    media.src = imageUrl;
    media.alt = event.title || 'Event image';
  } else {
    mediaWrap.hidden = true;
    media.removeAttribute('src');
    media.alt = '';
  }

  setHoverPanelSide(mouseEvent?.clientX || (window.innerWidth / 2));
  panel.removeAttribute('hidden');
  panel.classList.add('visible');
}

function hideHoverPreview() {
  if (!hoverPreviewPanel) return;
  hoverPreviewPanel.classList.remove('visible');
  hoverPreviewPanel.setAttribute('hidden', '');
}

function getCategoryMapById(mapId) {
  return (categoryMapConfig.maps || []).find(map => map.id === mapId) || (categoryMapConfig.maps || [])[0] || null;
}

function normalizeMapCategory(category) {
  return {
    label: category.label,
    color: category.color || '#475569',
    textColor: category.text_color || '#ffffff',
    slug: slugifyTag(category.label),
    matchSlugs: new Set((category.matches || []).map(slugifyTag).filter(Boolean))
  };
}

function getOtherCategory(categoryMap) {
  return (categoryMap?.categories || [])
    .map(normalizeMapCategory)
    .find(category => category.slug === 'other') || null;
}

function getMappedCategoriesForTags(tags, categoryMap = activeCategoryMap) {
  return getDirectMappedCategoriesForTags(tags, categoryMap);
}

function getDirectMappedCategoriesForTags(tags, categoryMap = activeCategoryMap) {
  const normalizedTags = Array.isArray(tags) ? tags.map(slugifyTag).filter(Boolean) : [];
  const mappedCategories = (categoryMap?.categories || [])
    .map(normalizeMapCategory)
    .filter(category => normalizedTags.some(tag => category.matchSlugs.has(tag)));

  if (mappedCategories.length > 0) {
    return mappedCategories;
  }

  const otherCategory = getOtherCategory(categoryMap);
  return otherCategory ? [otherCategory] : [];
}

function isTechOnlyEvent(tags) {
  if (filterUtils?.isTechOnlyEvent) {
    return filterUtils.isTechOnlyEvent(tags);
  }

  const normalizedTags = new Set((Array.isArray(tags) ? tags : []).map(slugifyTag).filter(Boolean));
  if (normalizedTags.size === 0) return false;

  const specificTechTags = new Set([
    'ai',
    'data-science',
    'cybersecurity',
    'cloud-and-platform',
    'devops',
    'software-development',
    'web-development',
    'javascript',
    'python',
    'ruby',
    'open-source',
    'technical-writing',
    'game-development',
    'ux',
    'product',
    'crypto-and-web3',
    'makerspace',
    'robotics',
    'civic-tech'
  ]);
  const genericTechTags = new Set([
    'tech-skills',
    'tech-community',
    'code-collective-and-partners'
  ]);
  const dominantNonTechTags = new Set([
    'water',
    'water-and-environment',
    'religion',
    'culture',
    'community',
    'politics',
    'food',
    'housing',
    'shelter-and-habitat',
    'clothing',
    'survival-and-health',
    'safety-and-stability',
    'belonging-and-culture',
    'purpose-and-service',
    'faith-and-spirituality',
    'business',
    'economic-development',
    'professional-networking',
    'career-growth',
    'startup',
    'waterfront',
    'infrastructure',
    'finance'
  ]);

  if (Array.from(normalizedTags).some(tag => specificTechTags.has(tag))) {
    return true;
  }

  if (!Array.from(normalizedTags).some(tag => genericTechTags.has(tag))) {
    return false;
  }

  if (Array.from(normalizedTags).some(tag => dominantNonTechTags.has(tag))) {
    return false;
  }

  return true;
}

function applyTagClasses(element, tags) {
  if (!element) return;

  element.classList.remove('tagged');
  element.style.removeProperty('--tag-color');
  element.style.removeProperty('--tag-text-color');

  if (element.classList.contains('source-codecollective-luma-title')) {
    return;
  }

  const primaryCategory = getMappedCategoriesForTags(tags)[0];
  if (!primaryCategory) return;

  element.classList.add('tagged');
  element.style.setProperty('--tag-color', primaryCategory.color);
  element.style.setProperty('--tag-text-color', primaryCategory.textColor);
}

function getLegendPrefs(categoryMap) {
  const defaultTags = Array.isArray(categoryMap?.categories)
    ? categoryMap.categories.map(category => slugifyTag(category.label))
    : [];
  const defaults = {
    hidden: true,
    useTagColors: true,
    showDayBackgrounds: true,
    showExcludedEvents: false,
    eventClickAction: 'open_page',
    selectedTags: defaultTags,
    mapId: categoryMap?.id || categoryMapConfig.default_map
  };

  let prefs = defaults;
  try {
    const stored = localStorage.getItem(LEGEND_PREFS_KEY);
    if (stored) {
      const parsed = JSON.parse(stored);
      prefs = {
        hidden: Boolean(parsed.hidden),
        useTagColors: parsed.useTagColors !== false,
        showDayBackgrounds: parsed.showDayBackgrounds !== false,
        showExcludedEvents: parsed.showExcludedEvents === true,
        eventClickAction: parsed.eventClickAction || defaults.eventClickAction,
        selectedTags: Array.isArray(parsed.selectedTags) ? parsed.selectedTags : defaultTags,
        mapId: parsed.mapId || defaults.mapId
      };
    }
  } catch (error) {
    prefs = defaults;
  }

  const queryState = getLegendQueryStateFromUrl();
  if (queryState.mapId) prefs.mapId = queryState.mapId;
  if (Array.isArray(queryState.selectedTags) && queryState.selectedTags.length > 0) prefs.selectedTags = queryState.selectedTags;
  if (typeof queryState.hidden === 'boolean') prefs.hidden = queryState.hidden;
  if (typeof queryState.useTagColors === 'boolean') prefs.useTagColors = queryState.useTagColors;
  if (typeof queryState.showDayBackgrounds === 'boolean') prefs.showDayBackgrounds = queryState.showDayBackgrounds;
  if (typeof queryState.showExcludedEvents === 'boolean') prefs.showExcludedEvents = queryState.showExcludedEvents;
  if (queryState.eventClickAction) prefs.eventClickAction = queryState.eventClickAction;

  return prefs;
}

function getValidSelectedTags(selectedTags, categoryMap) {
  const availableTags = new Set(
    Array.isArray(categoryMap?.categories)
      ? categoryMap.categories.map(category => slugifyTag(category.label))
      : []
  );

  const validTags = Array.isArray(selectedTags)
    ? selectedTags.filter(tag => availableTags.has(tag))
    : [];

  return validTags.length > 0 ? validTags : Array.from(availableTags);
}

function saveLegendPrefs() {
  const prefs = {
    hidden: document.body.classList.contains('legend-hidden'),
    useTagColors: !document.body.classList.contains('tags-disabled'),
    showDayBackgrounds: !document.body.classList.contains('day-backgrounds-disabled'),
    showExcludedEvents,
    eventClickAction: getEventClickAction(),
    selectedTags: Array.from(activeTagSlugs),
    mapId: activeCategoryMap?.id || categoryMapConfig.default_map
  };
  try {
    localStorage.setItem(LEGEND_PREFS_KEY, JSON.stringify(prefs));
  } catch (error) {
    // Ignore storage failures silently.
  }
  syncLegendStateToUrl(prefs);
}

function buildLegendItem(category, isChecked) {
  const item = document.createElement('label');
  item.className = 'legend-item';
  if (activeCategoryMap?.id === 'maslow_needs') {
    item.classList.add('legend-card');
  }
  item.innerHTML = `
    <input type="checkbox" data-tag="${category.slug}" ${isChecked ? 'checked' : ''} />
    <span class="legend-swatch" style="background-color: ${category.color}; color: ${category.textColor};"></span>
    <span class="legend-text">${category.label}</span>
  `;
  return item;
}

function buildMaslowLegendList(categories, activeSlugs) {
  const list = document.createElement('div');
  list.className = 'legend-list maslow-hierarchy';

  const rowDefs = [
    ['Purpose & Service'],
    ['Growth & Creativity'],
    ['Esteem & Opportunity'],
    ['Belonging & Culture'],
    ['Safety & Stability'],
    ['Food', 'Water', 'Shelter + Habitat', 'Clothing', 'Survival & Health']
  ];

  rowDefs.forEach((labels, index) => {
    const row = document.createElement('div');
    row.className = `legend-row legend-row-${index + 1}`;

    labels.forEach(label => {
      const category = categories.find(item => item.label === label);
      if (!category) return;
      const isChecked = activeSlugs.size === 0 ? true : activeSlugs.has(category.slug);
      row.appendChild(buildLegendItem(category, isChecked));
    });

    if (row.childElementCount > 0) {
      list.appendChild(row);
    }
  });

  return list;
}

function buildLegend(categoryMap, options = {}) {
  activeCategoryMap = categoryMap || getCategoryMapById(categoryMapConfig.default_map);
  if (!activeCategoryMap) {
    return;
  }
  let prefs = getLegendPrefs(activeCategoryMap);
  if (!options.lockMapId && prefs.mapId && prefs.mapId !== activeCategoryMap.id) {
    activeCategoryMap = getCategoryMapById(prefs.mapId);
    prefs = getLegendPrefs(activeCategoryMap);
  }

  const categories = activeCategoryMap.categories || [];
  activeTagSlugs = new Set(getValidSelectedTags(prefs.selectedTags, activeCategoryMap));
  showExcludedEvents = prefs.showExcludedEvents === true;

  const legendItems = document.getElementById('calendar-legend-items');
  if (!legendItems || !Array.isArray(categories)) {
    setTagFormattingEnabled(prefs.useTagColors);
    setLegendVisibility(prefs.hidden, { save: false });
    return;
  }

  legendItems.innerHTML = '';

  const controls = document.createElement('div');
  controls.className = 'legend-controls';
  const mapOptions = (categoryMapConfig.maps || [])
    .map(map => `<option value="${map.id}" ${map.id === activeCategoryMap.id ? 'selected' : ''}>${map.label}</option>`)
    .join('');
  controls.innerHTML = `
    <label class="legend-map-picker">
      <span class="legend-text">Lenses</span>
      <select id="legend-map-select">${mapOptions}</select>
    </label>
    <label class="legend-map-picker">
      <span class="legend-text">Click Action</span>
      <select id="legend-click-action-select">
        <option value="open_page" ${prefs.eventClickAction === 'open_page' ? 'selected' : ''}>Go to page</option>
        <option value="info_modal" ${prefs.eventClickAction === 'info_modal' ? 'selected' : ''}>Open info modal</option>
        <option value="copy_name" ${prefs.eventClickAction === 'copy_name' ? 'selected' : ''}>Copy name</option>
        <option value="copy_json" ${prefs.eventClickAction === 'copy_json' ? 'selected' : ''}>Copy event JSON</option>
      </select>
    </label>
    <label class="legend-item legend-toggle">
      <input type="checkbox" id="toggle-tag-formatting" ${prefs.useTagColors ? 'checked' : ''} />
      <span class="legend-text">Use tag colors</span>
    </label>
    <label class="legend-item legend-toggle">
      <input type="checkbox" id="toggle-day-backgrounds" ${prefs.showDayBackgrounds ? 'checked' : ''} />
      <span class="legend-text">Show day images</span>
    </label>
    <label class="legend-item legend-toggle legend-excluded-toggle">
      <input type="checkbox" id="toggle-excluded-events" ${showExcludedEvents ? 'checked' : ''} />
      <span class="legend-text">Show excluded in grey</span>
    </label>
    <div class="legend-actions">
      <button type="button" class="legend-action" data-action="all">Select all</button>
      <button type="button" class="legend-action" data-action="none">Select none</button>
      <button type="button" class="legend-action" data-action="hide">Hide legend</button>
    </div>
  `;
  legendItems.appendChild(controls);

  const normalizedCategories = categories.map(normalizeMapCategory);
  let list;

  if (activeCategoryMap.id === 'maslow_needs') {
    list = buildMaslowLegendList(normalizedCategories, activeTagSlugs);
  } else {
    list = document.createElement('div');
    list.className = 'legend-list';
    normalizedCategories.forEach(category => {
      const isChecked = activeTagSlugs.size === 0 ? true : activeTagSlugs.has(category.slug);
      list.appendChild(buildLegendItem(category, isChecked));
    });
  }

  legendItems.appendChild(list);

  legendItems.onchange = event => {
    if (event.target.matches('#legend-map-select')) {
      activeCategoryMap = getCategoryMapById(event.target.value);
      buildLegend(activeCategoryMap, { lockMapId: true });
      applyTagFilters();
      return;
    }
    if (event.target.matches('#legend-click-action-select')) {
      saveLegendPrefs();
      return;
    }
    if (event.target.matches('#toggle-tag-formatting')) {
      setTagFormattingEnabled(event.target.checked);
      saveLegendPrefs();
      return;
    }
    if (event.target.matches('#toggle-day-backgrounds')) {
      setDayBackgroundsEnabled(event.target.checked);
      saveLegendPrefs();
      refreshCalendarForVisualPreferenceChange();
      return;
    }
    if (event.target.matches('#toggle-excluded-events')) {
      showExcludedEvents = event.target.checked;
      applyTagFilters();
      return;
    }
    if (!event.target.matches('input[type="checkbox"][data-tag]')) return;
    updateActiveTagsFromLegend();
    applyTagFilters();
  };

  legendItems.onclick = event => {
    const actionBtn = event.target.closest('.legend-action');
    if (!actionBtn) return;
    const action = actionBtn.dataset.action;
    if (action === 'all') {
      setLegendCheckboxes(true);
    } else if (action === 'none') {
      setLegendCheckboxes(false);
    } else if (action === 'hide') {
      setLegendVisibility(true);
    }
  };

  const visibilityToggle = document.getElementById('legend-visibility-toggle');
  if (visibilityToggle) {
    visibilityToggle.onclick = () => {
      setLegendVisibility(false);
    };
  }

  setTagFormattingEnabled(prefs.useTagColors);
  setDayBackgroundsEnabled(prefs.showDayBackgrounds);
  setLegendVisibility(prefs.hidden, { save: false });
}

function setTagFormattingEnabled(enabled) {
  document.body.classList.toggle('tags-disabled', !enabled);
}

function setDayBackgroundsEnabled(enabled) {
  document.body.classList.toggle('day-backgrounds-disabled', !enabled);
}

function refreshCalendarForVisualPreferenceChange() {
  if (isMobile || !calendar) return;
  destroyCalendar();
  initializeCalendar(calendarDisplayEvents);
  addTodayStyles();
}

function setLegendVisibility(hidden, options = {}) {
  document.body.classList.toggle('legend-hidden', hidden);
  const toggleButton = document.getElementById('legend-visibility-toggle');
  if (toggleButton) {
    toggleButton.textContent = hidden ? 'Show legend' : 'Hide legend';
    toggleButton.setAttribute('aria-expanded', hidden ? 'false' : 'true');
  }
  if (options.save !== false) {
    saveLegendPrefs();
  }
}

function setLegendCheckboxes(checked) {
  const inputs = document.querySelectorAll('#calendar-legend-items input[type="checkbox"][data-tag]');
  inputs.forEach(input => {
    input.checked = checked;
  });
  updateActiveTagsFromLegend();
  applyTagFilters();
}

function updateActiveTagsFromLegend() {
  const inputs = document.querySelectorAll('#calendar-legend-items input[type="checkbox"][data-tag]');
  activeTagSlugs = new Set(
    Array.from(inputs)
      .filter(input => input.checked)
      .map(input => input.dataset.tag)
  );
}

function eventMatchesTags(tags) {
  if (filterUtils?.eventMatchesTags) {
    return filterUtils.eventMatchesTags({
      tags,
      categoryMap: activeCategoryMap,
      activeTagSlugs,
      showExcludedEvents,
    });
  }

  const mappedCategories = getEffectiveMappedCategories(tags);
  if (mappedCategories.length === 0) {
    return showExcludedEvents;
  }
  if (!activeTagSlugs || activeTagSlugs.size === 0) return false;
  return mappedCategories.some(category => activeTagSlugs.has(category.slug));
}

function filterEventsByTags(events) {
  return events.filter(event => eventMatchesTags(event.extendedProps?.tags));
}

function filterRawEventsByTags(events) {
  return events.filter(event => eventMatchesTags(event.tags));
}

function normalizeSearchText(value) {
  return String(value || '').toLowerCase().trim();
}

function getCalendarEventSearchBlob(event) {
  if (calendarSearchBlobCache.has(event)) {
    return calendarSearchBlobCache.get(event);
  }
  const tags = Array.isArray(event?.extendedProps?.tags) ? event.extendedProps.tags : [];
  const location = event?.extendedProps?.location || event?.location || {};
  const agenda = event?.extendedProps?.agenda || event?.agenda || null;
  const blob = [
    event?.title,
    event?.extendedProps?.description,
    location?.name,
    location?.address,
    event?.extendedProps?.source,
    event?.extendedProps?.sourceGroup,
    event?.extendedProps?.group,
    agenda?.day,
    ...(Array.isArray(agenda?.sessions)
      ? agenda.sessions.flatMap(session => [session?.title, session?.description, ...(Array.isArray(session?.hosts) ? session.hosts : [])])
      : []),
    ...tags
  ]
    .filter(Boolean)
    .join(' ')
    .toLowerCase();
  calendarSearchBlobCache.set(event, blob);
  return blob;
}

function getRawEventSearchBlob(event) {
  if (rawSearchBlobCache.has(event)) {
    return rawSearchBlobCache.get(event);
  }
  const tags = Array.isArray(event?.tags) ? event.tags : [];
  const location = event?.location || {};
  const agenda = event?.agenda || null;
  const blob = [
    event?.name,
    event?.description,
    location?.name,
    location?.address,
    event?.source,
    event?.source_group,
    event?.org_name,
    event?.orgName,
    agenda?.day,
    ...(Array.isArray(agenda?.sessions)
      ? agenda.sessions.flatMap(session => [session?.title, session?.description, ...(Array.isArray(session?.hosts) ? session.hosts : [])])
      : []),
    ...tags
  ]
    .filter(Boolean)
    .join(' ')
    .toLowerCase();
  rawSearchBlobCache.set(event, blob);
  return blob;
}

function filterEventsBySearch(events) {
  const query = normalizeSearchText(textSearchQuery);
  if (!query) return events;
  return events.filter(event => getCalendarEventSearchBlob(event).includes(query));
}

function filterRawEventsBySearch(events) {
  const query = normalizeSearchText(textSearchQuery);
  if (!query) return events;
  return events.filter(event => getRawEventSearchBlob(event).includes(query));
}

function hasAdvancedFilterControls() {
  return Boolean(document.getElementById('proximity-filter-input'));
}

function getAdvancedFilterElements() {
  return {
    nearInput: document.getElementById('proximity-filter-input'),
    radiusInput: document.getElementById('proximity-radius-input'),
    dateFromInput: document.getElementById('calendar-date-from-input'),
    dateToInput: document.getElementById('calendar-date-to-input'),
    timeStartInput: document.getElementById('calendar-time-start-input'),
    timeEndInput: document.getElementById('calendar-time-end-input'),
    applyButton: document.getElementById('calendar-filter-apply'),
    clearButton: document.getElementById('calendar-filter-clear'),
    status: document.getElementById('calendar-filter-status')
  };
}

function mergeGeocodeCaches(cacheList) {
  return Object.assign({}, ...cacheList.filter(cache => cache && typeof cache === 'object' && !Array.isArray(cache)));
}

async function fetchOptionalJson(url) {
  try {
    const response = await fetch(url, { cache: 'no-store' });
    if (!response.ok) return {};
    return response.json();
  } catch (error) {
    return {};
  }
}

async function loadGeocodeLookupCache(city) {
  if (!hasAdvancedFilterControls()) return {};
  const caches = await Promise.all([
    fetchOptionalJson('/geocode_cache.json'),
    fetchOptionalJson(`/${city}/geocode_cache.json`)
  ]);
  return mergeGeocodeCaches(caches);
}

function getAdvancedFiltersFromUrl() {
  const params = new URLSearchParams(window.location.search);
  return {
    near: params.get(PROXIMITY_QUERY_PARAM) || '',
    radius: params.get(RADIUS_QUERY_PARAM) || '25',
    dateFrom: params.get(DATE_FROM_QUERY_PARAM) || '',
    dateTo: params.get(DATE_TO_QUERY_PARAM) || '',
    timeStart: params.get(TIME_START_QUERY_PARAM) || '',
    timeEnd: params.get(TIME_END_QUERY_PARAM) || ''
  };
}

function syncAdvancedFiltersToUrl() {
  if (!window.history || typeof window.history.replaceState !== 'function') return;
  const url = new URL(window.location.href);
  const setOrDelete = (param, value) => {
    const normalized = String(value || '').trim();
    if (normalized) url.searchParams.set(param, normalized);
    else url.searchParams.delete(param);
  };

  setOrDelete(PROXIMITY_QUERY_PARAM, proximityFilter.query);
  setOrDelete(RADIUS_QUERY_PARAM, proximityFilter.query ? String(proximityFilter.radiusMiles || 25) : '');
  setOrDelete(DATE_FROM_QUERY_PARAM, timeFilter.dateFrom);
  setOrDelete(DATE_TO_QUERY_PARAM, timeFilter.dateTo);
  setOrDelete(TIME_START_QUERY_PARAM, timeFilter.timeStart);
  setOrDelete(TIME_END_QUERY_PARAM, timeFilter.timeEnd);

  window.history.replaceState({}, '', `${url.pathname}${url.search}${url.hash}`);
}

function readAdvancedFiltersFromControls() {
  const elements = getAdvancedFilterElements();
  const radius = Number(elements.radiusInput?.value || 25);
  proximityFilter.query = String(elements.nearInput?.value || '').trim();
  proximityFilter.radiusMiles = Number.isFinite(radius) && radius > 0 ? radius : 25;
  proximityFilter.center = proximityFilter.query && filterUtils?.resolveProximityQuery
    ? filterUtils.resolveProximityQuery(proximityFilter.query, rawEvents, geocodeLookupCache)
    : null;
  proximityFilter.pending = false;
  proximityFilter.error = '';

  let dateFrom = String(elements.dateFromInput?.value || '').trim();
  let dateTo = String(elements.dateToInput?.value || '').trim();
  if (dateFrom && dateTo && dateFrom > dateTo) {
    [dateFrom, dateTo] = [dateTo, dateFrom];
    if (elements.dateFromInput) elements.dateFromInput.value = dateFrom;
    if (elements.dateToInput) elements.dateToInput.value = dateTo;
  }

  timeFilter = {
    dateFrom,
    dateTo,
    timeStart: String(elements.timeStartInput?.value || '').trim(),
    timeEnd: String(elements.timeEndInput?.value || '').trim()
  };
  updateDateRangeInputConstraints();
}

function writeAdvancedFiltersToControls(values) {
  const elements = getAdvancedFilterElements();
  if (elements.nearInput) elements.nearInput.value = values.near || '';
  if (elements.radiusInput) elements.radiusInput.value = values.radius || '25';
  if (elements.dateFromInput) elements.dateFromInput.value = values.dateFrom || '';
  if (elements.dateToInput) elements.dateToInput.value = values.dateTo || '';
  if (elements.timeStartInput) elements.timeStartInput.value = values.timeStart || '';
  if (elements.timeEndInput) elements.timeEndInput.value = values.timeEnd || '';
}

function clearAdvancedFilters() {
  const searchInput = document.getElementById('calendar-search-input');
  if (searchInput) {
    searchInput.value = '';
    textSearchQuery = '';
    syncSearchQueryToUrl('');
  }
  writeAdvancedFiltersToControls({
    near: '',
    radius: '25',
    dateFrom: '',
    dateTo: '',
    timeStart: '',
    timeEnd: ''
  });
  readAdvancedFiltersFromControls();
  syncAdvancedFiltersToUrl();
  applyTagFilters();
}

function clearFieldById(fieldId) {
  const input = document.getElementById(fieldId);
  if (!input) return;
  input.value = '';
  input.dispatchEvent(new Event('input', { bubbles: true }));
  input.dispatchEvent(new Event('change', { bubbles: true }));
  input.focus();
}

function setupFieldClearButtons() {
  document.querySelectorAll('[data-clear-field]').forEach(button => {
    button.addEventListener('click', event => {
      event.preventDefault();
      event.stopPropagation();
      clearFieldById(button.dataset.clearField);
    });
  });
}

function updateDateRangeInputConstraints() {
  const { dateFromInput, dateToInput } = getAdvancedFilterElements();
  if (!dateFromInput || !dateToInput) return;
  dateToInput.min = dateFromInput.value || '';
  dateFromInput.max = dateToInput.value || '';
}

function getZipOnlyQuery(query) {
  const normalized = String(query || '').trim();
  const zip = filterUtils?.extractZipCode ? filterUtils.extractZipCode(normalized) : '';
  return zip && /^(\d{5})(?:-\d{4})?$/.test(normalized) ? zip : '';
}

async function resolveRemoteZip(zip) {
  if (remoteZipLookupCache.has(zip)) {
    return remoteZipLookupCache.get(zip);
  }

  const lookup = fetch(`https://api.zippopotam.us/us/${encodeURIComponent(zip)}`)
    .then(response => {
      if (!response.ok) throw new Error(`ZIP lookup HTTP ${response.status}`);
      return response.json();
    })
    .then(data => {
      const place = Array.isArray(data?.places) ? data.places[0] : null;
      const latitude = Number(place?.latitude);
      const longitude = Number(place?.longitude);
      if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) {
        throw new Error(`ZIP lookup did not include coordinates for ${zip}`);
      }
      return {
        latitude,
        longitude,
        source: 'zip',
        label: `${zip}${place?.['place name'] ? ` ${place['place name']}` : ''}`
      };
    })
    .catch(error => {
      remoteZipLookupCache.delete(zip);
      throw error;
    });

  remoteZipLookupCache.set(zip, lookup);
  return lookup;
}

function maybeResolveRemoteProximity() {
  const zip = getZipOnlyQuery(proximityFilter.query);
  if (!zip || proximityFilter.center) return;

  const sequence = ++proximityResolutionSequence;
  proximityFilter.pending = true;
  proximityFilter.error = '';
  updateAdvancedFilterStatus(calendarDisplayEvents.length);

  resolveRemoteZip(zip)
    .then(center => {
      if (sequence !== proximityResolutionSequence || getZipOnlyQuery(proximityFilter.query) !== zip) return;
      proximityFilter.center = center;
      proximityFilter.pending = false;
      proximityFilter.error = '';
      applyTagFilters();
    })
    .catch(error => {
      if (sequence !== proximityResolutionSequence || getZipOnlyQuery(proximityFilter.query) !== zip) return;
      console.error('Failed to resolve ZIP proximity filter:', error);
      proximityFilter.center = null;
      proximityFilter.pending = false;
      proximityFilter.error = `could not resolve "${proximityFilter.query}"`;
      applyTagFilters();
    });
}

function setupAdvancedFilters() {
  if (!hasAdvancedFilterControls()) return;

  const elements = getAdvancedFilterElements();
  writeAdvancedFiltersToControls(getAdvancedFiltersFromUrl());
  readAdvancedFiltersFromControls();

  const applyFilters = () => {
    readAdvancedFiltersFromControls();
    syncAdvancedFiltersToUrl();
    applyTagFilters();
    maybeResolveRemoteProximity();
  };

  const scheduleApplyFilters = () => {
    clearTimeout(advancedFilterApplyTimer);
    advancedFilterApplyTimer = setTimeout(applyFilters, 180);
  };

  elements.applyButton?.addEventListener('click', applyFilters);
  elements.clearButton?.addEventListener('click', clearAdvancedFilters);
  setupFieldClearButtons();
  updateDateRangeInputConstraints();

  [
    elements.nearInput,
    elements.radiusInput,
    elements.dateFromInput,
    elements.dateToInput,
    elements.timeStartInput,
    elements.timeEndInput
  ].filter(Boolean).forEach(input => {
    input.addEventListener('keydown', event => {
      if (event.key === 'Enter') {
        event.preventDefault();
        clearTimeout(advancedFilterApplyTimer);
        applyFilters();
      }
    });
    input.addEventListener('change', applyFilters);
    input.addEventListener('input', scheduleApplyFilters);
  });

  maybeResolveRemoteProximity();
}

function eventMatchesProximityFilter(event) {
  if (!proximityFilter.query) return true;
  if (proximityFilter.pending) return true;
  if (!proximityFilter.center || !filterUtils?.distanceMiles) return false;
  const location = event?.location || event?.extendedProps?.location || null;
  if (filterUtils?.isUsableProximityLocation && !filterUtils.isUsableProximityLocation(location)) {
    return false;
  }
  const distance = filterUtils.distanceMiles(location, proximityFilter.center);
  return distance !== null && distance <= proximityFilter.radiusMiles;
}

function eventMatchesCalendarTimeFilter(event) {
  if (!filterUtils?.eventMatchesTimeFilters) return true;
  return filterUtils.eventMatchesTimeFilters(event, {
    ...timeFilter,
    timeZone: getActiveTimeZone()
  });
}

function filterEventsByAdvancedFilters(events) {
  if (!hasAdvancedFilterControls()) return events;
  return events.filter(event => eventMatchesProximityFilter(event) && eventMatchesCalendarTimeFilter(event));
}

function filterRawEventsByAdvancedFilters(events) {
  if (!hasAdvancedFilterControls()) return events;
  return events.filter(event => eventMatchesProximityFilter(event) && eventMatchesCalendarTimeFilter(event));
}

function updateAdvancedFilterStatus(visibleCount) {
  if (!hasAdvancedFilterControls()) return;
  const status = getAdvancedFilterElements().status;
  if (!status) return;

  const activeParts = [];
  if (proximityFilter.query) {
    if (proximityFilter.pending) {
      activeParts.push(`resolving ${proximityFilter.query}`);
    } else if (proximityFilter.center) {
      activeParts.push(`within ${proximityFilter.radiusMiles} miles of ${proximityFilter.query}`);
    } else if (proximityFilter.error) {
      activeParts.push(proximityFilter.error);
    } else {
      activeParts.push(`could not resolve "${proximityFilter.query}"`);
    }
  }
  if (timeFilter.dateFrom || timeFilter.dateTo) {
    activeParts.push(`dates ${timeFilter.dateFrom || 'any'} to ${timeFilter.dateTo || 'any'}`);
  }
  if (timeFilter.timeStart || timeFilter.timeEnd) {
    activeParts.push(`times ${timeFilter.timeStart || 'any'} to ${timeFilter.timeEnd || 'any'}`);
  }

  status.textContent = activeParts.length
    ? `${visibleCount} matching events; ${activeParts.join('; ')}.`
    : `${visibleCount} matching events.`;
}

function setupTextSearch() {
  const searchInput = document.getElementById('calendar-search-input');
  if (!searchInput) return;

  const initialQuery = getSearchQueryFromUrl();
  searchInput.value = initialQuery;
  textSearchQuery = initialQuery;

  const applySearch = () => {
    textSearchQuery = searchInput.value || '';
    if (filterApplyTimer) {
      clearTimeout(filterApplyTimer);
    }
    filterApplyTimer = setTimeout(() => {
      applyTagFilters();
    }, 120);
    clearTimeout(searchUrlSyncTimer);
    searchUrlSyncTimer = setTimeout(() => {
      syncSearchQueryToUrl(textSearchQuery);
    }, 120);
  };

  searchInput.addEventListener('input', applySearch);
  searchInput.addEventListener('search', applySearch);

  window.addEventListener('popstate', () => {
    const nextQuery = getSearchQueryFromUrl();
    if (searchInput.value !== nextQuery) {
      searchInput.value = nextQuery;
      textSearchQuery = nextQuery;
    }
    buildLegend(activeCategoryMap);
    applyTagFilters();
  });
}

function applyTagFilters() {
  const tagFilteredEvents = filterEventsByTags(allEvents);
  const filteredByLegendSearchAndAdvanced = filterEventsByAdvancedFilters(filterEventsBySearch(tagFilteredEvents));
  calendarDisplayEvents = filteredByLegendSearchAndAdvanced;
  dayImageByDate = buildDayImageIndex(filteredByLegendSearchAndAdvanced);

  if (isMobile) {
    initializeMobileCards(filteredByLegendSearchAndAdvanced);
  } else if (calendar) {
    calendar.removeAllEvents();
    calendar.addEventSource(filteredByLegendSearchAndAdvanced);
  } else {
    initializeCalendar(filteredByLegendSearchAndAdvanced);
  }

  const rawFilteredByLegendSearchAndAdvanced = filterRawEventsByAdvancedFilters(filterRawEventsBySearch(filterRawEventsByTags(rawEvents)));
  populateCodeCollectiveEvents(rawFilteredByLegendSearchAndAdvanced);
  updateAdvancedFilterStatus(filteredByLegendSearchAndAdvanced.length);
  saveLegendPrefs();
}

function getEffectiveMappedCategories(tags, categoryMap = activeCategoryMap) {
  if (filterUtils?.getEffectiveMappedCategories) {
    return filterUtils.getEffectiveMappedCategories(tags, categoryMap);
  }

  if (categoryMap?.id === 'tech_only' && !isTechOnlyEvent(tags)) {
    return [];
  }
  return getMappedCategoriesForTags(tags, categoryMap);
}

function isExcludedFromActiveMap(tags) {
  if (filterUtils?.isExcludedFromActiveMap) {
    return filterUtils.isExcludedFromActiveMap(tags, activeCategoryMap);
  }

  if (activeCategoryMap?.id === 'tech_only' && !isTechOnlyEvent(tags)) {
    return true;
  }
  return getDirectMappedCategoriesForTags(tags).length === 0;
}

function getEventClickAction() {
  const selector = document.getElementById('legend-click-action-select');
  return selector?.value || 'open_page';
}

function getEventDataFromCalendarEvent(event) {
  return {
    id: event.id || '',
    name: event.title || '',
    startDate: event.startStr || (event.start ? event.start.toISOString() : ''),
    endTime: event.endStr || (event.end ? event.end.toISOString() : ''),
    description: event.extendedProps?.description || event.description || '',
    location: event.extendedProps?.location || event.location || null,
    url: event.url || '',
    imageUrl: event.extendedProps?.imageUrl || '',
    orgImageUrl: event.extendedProps?.orgImageUrl || '',
    agenda: event.extendedProps?.agenda || null,
    tags: Array.isArray(event.extendedProps?.tags) ? event.extendedProps.tags : [],
    source: event.extendedProps?.source || '',
    source_group: event.extendedProps?.sourceGroup || event.extendedProps?.group || ''
  };
}

function buildAgendaSummaryText(agenda) {
  if (!agenda || !Array.isArray(agenda.sessions) || agenda.sessions.length === 0) return '';
  const dayLabel = agenda.day ? `Agenda (${agenda.day})` : 'Agenda';
  const lines = agenda.sessions.map(session => {
    const title = String(session?.title || '').trim();
    const start = session?.startDate ? formatEventTime(new Date(session.startDate)) : '';
    const end = session?.endTime ? formatEventTime(new Date(session.endTime)) : '';
    const time = start && end ? `${start}-${end}` : start || '';
    const hosts = Array.isArray(session?.hosts) && session.hosts.length ? ` [${session.hosts.join(', ')}]` : '';
    return `${time ? `${time} ` : ''}${title}${hosts}`.trim();
  }).filter(Boolean);
  return lines.length ? `${dayLabel}\n${lines.join('\n')}` : '';
}

function buildAgendaHtml(agenda) {
  if (!agenda || !Array.isArray(agenda.sessions) || agenda.sessions.length === 0) return '';
  const dayLabel = agenda.day ? `Agenda: ${agenda.day}` : 'Agenda';
  const items = agenda.sessions.map(session => {
    const title = escapeHtml(session?.title || '');
    const start = session?.startDate ? formatEventTime(new Date(session.startDate)) : '';
    const end = session?.endTime ? formatEventTime(new Date(session.endTime)) : '';
    const time = start && end ? `${start}-${end}` : (start || '');
    const hosts = Array.isArray(session?.hosts) && session.hosts.length
      ? `<div class="event-agenda-hosts">${escapeHtml(session.hosts.join(', '))}</div>`
      : '';
    return `<li><div class="event-agenda-line">${time ? `<strong>${escapeHtml(time)}</strong> ` : ''}${title}</div>${hosts}</li>`;
  }).join('');
  return `<div class="event-agenda"><h4>${escapeHtml(dayLabel)}</h4><ul>${items}</ul></div>`;
}

function buildEventDisplayDescription(eventData) {
  const base = String(eventData?.description || '').trim();
  const agendaText = buildAgendaSummaryText(eventData?.agenda);
  return [base, agendaText].filter(Boolean).join('\n\n');
}

async function copyTextToClipboard(text) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }

  const textarea = document.createElement('textarea');
  textarea.value = text;
  textarea.setAttribute('readonly', '');
  textarea.style.position = 'fixed';
  textarea.style.opacity = '0';
  document.body.appendChild(textarea);
  textarea.select();
  document.execCommand('copy');
  textarea.remove();
}

function ensureEventInfoModal() {
  if (eventInfoModal) return eventInfoModal;

  const modal = document.createElement('div');
  modal.className = 'event-info-modal';
  modal.setAttribute('hidden', '');
  modal.innerHTML = `
    <div class="event-info-modal-backdrop" data-close-modal="true"></div>
    <div class="event-info-modal-dialog" role="dialog" aria-modal="true" aria-label="Event details">
      <button type="button" class="event-info-modal-close" data-close-modal="true" aria-label="Close event details">&times;</button>
      <div class="event-info-modal-media-wrap" hidden>
        <img class="event-info-modal-media" alt="" />
      </div>
      <div class="event-info-modal-copy">
        <div class="event-info-modal-kicker"></div>
        <h3 class="event-info-modal-title"></h3>
        <div class="event-info-modal-source"></div>
        <div class="event-info-modal-tags"></div>
        <div class="event-info-modal-description"></div>
        <div class="event-info-modal-actions">
          <a class="event-info-modal-link" target="_blank" rel="noopener noreferrer">Open event page</a>
        </div>
      </div>
    </div>
  `;
  modal.addEventListener('click', event => {
    if (event.target.closest('[data-close-modal="true"]')) {
      hideEventInfoModal();
    }
  });
  document.body.appendChild(modal);
  eventInfoModal = modal;
  return modal;
}

function showEventInfoModal(eventData) {
  const modal = ensureEventInfoModal();
  const sourceLabel = formatSourceLabel(eventData.source || eventData.url || '', eventData.source_group || 'Unknown source');
  const imageUrl = safeUrl(eventData.imageUrl || eventData.orgImageUrl || '');
  const mediaWrap = modal.querySelector('.event-info-modal-media-wrap');
  const media = modal.querySelector('.event-info-modal-media');
  modal.querySelector('.event-info-modal-kicker').textContent = formatEventDate(eventData.startDate, eventData.endTime);
  modal.querySelector('.event-info-modal-title').textContent = eventData.name || 'Untitled';
  modal.querySelector('.event-info-modal-source').textContent = sourceLabel;
  modal.querySelector('.event-info-modal-tags').innerHTML = (Array.isArray(eventData.tags) ? eventData.tags : []).map(tag => {
    const mapped = getEffectiveMappedCategories([tag])[0];
    const background = mapped?.color || '#4b5563';
    const textColor = mapped?.textColor || '#ffffff';
    return `<span class="event-hover-tag" style="--tag-chip-bg: ${escapeAttr(background)}; --tag-chip-fg: ${escapeAttr(textColor)};">${escapeHtml(tag)}</span>`;
  }).join('');
  const combinedDescription = buildEventDisplayDescription(eventData);
  const agendaHtml = buildAgendaHtml(eventData.agenda);
  modal.querySelector('.event-info-modal-description').innerHTML = `${renderRichText(combinedDescription || '')}${agendaHtml}`;
  const link = modal.querySelector('.event-info-modal-link');
  if (eventData.url) {
    link.href = eventData.url;
    link.removeAttribute('hidden');
  } else {
    link.removeAttribute('href');
    link.setAttribute('hidden', '');
  }

  if (imageUrl) {
    mediaWrap.hidden = false;
    media.src = imageUrl;
    media.alt = eventData.name || 'Event image';
  } else {
    mediaWrap.hidden = true;
    media.removeAttribute('src');
    media.alt = '';
  }

  modal.removeAttribute('hidden');
  document.body.classList.add('event-info-modal-open');
}

function hideEventInfoModal() {
  if (!eventInfoModal) return;
  eventInfoModal.setAttribute('hidden', '');
  document.body.classList.remove('event-info-modal-open');
}

async function handleEventActivation(eventData, triggerEvent) {
  const action = getEventClickAction();
  const wantsNewTab = Boolean(triggerEvent?.ctrlKey || triggerEvent?.metaKey);

  if (wantsNewTab && eventData.url) {
    window.open(eventData.url, '_blank', 'noopener');
    return;
  }

  if (action === 'info_modal') {
    showEventInfoModal(eventData);
    return;
  }

  if (action === 'copy_name') {
    await copyTextToClipboard(eventData.name || '');
    return;
  }

  if (action === 'copy_json') {
    await copyTextToClipboard(JSON.stringify(eventData, null, 2));
    return;
  }

  if (eventData.url) {
    window.location.href = eventData.url;
  }
}
// Generic image prefetching function (with unique URLs only)
function prefetchImages(urls) {
  if (!Array.isArray(urls) || urls.length === 0) return;

  // Best-practice: only prefetch a small, above-the-fold subset and do it during idle time.
  const uniqueUrls = Array.from(new Set(urls)).slice(0, IMAGE_PREFETCH_LIMIT);
  const prefetchTask = () => {
    uniqueUrls.forEach(url => {
      const link = document.createElement('link');
      link.rel = 'prefetch';
      link.as = 'image';
      link.href = url;
      document.head.appendChild(link);
    });
  };

  if (typeof window.requestIdleCallback === 'function') {
    window.requestIdleCallback(prefetchTask, { timeout: 2000 });
  } else {
    setTimeout(prefetchTask, 0);
  }
}


function getCityOptions() {
  return window.CALENDAR_CITY_OPTIONS || ['baltimore', 'westvirginia', 'hawaii', 'dc', 'pittsburgh', 'philadelphia', 'virtual'];
}

// Function to get city from URL parameters
function getCityFromUrl() {
  const urlParams = new URLSearchParams(window.location.search);
  const city = urlParams.get('city');
  const cityOptions = getCityOptions();
  return cityOptions.includes(city) ? city : 'baltimore'; // Default to baltimore if no city specified
}

function getSearchQueryFromUrl() {
  const urlParams = new URLSearchParams(window.location.search);
  return urlParams.get(SEARCH_QUERY_PARAM) || '';
}

function syncSearchQueryToUrl(rawQuery) {
  if (!window.history || typeof window.history.replaceState !== 'function') return;

  const query = String(rawQuery || '').trim();
  const url = new URL(window.location.href);
  if (query) {
    url.searchParams.set(SEARCH_QUERY_PARAM, query);
  } else {
    url.searchParams.delete(SEARCH_QUERY_PARAM);
  }

  window.history.replaceState({}, '', `${url.pathname}${url.search}${url.hash}`);
}

function shouldStayOnCalendarView() {
  const urlParams = new URLSearchParams(window.location.search);
  const viewPreference = (urlParams.get('view') || '').toLowerCase();

  if (viewPreference === 'calendar' || viewPreference === 'desktop') {
    sessionStorage.setItem('preferCalendarView', '1');
    return true;
  }

  return sessionStorage.getItem('preferCalendarView') === '1';
}

// Fetch and parse event data
document.addEventListener('DOMContentLoaded', function () {
  forceCardView = Boolean(window.FORCE_CALENDAR_CARDS);
  setupTimezoneControls();
  const stayOnCalendar = shouldStayOnCalendarView();
  const mobileViewport = isMobileDevice();
  isMobile = forceCardView ? true : (mobileViewport && !stayOnCalendar);

  if (!forceCardView && isMobile) {
    const query = window.location.search || '';
    const target = `/simplecalendar.html${query}`;
    window.location.replace(target);
    return;
  }

  const city = getCityFromUrl();
  const endpoint = `/${city}/upcoming_events.json`;

  Promise.all([
    loadCategoryMapConfig(),
    fetch(endpoint).then(response => {
      if (!response.ok) {
        throw new Error(`Failed to fetch events for city: ${city}`);
      }
      return response.json();
    }),
    loadGeocodeLookupCache(city)
  ])
    .then(([mapConfig, events, geocodeCache]) => {
      if (mapConfig && Array.isArray(mapConfig.maps) && mapConfig.maps.length > 0) {
        categoryMapConfig = mapConfig;
        activeCategoryMap = getCategoryMapById(mapConfig.default_map);
      }
      geocodeLookupCache = geocodeCache || {};
      rawEvents = Array.isArray(events) ? events : [];
      allEvents = processEvents(rawEvents);

      // Extract all unique event image URLs
      const eventImageUrls = allEvents
        .map(event => getPreferredEventImage(event))
        .filter(url => url); // Remove null/undefined

      // Prefetch all event images in parallel
      prefetchImages(eventImageUrls);

      filteredEvents = [...allEvents]; // Make a copy for filtering

      setupTextSearch();
      setupAdvancedFilters();
      buildLegend(activeCategoryMap);
      applyTagFilters();

      setupViewSelectors();
      document.getElementById('loading').style.display = 'none';

      if (!isMobile) {
        highlightToday();
      }
    })
    .catch(error => {
      console.error('Error loading events:', error);
      document.getElementById('loading').innerHTML = '<i class="fas fa-exclamation-circle"></i> Error loading events. Please try again.';
    });

  // Add CSS for today's date styling (desktop only)
  if (!isMobile) {
    addTodayStyles();
  }

  if (!forceCardView) {
    // Debounce the resize event listener to avoid excessive re-rendering
    let resizeTimeout;
    window.addEventListener('resize', function () {
      clearTimeout(resizeTimeout);
      resizeTimeout = setTimeout(() => {
        const wasMobile = isMobile;
        const mobileResizeViewport = isMobileDevice();
        isMobile = forceCardView ? true : (mobileResizeViewport && !shouldStayOnCalendarView());

        if (wasMobile !== isMobile) {
          if (isMobile) {
            destroyCalendar();
            initializeMobileCards(allEvents);
          } else {
            destroyMobileCards();
            const calendarEl = document.getElementById('calendar');
            if (calendarEl) {
              calendarEl.style.display = '';
            }
            initializeCalendar(allEvents);
            addTodayStyles();
          }
        }
      }, 200); // Adjust debounce time as needed
    });
  }
});

// Initialize mobile card view
function initializeMobileCards(events) {
  const container = document.getElementById('calendar');
  if (!container) return;

  if (document.body.classList.contains('calendar-filter-page')) {
    initializeSimpleListCards(events, container);
    return;
  }

  container.style.display = '';
  container.innerHTML = '';
  container.className = 'mobile-cards-container';

  // Filter events to only show future events (after today)
  const todayStart = getTodayStart();

  const futureEvents = events.filter(event =>
    isEventOnOrAfterToday(event.start, todayStart)
  );

  // Sort events by date and time
  futureEvents.sort((a, b) => new Date(a.start) - new Date(b.start));

  // Create individual cards for each event
  futureEvents.forEach(event => {
    const eventCard = createEventCard(event);
    container.appendChild(eventCard);
  });

  // If no future events, show a message
  if (futureEvents.length === 0) {
    const noEventsMsg = document.createElement('div');
    noEventsMsg.className = 'no-events-message';
    noEventsMsg.innerHTML = `
      <i class="fas fa-calendar-times"></i>
      <h3>No upcoming events</h3>
      <p>Check back later for new events!</p>
    `;
    container.appendChild(noEventsMsg);
  }
}

function initializeSimpleListCards(events, container) {
  container.style.display = '';
  container.innerHTML = '';
  container.className = 'simple-events-list';

  const todayStart = getTodayStart();
  const futureEvents = events
    .filter(event => isEventOnOrAfterToday(event.start, todayStart))
    .sort((a, b) => new Date(a.start) - new Date(b.start));

  if (futureEvents.length === 0) {
    const noEventsMsg = document.createElement('div');
    noEventsMsg.className = 'no-events-message';
    noEventsMsg.innerHTML = `
      <i class="fas fa-calendar-times"></i>
      <h3>No matching events</h3>
      <p>Adjust the filters and try again.</p>
    `;
    container.appendChild(noEventsMsg);
    return;
  }

  let currentDateKey = '';
  futureEvents.forEach((event, index) => {
    const dateKey = getDateKeyInTimeZone(event.start, getActiveTimeZone());
    if (dateKey !== currentDateKey) {
      currentDateKey = dateKey;
      const heading = document.createElement('h2');
      heading.className = 'date-head';
      heading.textContent = formatDateWithTimeZone(new Date(event.start), {
        weekday: 'long',
        month: 'long',
        day: 'numeric',
        year: 'numeric'
      });
      container.appendChild(heading);
    }
    container.appendChild(createSimpleListEvent(event, index));
  });
}

function createSimpleListEvent(event, index) {
  const article = document.createElement('article');
  article.className = 'event';
  article.tabIndex = 0;

  const detailsId = `filter-event-details-${index}-${new Date(event.start).getTime()}`;
  const eventUrl = safeUrl(event.url);
  const eventTitle = escapeHtml(event.title || 'Untitled');
  const titleHtml = eventUrl
    ? `<a href="${escapeAttr(eventUrl)}" target="_blank" rel="noopener noreferrer">${eventTitle}</a>`
    : `<span class="nolink">${eventTitle}</span>`;
  const startTime = formatEventTime(new Date(event.start));
  const endTime = event.end ? formatEventTime(new Date(event.end)) : '';
  const timeRange = endTime ? `${startTime} - ${endTime}` : startTime;
  const description = buildEventDisplayDescription({
    description: event.description || event.extendedProps?.description || '',
    agenda: event.extendedProps?.agenda || null
  });
  const eventLocation = event.extendedProps?.location || event.location || null;
  const locationText = [
    eventLocation?.name,
    eventLocation?.address
  ].filter(Boolean).join(', ');
  const imageUrl = safeUrl(getPreferredEventImage(event));

  article.innerHTML = `
    <div class="event-header">
      <div class="event-meta">
        <div class="event-time">${escapeHtml(timeRange)}</div>
        <div class="event-title">${titleHtml}</div>
      </div>
      <button class="toggle-btn" type="button" aria-expanded="false" aria-controls="${detailsId}" aria-label="Show details">+</button>
    </div>
    <div class="event-body" id="${detailsId}" hidden>
      ${description ? `<div class="event-desc">${renderRichText(description)}</div>` : ''}
      ${locationText ? `<div class="location">${escapeHtml(locationText)}</div>` : ''}
      ${imageUrl ? `<img class="event-image" src="${escapeAttr(imageUrl)}" alt="${eventTitle}" loading="lazy">` : ''}
    </div>
  `;

  const toggle = article.querySelector('.toggle-btn');
  const body = article.querySelector('.event-body');
  toggle.addEventListener('click', () => {
    const isOpen = toggle.getAttribute('aria-expanded') === 'true';
    toggle.setAttribute('aria-expanded', isOpen ? 'false' : 'true');
    toggle.textContent = isOpen ? '+' : '-';
    body.hidden = isOpen;
    body.classList.toggle('open', !isOpen);
  });
  article.addEventListener('mouseenter', mouseEvent => {
    showHoverPreview({ event }, mouseEvent);
  });
  article.addEventListener('mousemove', mouseEvent => {
    setHoverPanelSide(mouseEvent.clientX);
  });
  article.addEventListener('mouseleave', hideHoverPreview);
  article.addEventListener('focus', focusEvent => {
    showHoverPreview({ event }, focusEvent);
  });
  article.addEventListener('blur', hideHoverPreview);

  return article;
}

// Create individual event card with expandable description
function toggleCardDescription(button) {
  const card = button.closest('.card-content');
  const shortDesc = card.querySelector('.card-description-short');
  const fullDesc = card.querySelector('.card-description-full');
  const moreBtn = card.querySelector('.more-btn');

  if (fullDesc.style.display === 'none' || !fullDesc.style.display) {
    // Show full description
    shortDesc.style.display = 'none';
    fullDesc.style.display = 'block';
    moreBtn.innerHTML = '<i class="fas fa-chevron-up"></i> Less';
  } else {
    // Show short description
    shortDesc.style.display = 'block';
    fullDesc.style.display = 'none';
    moreBtn.innerHTML = '<i class="fas fa-chevron-down"></i> More';
  }
}
// Create individual event card
function createEventCard(event) {
  const card = document.createElement('div');
  card.className = 'card-content';

  const startTime = formatEventTime(new Date(event.start));
  const endTime = event.end ? formatEventTime(new Date(event.end)) : '';
  const timeRange = endTime ? `${startTime} - ${endTime}` : startTime;

  // Format the full date
  const eventDate = new Date(event.start);
  const fullDate = eventDate.toLocaleDateString('en-US', {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric'
  });

  // Prepare description with markdown support
  const rawDescription = buildEventDisplayDescription({
    description: event.description || '',
    agenda: event.extendedProps?.agenda || null
  });
  const description = rawDescription.trim();
  const maxDescLength = 100;
  const needsMore = description.length > maxDescLength;

  // Create short description by stripping markdown and truncating
  const shortDesc = needsMore ?
    stripMarkdown(description).substring(0, maxDescLength) + '...' :
    stripMarkdown(description);

  card.innerHTML = `
    ${getPreferredEventImage(event) ?
      `<div class="card-image" style="background-image: url(${getPreferredEventImage(event)})"></div>` :
      '<div class="card-image-placeholder"><i class="fas fa-calendar-alt"></i></div>'
    }
      <h3 class="card-title">${event.title}</h3>
      <div class="card-meta">
        <div class="card-time">
          ${fullDate}, ${timeRange}
        </div>${event.location ? `
  <div class="card-location">
    <i class="fas fa-map-marker-alt"></i> 
    <span class="location-address">
      ${[
        event.location.address
      ].filter(Boolean).join(', ')}
    </span>
  </div>
` : ''}


      </div>
      ${description ? `
        <div class="card-description">
          <div class="card-description-short">${shortDesc}</div>
          <div class="card-description-full markdown-content" style="display: none;"></div>
          ${needsMore ? '<button class="more-btn" onclick="toggleCardDescription(this)"><i class="fas fa-chevron-down"></i> More</button>' : ''}
        </div>
      ` : ''}
  `;

  applyTagClasses(card, event.extendedProps?.tags);
  if (isExcludedFromActiveMap(event.extendedProps?.tags)) {
    card.classList.add('excluded-from-map');
  }
  if (isFeaturedSource(event.extendedProps?.source)) {
    card.classList.add('source-codecollective-luma');
  }

  // Process markdown for full description if needed
  if (description && needsMore) {
    const fullDescContainer = card.querySelector('.card-description-full');
    if (fullDescContainer) {
      if (window.marked && typeof window.marked.parse === 'function') {
        fullDescContainer.innerHTML = marked.parse(description);
      } else {
        fullDescContainer.textContent = description;
      }
    }
  }

  // Add click handler (but not for the more button)
  card.addEventListener('click', function (e) {
    if (e.target.closest('.more-btn') || e.target.closest('a')) {
      return;
    }
    handleEventActivation(getEventDataFromCalendarEvent(event), e).catch(error => {
      console.error('Failed to handle event action:', error);
    });
  });

  return card;
}

// Helper function to strip markdown for short description
function stripMarkdown(text) {
  return text
    .replace(/^#+\s+/gm, '')          // Remove headings
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')  // Remove links but keep text
    .replace(/\*\*([^*]+)\*\*/g, '$1')        // Remove bold
    .replace(/\*([^*]+)\*/g, '$1')            // Remove italics
    .replace(/`([^`]+)`/g, '$1')              // Remove code
    .replace(/^\s*[-*+]\s+/gm, '')    // Remove list markers
    .replace(/\n+/g, ' ');            // Replace newlines with spaces
}

// Destroy mobile cards view
function destroyMobileCards() {
  const container = document.getElementById('calendar');
  if (!container) return;
  container.innerHTML = '';
  container.className = '';
  container.style.display = '';
}

// Destroy calendar view
function destroyCalendar() {
  if (calendar) {
    calendar.destroy();
    calendar = null;
  }
}

// Add CSS for today's date styling (desktop only)
function addTodayStyles() {
  const style = document.createElement('style');
  style.textContent = `
    .fc .fc-day-today .fc-daygrid-day-number {
      background-color: yellow !important;
      color: black !important;
      font-weight: bold !important;
      padding: 5px;
    }
  `;
  document.head.appendChild(style);
}

// Function to ensure today's date is highlighted correctly (desktop only)
function highlightToday() {
  if (isMobile) return;

  const todayEl = document.querySelector('.fc-day-today .fc-daygrid-day-number');
  if (todayEl) {
    todayEl.style.backgroundColor = 'yellow';
    todayEl.style.color = 'black';
    todayEl.style.fontWeight = 'bold';
  }
}

// Process the JSON event data into FullCalendar format
function processEvents(eventsData) {
  return eventsData.map(event => {
    // Extract group name from URL if exists, otherwise use default
    const urlParts = event.url ? event.url.split('/') : [];
    const groupName = urlParts.length > 3 ? urlParts[3] : 'Unknown Group';

    // Add group to the global set
    eventGroups.add(groupName);

    // Return the event in FullCalendar format
    const calendarEvent = {
      id: event.id,
      title: event.name,
      start: event.startDate,
      end: event.endTime,
      description: event.description,
      location: event.location,
      url: event.url,
      agenda: event.agenda || null,
      extendedProps: {
        group: groupName,
        sourceGroup: event.source_group || '',
        description: event.description || '',
        location: event.location || null,
        imageUrl: event.imageUrl,
        orgImageUrl: event.orgImageUrl || '',
        agenda: event.agenda || null,
        tags: Array.isArray(event.tags) ? event.tags : [],
        source: event.source || ''
      },
      backgroundColor: "#0f0f0f0",
      borderColor: "#0f0f0f0",
      textColor: "#000"
    };
    calendarSearchBlobCache.set(calendarEvent, getCalendarEventSearchBlob(calendarEvent));
    return calendarEvent;
  });
}

// Format event time to display like "3PM"
function formatEventTime(date) {
  if (!date) return '';
  return formatDateWithTimeZone(date, {
    hour: 'numeric',
    minute: '2-digit',
    hour12: true
  }).replace(' ', '');
}

// Get the latest event with an image for a specific day (desktop only)
function getLatestEventWithImageForDay(events, date) {
  if (isMobile) return null;
  const dateStr = getDateKeyInTimeZone(date, getActiveTimeZone());

  // Filter events that are on this day and have an image
  const dayEvents = events.filter(event => {
    const eventDateStr = getDateKeyInTimeZone(event.start, getActiveTimeZone());
    return eventDateStr === dateStr && getPreferredEventImage(event);
  });

  // If no events with images for this day, return null
  if (dayEvents.length === 0) return null;

  // Sort events by start time, descending (latest first)
  dayEvents.sort((a, b) => new Date(b.start) - new Date(a.start));

  // Return the latest event
  return dayEvents[0];
}

// Get a random event with an image for a specific day (desktop only)
function getRandomImageForDay(events, date) {
  if (isMobile) return null;
  const dateStr = getDateKeyInTimeZone(date, getActiveTimeZone());
  const event = dayImageByDate.get(dateStr) || null;
  return event;
}

function buildDayImageIndex(events) {
  const index = new Map();
  const todayKey = getDateKeyInTimeZone(getTodayStart(), getActiveTimeZone());
  if (!Array.isArray(events) || !todayKey) return index;

  for (const event of events) {
    const imageUrl = getPreferredEventImage(event);
    if (!imageUrl) continue;
    const eventDateKey = getDateKeyInTimeZone(event.start, getActiveTimeZone());
    if (!eventDateKey || eventDateKey < todayKey || index.has(eventDateKey)) continue;
    index.set(eventDateKey, event);
  }
  return index;
}

// Initialize the FullCalendar (desktop only)
function initializeCalendar(events) {
  if (isMobile) return;
  calendarDisplayEvents = events;
  dayImageByDate = buildDayImageIndex(events);

  // Date gating for desktop is handled by FullCalendar's validRange.
  const today = getTodayStart();

  const calendarEl = document.getElementById('calendar');
  calendar = new FullCalendar.Calendar(calendarEl, {
    timeZone: useLocalTime ? 'local' : selectedTimeZone,
    initialView: 'dayGridFourWeek',
    views: {
      dayGridFourWeek: {
        type: 'dayGrid',
        duration: { weeks: 4 },
        buttonText: '4 Weeks',
        fixedWeekCount: true,     // Always show the same number of weeks (usually 6)
        height: 'auto',           // Let calendar resize to fit, or use a fixed value (e.g., 600)

      },
    },
    headerToolbar: {
      left: 'prev',
      center: 'title',
      right: 'next'
    },
    validRange: {
      start: today             // today's date (inclusive)
    },

    events: events, // Use all events (validRange will filter the display)
    eventClassNames: function (arg) {
      return isFeaturedSource(arg.event.extendedProps?.source) ? ['source-codecollective-luma'] : [];
    },
    eventClick: function (info) {
      handleEventActivation(getEventDataFromCalendarEvent(info.event), info.jsEvent).catch(error => {
        console.error('Failed to handle event action:', error);
      });
      info.jsEvent.preventDefault();
    },
    eventTimeFormat: {
      hour: 'numeric',
      minute: '2-digit',
      meridiem: 'short'
    },
    height: 'auto',
    dayMaxEvents: true, // Allow "more" link when too many events
    dayCellDidMount: function (info) {
      if (document.body.classList.contains('day-backgrounds-disabled')) {
        return;
      }

      // Only show images for today and future dates
      const today = new Date();
      today.setHours(0, 0, 0, 0);
      const cellDate = new Date(info.date);
      cellDate.setHours(0, 0, 0, 0);

      // Skip if this day is before today
      if (cellDate < today) {
        return;
      }

      // Resolve from precomputed date->event lookup to avoid scanning all events per cell.
      const latestEvent = getRandomImageForDay(calendarDisplayEvents, info.date);

      const backgroundImageUrl = getPreferredEventImage(latestEvent);
      if (latestEvent && backgroundImageUrl) {
        // Get the day cell element
        const cellEl = info.el;

        // Find the day frame element (this is the actual "day" content area)
        const dayFrame = cellEl.querySelector('.fc-daygrid-day-frame');

        if (dayFrame) {
          // Add a class to help with styling
          dayFrame.classList.add('has-event-background');

          // Create a semi-transparent background with the event image
          const bgDiv = document.createElement('div');
          bgDiv.classList.add('fc-day-background');
          bgDiv.style.backgroundImage = `url(${backgroundImageUrl})`;
          bgDiv.style.backgroundSize = 'cover';
          bgDiv.style.backgroundPosition = 'center';
          bgDiv.style.backgroundRepeat = 'no-repeat';

          // Add the background div as the first child of the day frame
          dayFrame.style.position = 'relative'; // Ensure positioning context
          dayFrame.prepend(bgDiv);

          // Make sure event content is above the background
          const eventContent = dayFrame.querySelector('.fc-daygrid-day-events');
          if (eventContent) {
            eventContent.style.position = 'relative';
            eventContent.style.zIndex = '2';
          }
        }
      }
    },
    eventContent: function (info) {
      // Handle list view separately
      if (info.view.type.includes('list')) {
        return; // Use default list view rendering
      }

      const eventEl = document.createElement('div');
      eventEl.classList.add('fc-event-content-wrapper');

      // Format the time
      const eventTime = formatEventTime(info.event.start);

      // Add title with time
      const titleEl = document.createElement('div');
      titleEl.classList.add('fc-event-title');
      if (isExcludedFromActiveMap(info.event.extendedProps?.tags)) {
        titleEl.classList.add('excluded-from-map');
      }
      if (isFeaturedSource(info.event.extendedProps?.source)) {
        titleEl.classList.add('source-codecollective-luma-title');
      }
      titleEl.innerHTML = `${eventTime} ${info.event.title}`;
      applyTagClasses(titleEl, info.event.extendedProps?.tags);
      eventEl.appendChild(titleEl);

      return { domNodes: [eventEl] };
    },
    eventDidMount: function (info) {
      if (isFeaturedSource(info.event.extendedProps?.source)) {
        const dayCell = info.el.closest('.fc-daygrid-day');
        if (dayCell) {
          dayCell.classList.add('source-codecollective-luma-day');
        }
      }

      const description = info.event.extendedProps.description || info.event.description || '';
      const sourceLabel = formatSourceLabel(
        info.event.extendedProps?.source || info.event.url || '',
        info.event.extendedProps?.sourceGroup || info.event.extendedProps?.group || 'Unknown source'
      );
      info.el.setAttribute('aria-label', `${info.event.title}. ${sourceLabel}.`);
      info.el.removeAttribute('title');

      info.el.addEventListener('mouseenter', event => {
        showHoverPreview(info, event);
      });
      info.el.addEventListener('mousemove', event => {
        setHoverPanelSide(event.clientX);
      });
      info.el.addEventListener('mouseleave', hideHoverPreview);
      info.el.addEventListener('focus', event => {
        showHoverPreview(info, event);
      });
      info.el.addEventListener('blur', hideHoverPreview);
    },
    // Add this: Callback for when view is rendered
    viewDidMount: function () {
      // Apply today highlighting after view changes
      highlightToday();
    }
  });
  calendar.render();
}

// Set up view selector buttons
function setupViewSelectors() {
  document.querySelectorAll('.view-selector').forEach(button => {
    button.addEventListener('click', function () {
      // Remove active class from all buttons
      document.querySelectorAll('.view-selector').forEach(btn => {
        btn.classList.remove('active');
      });

      // Add active class to clicked button
      this.classList.add('active');

      // Change calendar view
      const view = this.dataset.view;
      currentView = view;

      if (isMobile) {
        // Mobile: Always show cards, but filter/sort differently based on view
        handleMobileViewChange(view);
      } else {
        // Desktop: Use FullCalendar
        const effectiveView = (view === 'listAll') ? 'dayGridMonth' : view;
        calendar.changeView(effectiveView);

        // Reapply today highlighting after view change
        setTimeout(highlightToday, 100);
      }
    });
  });
}

// Handle view changes in mobile mode
function handleMobileViewChange(view) {
  const todayStart = getTodayStart();
  const eventsToShow = filterEventsByTags(allEvents).filter(event =>
    isEventOnOrAfterToday(event.start, todayStart)
  );

  // Re-render mobile cards with filtered events
  initializeMobileCards(eventsToShow);
}

// Format event date for display
function formatEventDate(start, end) {
  if (!start) return '';

  const startDate = new Date(start);
  const options = {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit'
  };

  return formatDateWithTimeZone(startDate, options);
}

// Close popup when clicking outside the content
window.onclick = function (event) {
  const popup = document.getElementById('event-popup');
  if (event.target === popup && typeof closeEventPopup === 'function') {
    closeEventPopup();
  }
  if (event.target?.matches?.('.event-info-modal')) {
    hideEventInfoModal();
  }
};
function populateCodeCollectiveEvents(events) {
  const container = document.getElementById('code-collective-events-container');
  if (!container) return;

  const codeCollectiveEvents = events.filter(event =>
    event.url && event.url.includes('code-collective')
  );

  if (codeCollectiveEvents.length === 0) {
    container.innerHTML = '<p style="text-align: center; color: #999; padding: 20px;">No upcoming Code Collective events at this time.</p>';
    return;
  }

  codeCollectiveEvents.sort((a, b) => new Date(a.startDate) - new Date(b.startDate));

  // Clear container and build with DOM methods
  container.innerHTML = '';

  codeCollectiveEvents.forEach((event, index) => {
    const startDate = new Date(event.startDate);
    const formattedDate = formatDateWithTimeZone(startDate, {
      weekday: 'long',
      year: 'numeric',
      month: 'long',
      day: 'numeric'
    });
    const formattedTime = formatDateWithTimeZone(startDate, {
      hour: 'numeric',
      minute: '2-digit',
      hour12: true
    });

    // Create elements with DOM methods (prevents formatting issues)
    const eventCard = document.createElement('div');
    eventCard.className = 'cc-event-card';

    const eventLink = document.createElement('a');
    eventLink.href = event.url;
    eventLink.className = 'cc-event-card-link';
    eventLink.target = '_blank';
    eventLink.rel = 'noopener noreferrer';

    // Add image if available
    const codeCollectiveImage = getPreferredEventImage(event);
    if (codeCollectiveImage) {
      const img = document.createElement('img');
      img.src = codeCollectiveImage;
      img.alt = event.name;
      img.className = 'event-card-image';
      img.loading = 'lazy';
      eventLink.appendChild(img);
    }

    const contentDiv = document.createElement('div');
    contentDiv.className = 'cc-event-card-content';

    const title = document.createElement('h3');
    title.className = 'cc-event-card-title';
    title.textContent = event.name; // Safe from HTML injection

    const dateDiv = document.createElement('div');
    dateDiv.className = 'cc-event-card-date';
    dateDiv.textContent = `${formattedDate} at ${formattedTime}`;

    const locationDiv = document.createElement('div');
    locationDiv.className = 'cc-event-card-location';
    locationDiv.textContent = event.location?.name || 'Location TBD';

    const descriptionDiv = document.createElement('div');
    descriptionDiv.className = 'cc-event-card-description';

    // Handle description safely
    let description = event.description || '';
    
    // Strip all HTML/markdown and just use plain text
    description = description
      .replace(/<[^>]*>/g, '') // Remove all HTML tags
      .replace(/\*\*(.*?)\*\*/g, '$1') // Remove markdown bold
      .replace(/\*(.*?)\*/g, '$1') // Remove markdown italic
      .replace(/\n+/g, ' ') // Replace newlines with spaces
      .trim();

    const truncatedDescription = description.length > 200 
      ? description.substring(0, 200) + '...' 
      : description;
    
    const needsTruncation = description.length > 200;
    const eventId = `event-${index}`;

    const shortDesc = document.createElement('div');
    shortDesc.id = `${eventId}-short`;
    shortDesc.textContent = truncatedDescription; // Safe from HTML injection
    if (!needsTruncation) shortDesc.style.display = 'block';

    descriptionDiv.appendChild(shortDesc);

    if (needsTruncation) {
      const fullDesc = document.createElement('div');
      fullDesc.id = `${eventId}-full`;
      fullDesc.style.display = 'none';
      fullDesc.textContent = description; // Safe from HTML injection

      const showMoreBtn = document.createElement('button');
      showMoreBtn.type = 'button';
      showMoreBtn.className = 'cc-show-more-btn';
      showMoreBtn.id = `${eventId}-btn`;
      showMoreBtn.textContent = 'Show more';
      showMoreBtn.onclick = () => toggleCcDescription(eventId);

      descriptionDiv.appendChild(fullDesc);
      descriptionDiv.appendChild(showMoreBtn);
    }

    // Assemble the card
    contentDiv.appendChild(title);
    contentDiv.appendChild(dateDiv);
    contentDiv.appendChild(locationDiv);
    contentDiv.appendChild(descriptionDiv);
    eventLink.appendChild(contentDiv);
    eventCard.appendChild(eventLink);
    container.appendChild(eventCard);
  });
}

// Toggle function for show more/less
function toggleCcDescription(eventId) {
  const shortDiv = document.getElementById(`${eventId}-short`);
  const fullDiv = document.getElementById(`${eventId}-full`);
  const btn = document.getElementById(`${eventId}-btn`);

  if (fullDiv.style.display === 'none') {
    shortDiv.style.display = 'none';
    fullDiv.style.display = 'block';
    btn.textContent = 'Show less';
  } else {
    shortDiv.style.display = 'block';
    fullDiv.style.display = 'none';
    btn.textContent = 'Show more';
  }
}
