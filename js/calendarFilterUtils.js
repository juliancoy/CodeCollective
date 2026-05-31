(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory();
    return;
  }
  root.CalendarFilterUtils = factory();
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  function slugifyTag(tag) {
    return String(tag || '')
      .toLowerCase()
      .replace(/&/g, 'and')
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '');
  }

  function normalizeMapCategory(category) {
    return {
      label: category.label,
      slug: slugifyTag(category.label),
      matchSlugs: new Set((category.matches || []).map(slugifyTag).filter(Boolean)),
    };
  }

  function getOtherCategory(categoryMap) {
    return (categoryMap?.categories || [])
      .map(normalizeMapCategory)
      .find((category) => category.slug === 'other') || null;
  }

  function getDirectMappedCategoriesForTags(tags, categoryMap) {
    const normalizedTags = Array.isArray(tags) ? tags.map(slugifyTag).filter(Boolean) : [];
    const mappedCategories = (categoryMap?.categories || [])
      .map(normalizeMapCategory)
      .filter((category) => normalizedTags.some((tag) => category.matchSlugs.has(tag)));

    if (mappedCategories.length > 0) {
      return mappedCategories;
    }

    const otherCategory = getOtherCategory(categoryMap);
    return otherCategory ? [otherCategory] : [];
  }

  function isTechOnlyEvent(tags) {
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
      'civic-tech',
    ]);
    const genericTechTags = new Set([
      'tech-skills',
      'tech-community',
      'code-collective-and-partners',
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
      'finance',
    ]);

    if (Array.from(normalizedTags).some((tag) => specificTechTags.has(tag))) {
      return true;
    }

    if (!Array.from(normalizedTags).some((tag) => genericTechTags.has(tag))) {
      return false;
    }

    if (Array.from(normalizedTags).some((tag) => dominantNonTechTags.has(tag))) {
      return false;
    }

    return true;
  }

  function getEffectiveMappedCategories(tags, categoryMap) {
    if (categoryMap?.id === 'tech_only' && !isTechOnlyEvent(tags)) {
      return [];
    }
    return getDirectMappedCategoriesForTags(tags, categoryMap);
  }

  function isExcludedFromActiveMap(tags, categoryMap) {
    if (categoryMap?.id === 'tech_only' && !isTechOnlyEvent(tags)) {
      return true;
    }
    return getDirectMappedCategoriesForTags(tags, categoryMap).length === 0;
  }

  function eventMatchesTags(params) {
    const tags = params?.tags;
    const categoryMap = params?.categoryMap;
    const activeTagSlugs = params?.activeTagSlugs;
    const showExcludedEvents = params?.showExcludedEvents === true;

    const mappedCategories = getEffectiveMappedCategories(tags, categoryMap);
    if (mappedCategories.length === 0) {
      return showExcludedEvents;
    }
    if (!activeTagSlugs || activeTagSlugs.size === 0) return false;
    return mappedCategories.some((category) => activeTagSlugs.has(category.slug));
  }

  function toFiniteNumber(value) {
    const number = Number(value);
    return Number.isFinite(number) ? number : null;
  }

  function normalizeCoordinate(value) {
    const number = toFiniteNumber(value);
    return number === null ? null : number;
  }

  function getLocationCoordinates(location) {
    if (!location || typeof location !== 'object') return null;
    const latitude = normalizeCoordinate(location.latitude ?? location.lat);
    const longitude = normalizeCoordinate(location.longitude ?? location.lng ?? location.lon);
    if (latitude === null || longitude === null) return null;
    if (latitude < -90 || latitude > 90 || longitude < -180 || longitude > 180) return null;
    return { latitude, longitude };
  }

  function isGenericLocationText(value) {
    const normalized = normalizeAddressKey(value);
    return [
      '',
      'united states',
      'usa',
      'u.s.',
      'u.s.a.',
      'online',
      'virtual',
      'zoom',
      'tbd',
      'to be determined',
    ].includes(normalized);
  }

  function isUsableProximityLocation(location) {
    if (!getLocationCoordinates(location)) return false;
    const parts = getLocationTextParts(location);
    if (String(location?.geocode_status || '').toLowerCase().includes('low_quality')) return false;
    if (parts.length === 0) return true;
    return parts.some((part) => !isGenericLocationText(part));
  }

  function degreesToRadians(degrees) {
    return degrees * Math.PI / 180;
  }

  function distanceMiles(pointA, pointB) {
    const a = getLocationCoordinates(pointA);
    const b = getLocationCoordinates(pointB);
    if (!a || !b) return null;

    const earthRadiusMiles = 3958.7613;
    const latDelta = degreesToRadians(b.latitude - a.latitude);
    const lonDelta = degreesToRadians(b.longitude - a.longitude);
    const latA = degreesToRadians(a.latitude);
    const latB = degreesToRadians(b.latitude);
    const haversine =
      Math.sin(latDelta / 2) ** 2 +
      Math.cos(latA) * Math.cos(latB) * Math.sin(lonDelta / 2) ** 2;

    return 2 * earthRadiusMiles * Math.asin(Math.min(1, Math.sqrt(haversine)));
  }

  function parseLatLongQuery(query) {
    const value = String(query || '').trim();
    if (!value) return null;

    const labeled = value.match(/lat(?:itude)?\s*[:=]?\s*(-?\d+(?:\.\d+)?)[^\d-]+(?:lon|lng|long|longitude)?\s*[:=]?\s*(-?\d+(?:\.\d+)?)/i);
    const pair = labeled || value.match(/^\s*(-?\d+(?:\.\d+)?)\s*[, ]\s*(-?\d+(?:\.\d+)?)\s*$/);
    if (!pair) return null;

    const latitude = normalizeCoordinate(pair[1]);
    const longitude = normalizeCoordinate(pair[2]);
    return getLocationCoordinates({ latitude, longitude });
  }

  function normalizeAddressKey(value) {
    return String(value || '')
      .toLowerCase()
      .replace(/\s+/g, ' ')
      .trim();
  }

  function extractZipCode(value) {
    const match = String(value || '').match(/\b\d{5}(?:-\d{4})?\b/);
    return match ? match[0].slice(0, 5) : '';
  }

  function getLocationTextParts(location) {
    if (!location || typeof location !== 'object') return [];
    return [
      location.name,
      location.address,
      location.city,
      location.state,
      location.country,
      location.geocode_query,
    ].filter(Boolean).map(String);
  }

  function collectCandidateCoordinates(events, geocodeCache) {
    const candidates = [];
    const seen = new Set();
    const addCandidate = (label, coords, source) => {
      const point = getLocationCoordinates(coords);
      const key = normalizeAddressKey(label);
      if (!key || !point) return;
      if (isGenericLocationText(label)) return;
      const seenKey = `${source}:${key}:${point.latitude},${point.longitude}`;
      if (seen.has(seenKey)) return;
      seen.add(seenKey);
      candidates.push({
        label,
        key,
        zip: extractZipCode(label),
        latitude: point.latitude,
        longitude: point.longitude,
        source,
      });
    };

    (Array.isArray(events) ? events : []).forEach((event) => {
      const location = event?.location || event?.extendedProps?.location || null;
      const coords = getLocationCoordinates(location);
      if (!coords || !isUsableProximityLocation(location)) return;
      getLocationTextParts(location).forEach((part) => addCandidate(part, coords, 'event'));
    });

    Object.entries(geocodeCache || {}).forEach(([label, coords]) => {
      addCandidate(label, coords, 'cache');
    });

    return candidates;
  }

  function averageCoordinates(candidates) {
    if (!Array.isArray(candidates) || candidates.length === 0) return null;
    const totals = candidates.reduce((acc, candidate) => {
      acc.latitude += candidate.latitude;
      acc.longitude += candidate.longitude;
      return acc;
    }, { latitude: 0, longitude: 0 });
    return {
      latitude: totals.latitude / candidates.length,
      longitude: totals.longitude / candidates.length,
      matchedCandidates: candidates.length,
    };
  }

  function resolveProximityQuery(query, events, geocodeCache) {
    const coordinateQuery = parseLatLongQuery(query);
    if (coordinateQuery) {
      return { ...coordinateQuery, source: 'coordinates', label: String(query || '').trim() };
    }

    const normalizedQuery = normalizeAddressKey(query);
    if (!normalizedQuery) return null;

    const candidates = collectCandidateCoordinates(events, geocodeCache);
    const zip = extractZipCode(normalizedQuery);
    if (zip) {
      const zipMatches = candidates.filter((candidate) => candidate.zip === zip);
      const averagedZip = averageCoordinates(zipMatches);
      if (averagedZip) return { ...averagedZip, source: 'zip', label: zip };
    }

    const exact = candidates.find((candidate) => candidate.key === normalizedQuery);
    if (exact) return { latitude: exact.latitude, longitude: exact.longitude, source: exact.source, label: exact.label };

    const containsMatches = candidates.filter((candidate) => (
      candidate.key.includes(normalizedQuery) || normalizedQuery.includes(candidate.key)
    ));
    const averagedContains = averageCoordinates(containsMatches);
    if (averagedContains) {
      return { ...averagedContains, source: 'address', label: query };
    }

    return null;
  }

  function minutesFromTimeString(value) {
    const raw = String(value || '').trim();
    if (!raw) return null;
    const match = raw.match(/^(\d{1,2})(?::(\d{2}))?\s*(am|pm)?$/i);
    if (!match) return null;

    let hours = Number(match[1]);
    const minutes = Number(match[2] || 0);
    const meridiem = match[3]?.toLowerCase();
    if (!Number.isInteger(hours) || !Number.isInteger(minutes) || minutes < 0 || minutes > 59) return null;
    if (meridiem) {
      if (hours < 1 || hours > 12) return null;
      if (meridiem === 'pm' && hours !== 12) hours += 12;
      if (meridiem === 'am' && hours === 12) hours = 0;
    } else if (hours > 23) {
      return null;
    }

    return hours * 60 + minutes;
  }

  function minutesForDateInTimeZone(dateInput, timeZone) {
    const date = dateInput instanceof Date ? dateInput : new Date(dateInput);
    if (isNaN(date)) return null;
    const options = {
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    };
    if (timeZone) options.timeZone = timeZone;
    const parts = new Intl.DateTimeFormat('en-US', options).formatToParts(date);
    const values = {};
    parts.forEach((part) => {
      if (part.type !== 'literal') values[part.type] = part.value;
    });
    const hour = Number(values.hour === '24' ? '0' : values.hour);
    const minute = Number(values.minute);
    if (!Number.isFinite(hour) || !Number.isFinite(minute)) return null;
    return hour * 60 + minute;
  }

  function dateKeyInTimeZone(dateInput, timeZone) {
    const date = dateInput instanceof Date ? dateInput : new Date(dateInput);
    if (isNaN(date)) return '';
    const options = {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    };
    if (timeZone) options.timeZone = timeZone;
    const parts = new Intl.DateTimeFormat('en-CA', options).formatToParts(date);
    const values = {};
    parts.forEach((part) => {
      if (part.type !== 'literal') values[part.type] = part.value;
    });
    return values.year && values.month && values.day ? `${values.year}-${values.month}-${values.day}` : '';
  }

  function dayIndexInTimeZone(dateInput, timeZone) {
    const date = dateInput instanceof Date ? dateInput : new Date(dateInput);
    if (isNaN(date)) return null;
    const options = { weekday: 'short' };
    if (timeZone) options.timeZone = timeZone;
    const weekday = new Intl.DateTimeFormat('en-US', options).format(date).toLowerCase();
    return {
      sun: 0,
      mon: 1,
      tue: 2,
      wed: 3,
      thu: 4,
      fri: 5,
      sat: 6,
    }[weekday.slice(0, 3)] ?? null;
  }

  function eventMatchesTimeFilters(event, filters) {
    const startValue = event?.start || event?.startDate;
    if (!startValue) return false;
    const eventDate = new Date(startValue);
    if (isNaN(eventDate)) return false;

    const timeZone = filters?.timeZone || '';
    const eventDateKey = dateKeyInTimeZone(eventDate, timeZone);
    if (filters?.dateFrom && eventDateKey < filters.dateFrom) return false;
    if (filters?.dateTo && eventDateKey > filters.dateTo) return false;

    const daysOfWeek = Array.isArray(filters?.daysOfWeek) ? filters.daysOfWeek : [];
    if (daysOfWeek.length > 0) {
      const dayIndex = dayIndexInTimeZone(eventDate, timeZone);
      if (!daysOfWeek.includes(dayIndex)) return false;
    }

    const startMinutes = minutesFromTimeString(filters?.timeStart);
    const endMinutes = minutesFromTimeString(filters?.timeEnd);
    if (startMinutes === null && endMinutes === null) return true;

    const eventMinutes = minutesForDateInTimeZone(eventDate, timeZone);
    if (eventMinutes === null) return false;

    if (startMinutes !== null && endMinutes !== null && startMinutes > endMinutes) {
      return eventMinutes >= startMinutes || eventMinutes <= endMinutes;
    }
    if (startMinutes !== null && eventMinutes < startMinutes) return false;
    if (endMinutes !== null && eventMinutes > endMinutes) return false;
    return true;
  }

  return {
    slugifyTag,
    normalizeMapCategory,
    getOtherCategory,
    getDirectMappedCategoriesForTags,
    isTechOnlyEvent,
    getEffectiveMappedCategories,
    isExcludedFromActiveMap,
    eventMatchesTags,
    getLocationCoordinates,
    isUsableProximityLocation,
    distanceMiles,
    parseLatLongQuery,
    extractZipCode,
    collectCandidateCoordinates,
    resolveProximityQuery,
    minutesFromTimeString,
    dateKeyInTimeZone,
    eventMatchesTimeFilters,
  };
});
