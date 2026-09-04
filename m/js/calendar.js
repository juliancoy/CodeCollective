/*!
 * Mobile Calendar Cards (no framework)
 * Best-practices JS: event delegation, lazy rendering, optional Markdown+sanitize
 * Requires minimal HTML:
 *   <div id="mobileLoading">Loading…</div>
 *   <div id="mobileCalendar"></div>
 */

/**
 * @typedef {Object} RawEvent
 * @property {string} name
 * @property {string|Date} startDate
 * @property {string|Date} [endTime]
 * @property {string} [description]
 * @property {string|Object} [location] - May be a string or object with { address?: string }
 * @property {string} [url]
 * @property {string} [imageUrl]
 */

(function (window, document) {
  'use strict';

  // --- Config ----------------------------------------------------------------
  const CONFIG = {
    containerSelector: '#mobileCalendar',
    loadingSelector: '#mobileLoading',
    dataUrl: '/upcoming_events.json',
    // Locale + formatting
    locale: 'en-US',
    dayKeyOptions: { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' },
    // Description behavior
    maxShortDescLen: 100,
    // Mobile breakpoint (match CSS)
    mobileMedia: '(max-width: 768px)'
  };

  // --- State -----------------------------------------------------------------
  /** @type {Array<ProcessedEvent>} */
  let ALL_EVENTS = [];
  /** @type {HTMLElement|null} */
  let containerEl = null;
  /** @type {HTMLElement|null} */
  let loadingEl = null;
  /** @type {number|null} */
  let resizeTimer = null;

  // --- Types -----------------------------------------------------------------
  /**
   * @typedef {Object} ProcessedEvent
   * @property {string} title
   * @property {string} start - ISO string
   * @property {string|undefined} end - ISO string
   * @property {string} [description]
   * @property {string|Object} [location]
   * @property {string} [url]
   * @property {{ imageUrl?: string }} [extendedProps]
   */

  // --- Utilities -------------------------------------------------------------
  /** Simple type-safe guard */
  const isString = (v) => typeof v === 'string';

  /** Return true if we consider the viewport "mobile" */
  function isMobileDevice() {
    return window.matchMedia && window.matchMedia(CONFIG.mobileMedia).matches;
  }

  /** Parse a date-ish value to Date or null (defensive) */
  function toDateSafe(value) {
    if (value instanceof Date && !isNaN(value)) return value;
    if (!value) return null;
    const d = new Date(value);
    return isNaN(d) ? null : d;
  }

  /** Format a Date as h:mmAM/PM (minutes optional) */
  function formatEventTime(date) {
    if (!date) return '';
    const hours = date.getHours();
    const minutes = date.getMinutes();
    const period = hours >= 12 ? 'PM' : 'AM';
    const displayHours = hours % 12 || 12;
    return minutes === 0
      ? `${displayHours}${period}`
      : `${displayHours}:${String(minutes).padStart(2, '0')}${period}`;
  }

  /** Very small HTML-escape helper for fallback plain text rendering */
  function escapeHtml(s = '') {
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }

  /** Strip a bit of markdown for short preview text */
  function stripMarkdown(text) {
    return (text || '')
      .replace(/^#+\s+/gm, '')
      .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
      .replace(/\*\*([^*]+)\*\*/g, '$1')
      .replace(/\*([^*]+)\*/g, '$1')
      .replace(/`([^`]+)`/g, '$1')
      .replace(/^\s*[-*+]\s+/gm, '')
      .replace(/\n+/g, ' ')
      .trim();
  }

  /** Optional Markdown -> HTML (uses marked if present; sanitizes if DOMPurify present) */
  function renderMarkdownSafe(md) {
    let html;
    if (window.marked && typeof window.marked.parse === 'function') {
      html = window.marked.parse(md);
    } else {
      // Plaintext fallback: escape + line breaks
      html = escapeHtml(md).replace(/\n/g, '<br>');
    }
    if (window.DOMPurify && typeof window.DOMPurify.sanitize === 'function') {
      html = window.DOMPurify.sanitize(html);
    }
    return html;
  }

  /** Get a readable address string from possible location shapes */
  function getAddressString(loc) {
    if (!loc) return '';
    if (isString(loc)) return loc;
    if (loc && typeof loc === 'object' && 'address' in loc && loc.address) {
      return String(loc.address);
    }
    return '';
  }

  /** Throttle/debounce helper */
  function debounce(fn, wait) {
    return function (...args) {
      if (resizeTimer) window.clearTimeout(resizeTimer);
      resizeTimer = window.setTimeout(() => {
        resizeTimer = null;
        fn.apply(this, args);
      }, wait);
    };
  }

  function parseScrapeTime(value) {
    if (!value) return null;
    let text = String(value).trim();
    if (!text) return null;
    if (/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}/.test(text)) {
      text = `${text.replace(' ', 'T')}Z`;
    }
    const date = new Date(text);
    return Number.isNaN(date.getTime()) ? null : date;
  }

  function getCalendarDataFreshness(events) {
    return (events || []).reduce((latest, event) => {
      const scrapedAt = parseScrapeTime(event.scrapeTime);
      if (!scrapedAt) return latest;
      return !latest || scrapedAt > latest ? scrapedAt : latest;
    }, null);
  }

  function formatCalendarFreshness(date) {
    if (!date) return 'Calendar data freshness unavailable.';
    const absolute = new Intl.DateTimeFormat(CONFIG.locale, {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
      timeZoneName: 'short',
    }).format(date);

    const diffMs = Date.now() - date.getTime();
    if (diffMs < 0) return `Calendar data updated ${absolute}.`;

    const minutes = Math.floor(diffMs / 60000);
    let relative = 'just now';
    if (minutes >= 60 * 24) {
      const days = Math.floor(minutes / (60 * 24));
      relative = `${days} day${days === 1 ? '' : 's'} ago`;
    } else if (minutes >= 60) {
      const hours = Math.floor(minutes / 60);
      relative = `${hours} hour${hours === 1 ? '' : 's'} ago`;
    } else if (minutes >= 1) {
      relative = `${minutes} minute${minutes === 1 ? '' : 's'} ago`;
    }

    return `Calendar data updated ${relative} (${absolute}).`;
  }

  function updateCalendarFreshness(events) {
    const el = document.getElementById('mobileFreshness');
    if (!el) return;
    el.textContent = formatCalendarFreshness(getCalendarDataFreshness(events));
  }

  // --- Data shaping ----------------------------------------------------------
  /**
   * Convert server events to our internal shape.
   * @param {RawEvent[]} events
   * @returns {ProcessedEvent[]}
   */
  function processEvents(events) {
    return (events || []).map((e) => ({
      title: e.name,
      start: e.startDate || '',
      end: e.endTime || '',
      description: e.description || '',
      location: e.location,
      url: e.url || '',
      extendedProps: { imageUrl: e.imageUrl || '' }
    }));
  }

  // --- Rendering -------------------------------------------------------------
  function clearContainer() {
    if (!containerEl) return;
    containerEl.innerHTML = '';
    containerEl.className = 'mobile-cards-container';
    Object.assign(containerEl.style, {
      display: 'flex',
      flexDirection: 'column',
      gap: '1rem',
      padding: '1rem'
    });
  }

  function renderEmptyState() {
    const noEventsMsg = document.createElement('div');
    noEventsMsg.className = 'no-events-message';
    Object.assign(noEventsMsg.style, {
      textAlign: 'center',
      padding: '2rem'
    });
    noEventsMsg.innerHTML = `
      <i class="fas fa-calendar-times" aria-hidden="true"></i>
      <h3>No upcoming events</h3>
      <p>Check back later for new events!</p>
    `;
    containerEl.appendChild(noEventsMsg);
  }

  function groupEventsByDay(events) {
    const today = new Date();
    today.setHours(0, 0, 0, 0);

    const fmt = (d) =>
      d.toLocaleDateString(CONFIG.locale, CONFIG.dayKeyOptions);

    /** @type {Record<string, ProcessedEvent[]>} */
    const byDay = {};
    events
      .filter((ev) => {
        const d = toDateSafe(ev.start);
        if (!d) return false;
        return d >= today;
      })
      .sort((a, b) => {
        const da = toDateSafe(a.start);
        const db = toDateSafe(b.start);
        return (da?.getTime() || 0) - (db?.getTime() || 0);
      })
      .forEach((ev) => {
        const d = toDateSafe(ev.start);
        if (!d) return;
        const key = fmt(d);
        byDay[key] = byDay[key] || [];
        byDay[key].push(ev);
      });

    return byDay;
  }

  /** Build a single event card element */
  function buildEventCard(ev) {
    const card = document.createElement('div');
    card.className = 'mobile-event-card';
    card.setAttribute('role', 'group');
    card.style.width = '100%';
    card.style.maxWidth = '100%';
    card.style.margin = '0';
    card.style.boxSizing = 'border-box';

    const start = toDateSafe(ev.start);
    const end = toDateSafe(ev.end);
    const timeRange = start
      ? end
        ? `${formatEventTime(start)} - ${formatEventTime(end)}`
        : `${formatEventTime(start)}`
      : '';

    const rawDesc = (ev.description || '').trim();
    const needsMore = stripMarkdown(rawDesc).length > CONFIG.maxShortDescLen;
    const shortPreview = stripMarkdown(rawDesc).slice(0, CONFIG.maxShortDescLen);
    const shortDesc = needsMore ? `${shortPreview}…` : shortPreview;

    const address = getAddressString(ev.location);

    // Image block
    const imgBlock = ev.extendedProps?.imageUrl
      ? `<img src="${escapeHtml(ev.extendedProps.imageUrl)}" alt="${escapeHtml(ev.title)}" class="mobile-event-image">`
      : `<div class="mobile-event-image-placeholder" aria-hidden="true"><i class="fas fa-calendar-alt"></i></div>`;

    // Unique id for aria-controls
    const descId = `desc-${Math.random().toString(36).slice(2)}`;

    // Card content (no inline onclick)
    card.innerHTML = `
      <div class="mobile-event-image-container">
        ${imgBlock}
      </div>
      <div class="mobile-event-content">
        <div class="mobile-event-header">
          <h3 class="mobile-event-title">${escapeHtml(ev.title)}</h3>
          <div class="mobile-event-time">${escapeHtml(timeRange)}</div>
        </div>
        ${
          address
            ? `
        <div class="mobile-event-location">
          <i class="fas fa-map-marker-alt" aria-hidden="true"></i>
          <span>${escapeHtml(address)}</span>
        </div>`
            : ''
        }
        ${
          rawDesc
            ? `
        <div class="mobile-event-description" id="${descId}" data-raw="${encodeURIComponent(rawDesc)}">
          ${
            needsMore
              ? `
                <div class="mobile-event-description-short">${escapeHtml(shortDesc)}</div>
                <div class="mobile-event-description-full" style="display:none"></div>
                <button type="button" class="mobile-event-more-btn js-toggle-desc" aria-expanded="false" aria-controls="${descId}">
                  Show More  <i class="fas fa-chevron-down" aria-hidden="true"></i>
                </button>
              `
              : `
                <div class="mobile-event-description-full" data-populated="true">
                  ${renderMarkdownSafe(rawDesc)}
                </div>
              `
          }
        </div>`
            : ''
        }
      </div>
    `;

    // Attach a click on the card itself to open link, but not when clicking buttons/links
    card.addEventListener('click', (e) => {
      const inToggle = e.target.closest('.js-toggle-desc');
      const inLink = e.target.closest('a');
      if (inToggle || inLink) return;
      if (ev.url) window.open(ev.url, '_blank', 'noopener');
    });

    return card;
  }

  /** Render the grouped events into the container */
  function renderCards(events) {
    clearContainer();

    const grouped = groupEventsByDay(events);
    const dayOrder = Object.keys(grouped);

    if (dayOrder.length === 0) {
      renderEmptyState();
      return;
    }

    dayOrder.forEach((day) => {
      const dayHeader = document.createElement('div');
      dayHeader.className = 'mobile-date-header';
      dayHeader.textContent = day;
      containerEl.appendChild(dayHeader);

      grouped[day].forEach((ev) => {
        const card = buildEventCard(ev);
        containerEl.appendChild(card);
      });
    });
  }

  // --- Behavior: expand/collapse with lazy-full rendering --------------------
  function handleToggleClick(btn) {
    const card = btn.closest('.mobile-event-card');
    if (!card) return;
    const shortDesc = card.querySelector('.mobile-event-description-short');
    const fullDesc = card.querySelector('.mobile-event-description-full');
    const wrap = card.querySelector('.mobile-event-description');

    if (!fullDesc || !wrap) return;

    // First time expand? Populate full description
    if (!fullDesc.dataset.populated) {
      const raw = decodeURIComponent(wrap.getAttribute('data-raw') || '');
      fullDesc.innerHTML = renderMarkdownSafe(raw);
      fullDesc.dataset.populated = 'true';
    }

    const isHidden = fullDesc.style.display === 'none';
    if (isHidden) {
      if (shortDesc) shortDesc.style.display = 'none';
      fullDesc.style.display = 'block';
      btn.innerHTML = 'Show Less <i class="fas fa-chevron-up" aria-hidden="true"></i>';
      btn.setAttribute('aria-expanded', 'true');
    } else {
      if (shortDesc) shortDesc.style.display = 'block';
      fullDesc.style.display = 'none';
      btn.innerHTML = 'Show More <i class="fas fa-chevron-down" aria-hidden="true"></i>';
      btn.setAttribute('aria-expanded', 'false');
    }

    // Keep the button in view on mobile
    if (btn.scrollIntoView) {
      btn.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  }

  // --- Public-ish API --------------------------------------------------------
  /**
   * Initialize the mobile calendar UI.
   * Will fetch events from CONFIG.dataUrl unless events are provided.
   * @param {RawEvent[]=} rawEvents
   */
  async function init(rawEvents) {
    containerEl = document.querySelector(CONFIG.containerSelector);
    loadingEl = document.querySelector(CONFIG.loadingSelector);

    if (!containerEl) {
      console.warn('[MobileCalendar] Container not found:', CONFIG.containerSelector);
      return;
    }

    // Event delegation for toggle buttons
    containerEl.addEventListener('click', (e) => {
      const btn = e.target.closest('.js-toggle-desc');
      if (btn) {
        e.preventDefault();
        e.stopPropagation();
        handleToggleClick(btn);
      }
    });

    // Handle mobile-only rendering on resize
    window.addEventListener(
      'resize',
      debounce(() => {
        if (isMobileDevice()) {
          renderCards(ALL_EVENTS);
        }
      }, 200)
    );

    try {
      if (!rawEvents) {
        if (loadingEl) loadingEl.style.display = '';
        const res = await fetch(CONFIG.dataUrl, { credentials: 'same-origin' });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const events = await res.json();
        updateCalendarFreshness(events);
        ALL_EVENTS = processEvents(events);
      } else {
        updateCalendarFreshness(rawEvents);
        ALL_EVENTS = processEvents(rawEvents);
      }

      if (isMobileDevice()) {
        renderCards(ALL_EVENTS);
      } else {
        // If not mobile, you might leave desktop rendering to another script.
        // We still populate the container so it's not empty if CSS stacks it.
        renderCards(ALL_EVENTS);
      }
    } catch (err) {
      console.error('[MobileCalendar] Error loading events:', err);
      if (loadingEl) {
        loadingEl.innerHTML =
          '<i class="fas fa-exclamation-circle" aria-hidden="true"></i> Error loading events. Please try again.';
      }
    } finally {
      if (loadingEl) loadingEl.style.display = 'none';
    }
  }

  /** Refresh cards with current ALL_EVENTS (e.g., after external mutation) */
  function refresh() {
    if (!containerEl) return;
    renderCards(ALL_EVENTS);
  }

  /** Override the data URL before init() if you like */
  function setSourceUrl(url) {
    CONFIG.dataUrl = String(url || CONFIG.dataUrl);
  }

  // Expose tiny API
  window.MobileCalendar = Object.freeze({
    init,
    refresh,
    setSourceUrl
  });

  // Auto-init on DOM ready if container exists
  document.addEventListener('DOMContentLoaded', () => {
    const c = document.querySelector(CONFIG.containerSelector);
    if (c) init();
  });
})(window, document);
