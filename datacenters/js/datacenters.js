(() => {
  const DATA_URLS = {
    datacenters: '/datacenters/data/datacenters.json',
    plants: '/datacenters/data/power-plants.json',
    plantImages: '/datacenters/data/power-plant-images.json',
    sources: '/datacenters/data/sources.json',
  };
  const PLANT_IMAGE_FALLBACK = '/datacenters/images/power-plants/fallback/energy-infrastructure-illustration.webp';
  const USGS_IMAGERY_SOURCE = 'https://basemap.nationalmap.gov/arcgis/rest/services/USGSImageryOnly/MapServer';
  const ENVIROSCREEN_SERVICE = 'https://mdgeodata.md.gov/imap/rest/services/Environment/MD_EnviroScreen/FeatureServer/0';
  const ENVIROSCREEN_QUERY = `${ENVIROSCREEN_SERVICE}/query?${new URLSearchParams({
    where: '1=1',
    outFields: 'GEOID20,P_EJ,OVERBURDENED_COMMUNITY,UNDERSERVED_COMMUNITY',
    returnGeometry: 'true',
    outSR: '4326',
    geometryPrecision: '5',
    maxAllowableOffset: '0.0001',
    f: 'geojson',
  })}`;
  const ENVIROSCREEN_SOURCE_ID = 'mde-enviroscreen';
  const ENVIROSCREEN_FILL_ID = 'mde-enviroscreen-fill';
  const ENVIROSCREEN_LINE_ID = 'mde-enviroscreen-line';
  const PARCEL_SERVICE = 'https://mdgeodata.md.gov/imap/rest/services/PlanningCadastre/MD_ParcelBoundaries/MapServer';
  const PARCEL_SOURCE_ID = 'mdp-sdat-parcels';
  const PARCEL_LAYER_ID = 'mdp-sdat-parcels-line';
  const PARCEL_HOVER_SOURCE_ID = 'mdp-sdat-parcel-hover';
  const PARCEL_HOVER_FILL_ID = 'mdp-sdat-parcel-hover-fill';
  const PARCEL_HOVER_LINE_ID = 'mdp-sdat-parcel-hover-line';
  const PARCEL_MIN_ZOOM = 13;
  const PARCEL_MAX_FEATURES = 1000;
  const BASEMAP_STYLES = {
    collective: 'https://tiles.openfreemap.org/styles/liberty',
    dark: 'https://tiles.openfreemap.org/styles/dark',
    fiord: 'https://tiles.openfreemap.org/styles/fiord',
    positron: 'https://tiles.openfreemap.org/styles/positron',
    bright: 'https://tiles.openfreemap.org/styles/bright',
    liberty: 'https://tiles.openfreemap.org/styles/liberty',
  };
  const ENERGY_SOURCES = {
    SUN: { label: 'Solar', light: '#69c7ff', color: '#167fc1', dark: '#064a7d' },
    BIT: { label: 'Coal', light: '#59616a', color: '#20262c', dark: '#050708' },
    SUB: { label: 'Coal', light: '#59616a', color: '#20262c', dark: '#050708' },
    LIG: { label: 'Coal', light: '#59616a', color: '#20262c', dark: '#050708' },
    WC: { label: 'Coal', light: '#59616a', color: '#20262c', dark: '#050708' },
    RC: { label: 'Coal', light: '#59616a', color: '#20262c', dark: '#050708' },
    NG: { label: 'Natural gas', light: '#c58a62', color: '#865033', dark: '#4a281b' },
    PG: { label: 'Propane gas', light: '#c58a62', color: '#865033', dark: '#4a281b' },
    DFO: { label: 'Oil / diesel', light: '#ffb454', color: '#c76522', dark: '#743010' },
    RFO: { label: 'Oil / diesel', light: '#ffb454', color: '#c76522', dark: '#743010' },
    WAT: { label: 'Hydroelectric', light: '#70ebef', color: '#16a5b5', dark: '#075f74' },
    WND: { label: 'Wind', light: '#95e59b', color: '#3caa62', dark: '#17633b' },
    NUC: { label: 'Nuclear', light: '#d2a5ff', color: '#8754bd', dark: '#4d267b' },
    MWH: { label: 'Battery storage', light: '#d7b4ff', color: '#8d65ca', dark: '#4c317e' },
    LFG: { label: 'Landfill gas', light: '#b7cf70', color: '#718e39', dark: '#3d5520' },
    MSW: { label: 'Municipal waste', light: '#f4d06f', color: '#b38b25', dark: '#695012' },
    MSB: { label: 'Municipal waste', light: '#f4d06f', color: '#b38b25', dark: '#695012' },
    MSN: { label: 'Municipal waste', light: '#f4d06f', color: '#b38b25', dark: '#695012' },
    OBG: { label: 'Biomass', light: '#d0c779', color: '#8b8436', dark: '#514c1e' },
    WDS: { label: 'Biomass', light: '#d0c779', color: '#8b8436', dark: '#514c1e' },
    UNKNOWN: { label: 'Undisclosed', light: '#aab9c5', color: '#657887', dark: '#344550' },
  };

  const escapeHtml = (value) => String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');

  const known = (value, suffix = '') => value === null || value === undefined || value === ''
    ? '<span class="dc-unknown">Not publicly disclosed</span>'
    : `${escapeHtml(value)}${suffix}`;

  const number = (value, digits = 0) => Number(value).toLocaleString('en-US', {
    maximumFractionDigits: digits,
  });

  function markerSourceCodes(record) {
    if (record.record_type === 'power_plant') {
      const codes = record.generation_fuel_codes?.length
        ? record.generation_fuel_codes
        : record.energy_source_codes;
      return [...new Set(codes?.filter((code) => ENERGY_SOURCES[code]) || [])];
    }

    const codes = [];
    const onSite = String(record.on_site_generation_technology || '').toLowerCase();
    const gas = String(record.on_site_natural_gas_power_plant || '').toLowerCase();
    const backup = String(record.backup_generation_fuel || '').toLowerCase();
    if (onSite.includes('battery')) codes.push('MWH');
    if (gas.includes('natural gas') && !/not identified|not disclosed/.test(gas)) codes.push('NG');
    if (/diesel|fuel oil/.test(backup)) codes.push('DFO');
    return [...new Set(codes)];
  }

  function markerGradient(sourceCodes) {
    const sources = (sourceCodes.length ? sourceCodes : ['UNKNOWN'])
      .map((code) => ENERGY_SOURCES[code])
      .filter((source, index, all) => all.findIndex((candidate) => candidate.label === source.label) === index);
    const highlight = 'radial-gradient(circle at 30% 22%, rgba(255,255,255,.78) 0 7%, rgba(255,255,255,.2) 22%, transparent 48%)';
    if (sources.length === 1) {
      const source = sources[0];
      return `${highlight}, linear-gradient(145deg, ${source.light} 0%, ${source.color} 48%, ${source.dark} 100%)`;
    }
    const stops = sources.flatMap((source, index) => {
      const start = (index / sources.length) * 100;
      const end = ((index + 1) / sources.length) * 100;
      return `${source.color} ${start}% ${end}%`;
    }).join(', ');
    return `${highlight}, conic-gradient(from -35deg, ${stops})`;
  }

  function markerSourceLabel(sourceCodes) {
    const codes = sourceCodes.length ? sourceCodes : ['UNKNOWN'];
    return [...new Set(codes.map((code) => ENERGY_SOURCES[code].label))].join(' + ');
  }
  let selectedRecordId = null;
  let plantImageById = new Map();
  let enviroScreenData = null;
  let enviroScreenRequest = null;
  let parcelHoverTimer = null;
  let parcelHoverAbort = null;
  let parcelBoundaryAbort = null;
  let hoveredParcel = null;

  Promise.all(Object.entries(DATA_URLS).map(async ([key, url]) => {
    const response = await fetch(url, { cache: 'no-store' });
    if (!response.ok) throw new Error(`${url}: HTTP ${response.status}`);
    return [key, await response.json()];
  }))
    .then((entries) => initialize(Object.fromEntries(entries)))
    .catch((error) => {
      document.getElementById('record-detail').innerHTML = `<h2>Data unavailable</h2><p>${escapeHtml(error.message)}</p>`;
    });

  function initialize(data) {
    const sourceById = new Map(data.sources.map((source) => [source.id, source]));
    plantImageById = new Map(data.plantImages.map((image) => [image.plant_id, image]));
    const themeSelect = document.getElementById('map-theme');
    const map = new maplibregl.Map({
      container: 'datacenter-map',
      style: BASEMAP_STYLES[themeSelect.value],
      center: [-76.75, 39.05],
      zoom: 7.25,
      maxZoom: 18,
      attributionControl: false,
    });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-left');
    map.addControl(new maplibregl.AttributionControl({ compact: true }), 'bottom-right');
    map.on('style.load', () => {
      if (themeSelect.value === 'collective') applyCollectiveTheme(map);
      if (document.getElementById('show-enviroscreen').checked) setEnviroScreenVisibility(map, true);
      if (document.getElementById('show-parcels').checked) setParcelVisibility(map, true);
    });
    themeSelect.addEventListener('change', () => {
      map.setStyle(BASEMAP_STYLES[themeSelect.value]);
    });

    const markerById = new Map();
    const allRecords = [...data.datacenters, ...data.plants];

    allRecords.forEach((record) => {
      if (!Number.isFinite(record.latitude) || !Number.isFinite(record.longitude)) return;
      const isCenter = record.record_type === 'data_center';
      const sourceCodes = markerSourceCodes(record);
      const sourceLabel = markerSourceLabel(sourceCodes);
      const element = document.createElement('button');
      element.type = 'button';
      element.className = `dc-map-marker dc-map-marker--${isCenter ? 'center' : 'plant'}`;
      element.setAttribute('aria-label', record.name);
      element.title = `${record.name} · ${sourceLabel}`;
      element.dataset.energySources = sourceCodes.length ? sourceCodes.join(' ') : 'UNKNOWN';
      element.style.setProperty('--marker-source-gradient', markerGradient(sourceCodes));
      element.innerHTML = `<span class="dc-map-icon dc-map-icon--${isCenter ? 'center' : 'plant'}"></span>`;
      element.addEventListener('click', () => selectRecord(record, sourceById));
      element.addEventListener('pointerenter', () => selectRecord(record, sourceById));
      element.addEventListener('focus', () => selectRecord(record, sourceById));
      const popupText = `${record.name} · ${sourceLabel}${isCenter ? '' : ` · ${number(record.nameplate_capacity_mw, 1)} MW`}`;
      const marker = new maplibregl.Marker({ element, anchor: 'center' })
        .setLngLat([record.longitude, record.latitude])
        .setPopup(new maplibregl.Popup({ offset: 16, closeButton: false }).setText(popupText))
        .addTo(map);
      markerById.set(record.id, marker);
    });

    document.getElementById('type-filter').addEventListener('change', () => renderResults(allRecords, markerById, map));
    document.getElementById('show-enviroscreen').addEventListener('change', (event) => {
      setEnviroScreenVisibility(map, event.target.checked);
    });
    document.getElementById('show-parcels').addEventListener('change', (event) => {
      setParcelVisibility(map, event.target.checked);
    });
    document.getElementById('map-search').addEventListener('input', () => renderResults(allRecords, markerById, map));
    document.getElementById('status-filter').addEventListener('change', () => renderResults(allRecords, markerById, map));
    document.getElementById('energy-filter').addEventListener('change', () => renderResults(allRecords, markerById, map));
    document.getElementById('sentiment-filter').addEventListener('change', () => renderResults(allRecords, markerById, map));

    renderResults(allRecords, markerById, map);
    renderSources(data.sources);
    map.on('mousemove', (event) => handleMapHover(map, event));
    map.on('moveend', () => loadParcelBoundaries(map));
  }

  function applyCollectiveTheme(map) {
    const setPaint = (layer, property, value) => {
      try {
        map.setPaintProperty(layer.id, property, value);
      } catch (_error) {
        // A provider theme may omit an optional paint property for a layer.
      }
    };

    map.getStyle().layers.forEach((layer) => {
      const semantic = `${layer.id} ${layer['source-layer'] || ''}`.toLowerCase();
      const isWater = semantic.includes('water');
      const isRoad = /road|transportation|bridge|tunnel|motorway|trunk/.test(semantic);
      const isRail = semantic.includes('rail');
      const isBoundary = /boundary|admin/.test(semantic);
      const isPark = /park|landcover|wood|grass|wetland/.test(semantic);
      const isBuilding = semantic.includes('building');

      if (layer.type === 'background') {
        setPaint(layer, 'background-color', '#001a3d');
      } else if (layer.type === 'raster') {
        setPaint(layer, 'raster-saturation', -1);
        setPaint(layer, 'raster-contrast', .18);
        setPaint(layer, 'raster-brightness-min', .06);
        setPaint(layer, 'raster-brightness-max', .28);
      } else if (layer.type === 'fill') {
        setPaint(layer, 'fill-pattern', null);
        setPaint(layer, 'fill-color', isWater
          ? '#075d8f'
          : isPark
            ? '#073954'
            : isBuilding
              ? '#16466f'
              : '#082950');
        setPaint(layer, 'fill-outline-color', isWater ? '#147fb5' : '#17466d');
      } else if (layer.type === 'fill-extrusion') {
        setPaint(layer, 'fill-extrusion-color', '#16466f');
      } else if (layer.type === 'line') {
        setPaint(layer, 'line-color', isWater
          ? '#2697c8'
          : isRoad && !isRail
            ? roadColor(semantic)
            : isBoundary
              ? '#5794bd'
              : '#245271');
        if (isRoad && !isRail) {
          setPaint(layer, 'line-width', roadWidth(semantic));
          setPaint(layer, 'line-opacity', roadOpacity(semantic));
        }
      } else if (layer.type === 'symbol') {
        setPaint(layer, 'text-color', '#b8d9e8');
        setPaint(layer, 'text-halo-color', '#00162f');
        setPaint(layer, 'text-halo-width', 1.1);
      }
    });
  }

  function roadColor(semantic) {
    if (semantic.includes('casing')) return '#102f4d';
    if (semantic.includes('motorway')) return '#7eb2d0';
    if (/trunk|primary/.test(semantic)) return '#6899b9';
    if (/secondary|tertiary/.test(semantic)) return '#4f7d9f';
    return '#365f80';
  }

  function roadWidth(semantic) {
    const isCasing = semantic.includes('casing');
    let stops;
    if (semantic.includes('motorway')) {
      stops = [[5, .42], [8, .6], [11, .92], [14, 1.55], [18, 4.1]];
    } else if (/trunk|primary/.test(semantic)) {
      stops = [[5, .32], [8, .48], [11, .76], [14, 1.3], [18, 3.5]];
    } else if (/secondary|tertiary/.test(semantic)) {
      stops = [[7, .16], [10, .32], [13, .68], [16, 1.4], [19, 3.1]];
    } else if (/service|track|path|pedestrian/.test(semantic)) {
      stops = [[12, 0], [14, .16], [16, .48], [19, 1.25]];
    } else {
      stops = [[10, 0], [12, .16], [14, .42], [16, .88], [19, 2.15]];
    }
    const scaledStops = stops.flatMap(([zoom, width]) => [
      zoom,
      isCasing && width > 0 ? (width * 1.35) + .16 : width,
    ]);
    return ['interpolate', ['exponential', 1.25], ['zoom'], ...scaledStops];
  }

  function roadOpacity(semantic) {
    if (/service|track|path|pedestrian/.test(semantic)) {
      return ['interpolate', ['linear'], ['zoom'], 12, 0, 14, .42, 17, .72, 19, .86];
    }
    if (/minor|street/.test(semantic)) {
      return ['interpolate', ['linear'], ['zoom'], 10, 0, 12, .38, 15, .7, 18, .86];
    }
    return semantic.includes('casing') ? .82 : .92;
  }

  async function setEnviroScreenVisibility(map, enabled) {
    const toggle = document.getElementById('show-enviroscreen');
    const legend = document.getElementById('enviroscreen-legend');
    const status = document.getElementById('enviroscreen-status');
    legend.hidden = !enabled;
    legend.classList.remove('is-error');

    if (!enabled) {
      [ENVIROSCREEN_FILL_ID, ENVIROSCREEN_LINE_ID].forEach((layerId) => {
        if (map.getLayer(layerId)) map.setLayoutProperty(layerId, 'visibility', 'none');
      });
      toggle.removeAttribute('aria-busy');
      return;
    }

    status.textContent = 'Loading official MDE census-tract data…';
    toggle.setAttribute('aria-busy', 'true');
    try {
      if (!enviroScreenData) {
        enviroScreenRequest ||= fetch(ENVIROSCREEN_QUERY).then((response) => {
          if (!response.ok) throw new Error(`MDE service returned HTTP ${response.status}`);
          return response.json();
        });
        enviroScreenData = await enviroScreenRequest;
      }
      if (!toggle.checked) return;
      addEnviroScreenLayers(map, enviroScreenData);
      status.textContent = `${number(enviroScreenData.features.length)} census tracts · MDE V3, updated July 24, 2025`;
    } catch (error) {
      enviroScreenRequest = null;
      legend.classList.add('is-error');
      status.textContent = `Layer unavailable: ${error.message}`;
    } finally {
      toggle.removeAttribute('aria-busy');
    }
  }

  function addEnviroScreenLayers(map, data) {
    if (!map.getSource(ENVIROSCREEN_SOURCE_ID)) {
      map.addSource(ENVIROSCREEN_SOURCE_ID, { type: 'geojson', data });
    }
    const firstLabel = map.getStyle().layers.find((layer) => layer.type === 'symbol')?.id;
    if (!map.getLayer(ENVIROSCREEN_FILL_ID)) {
      map.addLayer({
        id: ENVIROSCREEN_FILL_ID,
        type: 'fill',
        source: ENVIROSCREEN_SOURCE_ID,
        paint: {
          'fill-color': [
            'step', ['coalesce', ['get', 'P_EJ'], 0],
            '#01856f', 25,
            '#81ccbf', 50,
            '#dec17e', 75,
            '#a6601b',
          ],
          'fill-opacity': .48,
        },
      }, firstLabel);
    }
    if (!map.getLayer(ENVIROSCREEN_LINE_ID)) {
      map.addLayer({
        id: ENVIROSCREEN_LINE_ID,
        type: 'line',
        source: ENVIROSCREEN_SOURCE_ID,
        paint: {
          'line-color': 'rgba(230, 244, 251, .48)',
          'line-width': ['interpolate', ['linear'], ['zoom'], 6, .25, 11, .7, 15, 1.1],
        },
      }, firstLabel);
    }
    map.setLayoutProperty(ENVIROSCREEN_FILL_ID, 'visibility', 'visible');
    map.setLayoutProperty(ENVIROSCREEN_LINE_ID, 'visibility', 'visible');
  }

  function setParcelVisibility(map, enabled) {
    const legend = document.getElementById('parcel-legend');
    legend.hidden = !enabled;
    legend.classList.remove('is-error');
    if (!enabled) {
      parcelHoverAbort?.abort();
      parcelBoundaryAbort?.abort();
      clearTimeout(parcelHoverTimer);
      hoveredParcel = null;
      [PARCEL_LAYER_ID, PARCEL_HOVER_FILL_ID, PARCEL_HOVER_LINE_ID].forEach((layerId) => {
        if (map.getLayer(layerId)) map.setLayoutProperty(layerId, 'visibility', 'none');
      });
      map.getCanvas().style.cursor = '';
      return;
    }

    try {
      if (!map.getSource(PARCEL_SOURCE_ID)) {
        map.addSource(PARCEL_SOURCE_ID, {
          type: 'geojson',
          data: { type: 'FeatureCollection', features: [] },
          attribution: 'Parcel boundaries: MD iMAP, MDP, SDAT',
        });
      }
      const firstLabel = map.getStyle().layers.find((layer) => layer.type === 'symbol')?.id;
      if (!map.getLayer(PARCEL_LAYER_ID)) {
        map.addLayer({
          id: PARCEL_LAYER_ID,
          type: 'line',
          source: PARCEL_SOURCE_ID,
          minzoom: PARCEL_MIN_ZOOM,
          paint: {
            'line-color': 'rgba(121, 207, 241, .82)',
            'line-width': ['interpolate', ['linear'], ['zoom'], 13, .7, 16, 1.2, 19, 1.8],
          },
        }, firstLabel);
      }
      map.setLayoutProperty(PARCEL_LAYER_ID, 'visibility', 'visible');
      ensureParcelHoverLayers(map, firstLabel);
      loadParcelBoundaries(map);
    } catch (error) {
      legend.classList.add('is-error');
      document.getElementById('parcel-status').textContent = `Layer unavailable: ${error.message}`;
    }
  }

  function ensureParcelHoverLayers(map, firstLabel) {
    if (!map.getSource(PARCEL_HOVER_SOURCE_ID)) {
      map.addSource(PARCEL_HOVER_SOURCE_ID, {
        type: 'geojson',
        data: { type: 'FeatureCollection', features: [] },
      });
    }
    if (!map.getLayer(PARCEL_HOVER_FILL_ID)) {
      map.addLayer({
        id: PARCEL_HOVER_FILL_ID,
        type: 'fill',
        source: PARCEL_HOVER_SOURCE_ID,
        paint: { 'fill-color': '#f3a712', 'fill-opacity': .16 },
      }, firstLabel);
    }
    if (!map.getLayer(PARCEL_HOVER_LINE_ID)) {
      map.addLayer({
        id: PARCEL_HOVER_LINE_ID,
        type: 'line',
        source: PARCEL_HOVER_SOURCE_ID,
        paint: { 'line-color': '#ffd582', 'line-width': 2 },
      }, firstLabel);
    }
    map.setLayoutProperty(PARCEL_HOVER_FILL_ID, 'visibility', 'visible');
    map.setLayoutProperty(PARCEL_HOVER_LINE_ID, 'visibility', 'visible');
    if (hoveredParcel) map.getSource(PARCEL_HOVER_SOURCE_ID).setData(hoveredParcel);
  }

  function updateParcelStatus(map) {
    if (!document.getElementById('show-parcels').checked) return;
    const status = document.getElementById('parcel-status');
    status.textContent = map.getZoom() < PARCEL_MIN_ZOOM
      ? `Zoom in to level ${PARCEL_MIN_ZOOM} to display and inspect parcels.`
      : 'Property boundaries visible · hover a parcel to query MDP/SDAT.';
  }

  async function loadParcelBoundaries(map) {
    if (!document.getElementById('show-parcels').checked || !map.getSource(PARCEL_SOURCE_ID)) return;
    parcelBoundaryAbort?.abort();
    const source = map.getSource(PARCEL_SOURCE_ID);
    if (map.getZoom() < PARCEL_MIN_ZOOM) {
      source.setData({ type: 'FeatureCollection', features: [] });
      updateParcelStatus(map);
      return;
    }

    const bounds = map.getBounds();
    const parameters = new URLSearchParams({
      where: '1=1',
      geometry: `${bounds.getWest()},${bounds.getSouth()},${bounds.getEast()},${bounds.getNorth()}`,
      geometryType: 'esriGeometryEnvelope',
      inSR: '4326',
      spatialRel: 'esriSpatialRelIntersects',
      outFields: 'ACCTID',
      returnGeometry: 'true',
      outSR: '4326',
      geometryPrecision: '6',
      maxAllowableOffset: '0.00001',
      resultRecordCount: String(PARCEL_MAX_FEATURES),
      f: 'geojson',
    });
    parcelBoundaryAbort = new AbortController();
    document.getElementById('parcel-status').textContent = 'Loading property boundaries for this view…';
    try {
      const response = await fetch(`${PARCEL_SERVICE}/0/query?${parameters}`, { signal: parcelBoundaryAbort.signal });
      if (!response.ok) throw new Error(`MDP/SDAT service returned HTTP ${response.status}`);
      const data = await response.json();
      if (data.error) throw new Error(data.error.message || 'MDP/SDAT query failed');
      if (!document.getElementById('show-parcels').checked) return;
      source.setData(data);
      document.getElementById('parcel-status').textContent = data.features.length >= PARCEL_MAX_FEATURES
        ? `Showing ${number(data.features.length)} boundaries · zoom in for a complete view.`
        : `${number(data.features.length)} property boundaries visible · hover to look up a record.`;
    } catch (error) {
      if (error.name === 'AbortError') return;
      document.getElementById('parcel-legend').classList.add('is-error');
      document.getElementById('parcel-status').textContent = `Layer unavailable: ${error.message}`;
    }
  }

  function handleMapHover(map, event) {
    const parcelEnabled = document.getElementById('show-parcels').checked && map.getZoom() >= PARCEL_MIN_ZOOM;
    const enviroFeature = map.getLayer(ENVIROSCREEN_FILL_ID)
      ? map.queryRenderedFeatures(event.point, { layers: [ENVIROSCREEN_FILL_ID] })[0]
      : null;

    if (enviroFeature) renderEnviroScreenDetail(enviroFeature.properties);
    if (parcelEnabled) {
      map.getCanvas().style.cursor = 'pointer';
      const insideCurrentParcel = map.getLayer(PARCEL_HOVER_FILL_ID)
        && map.queryRenderedFeatures(event.point, { layers: [PARCEL_HOVER_FILL_ID] }).length > 0;
      if (insideCurrentParcel && hoveredParcel) {
        renderParcelDetail(hoveredParcel.features[0].properties);
        return;
      }
      scheduleParcelLookup(map, event.lngLat);
      return;
    }

    clearTimeout(parcelHoverTimer);
    parcelHoverAbort?.abort();
    map.getCanvas().style.cursor = enviroFeature ? 'pointer' : '';
  }

  function scheduleParcelLookup(map, lngLat) {
    clearTimeout(parcelHoverTimer);
    parcelHoverAbort?.abort();
    parcelHoverTimer = setTimeout(() => lookupParcel(map, lngLat), 180);
  }

  async function lookupParcel(map, lngLat) {
    parcelHoverAbort = new AbortController();
    const fields = [
      'ACCTID', 'ADDRESS', 'PREMSNUM', 'PREMSDIR', 'PREMSNAM', 'PREMSTYP', 'PREMCITY', 'PREMZIP',
      'OWNADD1', 'OWNADD2', 'OWNCITY', 'OWNSTATE', 'OWNERZIP', 'LEGAL1', 'LEGAL2', 'LEGAL3',
      'DESCLU', 'ACRES', 'NFMTTLVL', 'SDATWEBADR', 'SDATDATE', 'POLYDATE', 'MAP', 'GRID', 'PARCEL',
    ].join(',');
    const parameters = new URLSearchParams({
      geometry: `${lngLat.lng},${lngLat.lat}`,
      geometryType: 'esriGeometryPoint',
      inSR: '4326',
      spatialRel: 'esriSpatialRelIntersects',
      outFields: fields,
      returnGeometry: 'true',
      outSR: '4326',
      geometryPrecision: '6',
      resultRecordCount: '1',
      f: 'geojson',
    });
    try {
      const response = await fetch(`${PARCEL_SERVICE}/0/query?${parameters}`, { signal: parcelHoverAbort.signal });
      if (!response.ok) throw new Error(`MDP/SDAT service returned HTTP ${response.status}`);
      const data = await response.json();
      if (!data.features?.length || !document.getElementById('show-parcels').checked) {
        clearParcelHighlight(map);
        return;
      }
      hoveredParcel = data;
      map.getSource(PARCEL_HOVER_SOURCE_ID)?.setData(data);
      renderParcelDetail(data.features[0].properties);
      document.getElementById('parcel-status').textContent = 'Property record loaded from MDP/SDAT.';
    } catch (error) {
      if (error.name === 'AbortError') return;
      const legend = document.getElementById('parcel-legend');
      legend.classList.add('is-error');
      document.getElementById('parcel-status').textContent = `Lookup unavailable: ${error.message}`;
    }
  }

  function clearParcelHighlight(map) {
    hoveredParcel = null;
    map.getSource(PARCEL_HOVER_SOURCE_ID)?.setData({ type: 'FeatureCollection', features: [] });
  }

  function renderEnviroScreenDetail(properties) {
    const detail = document.getElementById('record-detail');
    detail.innerHTML = `
      <h2>MDEnviroScreen tract ${escapeHtml(properties.GEOID20 || 'unknown')}</h2>
      <p class="dc-type">Maryland Department of the Environment · census tract</p>
      ${renderFactGroup('Environmental justice screen', [
        ['EJ score', known(properties.P_EJ)],
        ['Overburdened community', yesNo(properties.OVERBURDENED_COMMUNITY)],
        ['Underserved community', yesNo(properties.UNDERSERVED_COMMUNITY)],
      ])}
      <p class="dc-record-note">The summary score does not include every available MDEnviroScreen layer. Review the underlying indicators and MDE cautions before using it in a decision.</p>
      <div class="dc-record-sources"><strong>Source</strong><ul><li><a href="https://mde.maryland.gov/Environmental_Justice/Pages/MDEnviroScreen.aspx" target="_blank" rel="noopener noreferrer">MDE MDEnviroScreen methodology</a></li></ul></div>`;
  }

  function renderParcelDetail(properties) {
    const premise = properties.ADDRESS || [
      properties.PREMSNUM, properties.PREMSDIR, properties.PREMSNAM, properties.PREMSTYP,
      properties.PREMCITY, properties.PREMZIP,
    ].filter(Boolean).join(' ');
    const mailing = [properties.OWNADD1, properties.OWNADD2, properties.OWNCITY, properties.OWNSTATE, properties.OWNERZIP]
      .filter(Boolean).join(', ');
    const legal = [properties.LEGAL1, properties.LEGAL2, properties.LEGAL3].filter(Boolean).join(' · ');
    const detail = document.getElementById('record-detail');
    detail.innerHTML = `
      <h2>${escapeHtml(premise || `Parcel ${properties.ACCTID || 'unknown'}`)}</h2>
      <p class="dc-type">MDP / SDAT public property record</p>
      ${renderFactGroup('Parcel', [
        ['Account ID', known(properties.ACCTID)],
        ['Premise', known(premise)],
        ['Map / grid / parcel', known([properties.MAP, properties.GRID, properties.PARCEL].filter(Boolean).join(' / '))],
        ['Land use', known(properties.DESCLU)],
        ['Acres', properties.ACRES == null ? known(null) : number(properties.ACRES, 2)],
        ['Legal description', known(legal)],
      ])}
      ${renderFactGroup('Assessment record', [
        ['Appraised full value', properties.NFMTTLVL == null ? known(null) : `$${number(properties.NFMTTLVL)}`],
        ['Assessment data', known(properties.SDATDATE)],
        ['Boundary geometry', known(properties.POLYDATE)],
        ['Mailing address', known(mailing)],
      ])}
      <p class="dc-record-note">Parcel boundaries are planning and assessment references, not legal surveys. Dates can differ between the boundary geometry and linked SDAT assessment record.</p>
      ${properties.SDATWEBADR ? `<div class="dc-record-sources"><strong>Source</strong><ul><li><a href="${escapeHtml(properties.SDATWEBADR)}" target="_blank" rel="noopener noreferrer">Open official SDAT property record</a></li></ul></div>` : ''}`;
  }

  function yesNo(value) {
    if (value === null || value === undefined || value === '') return known(null);
    return Number(value) > 0 ? 'Yes' : 'No';
  }

  function visibleType(record) {
    const typeFilter = document.getElementById('type-filter').value;
    return typeFilter === 'all' || record.record_type === typeFilter;
  }

  function lifecycleStage(record) {
    if (record.record_type === 'power_plant') return 'operating';
    const status = record.status.toLowerCase();
    if (status === 'operating') return 'operating';
    if (/paused|blocked|prohibition|cancel/.test(status)) return 'paused';
    if (/permit|development|construction/.test(status)) return 'development';
    if (/proposed|concept|planned/.test(status)) return 'proposal';
    return 'other';
  }

  function matchesEnergySource(record, energyFilter) {
    if (energyFilter === 'all') return true;
    const codes = markerSourceCodes(record);
    if (energyFilter === 'UNKNOWN') return codes.length === 0;
    const families = {
      BIT: ['BIT', 'SUB', 'LIG', 'WC', 'RC'],
      NG: ['NG', 'PG'],
      DFO: ['DFO', 'RFO'],
      WASTE: ['LFG', 'MSW', 'MSB', 'MSN', 'OBG', 'WDS'],
    };
    return (families[energyFilter] || [energyFilter]).some((code) => codes.includes(code));
  }

  function renderResults(records, markerById, map) {
    const query = document.getElementById('map-search').value.trim().toLowerCase();
    const statusFilter = document.getElementById('status-filter').value;
    const energyFilter = document.getElementById('energy-filter').value;
    const sentimentFilter = document.getElementById('sentiment-filter').value;
    const matches = records.filter((record) => matchesFilters(record, query, statusFilter, energyFilter, sentimentFilter));
    records.forEach((record) => {
      const marker = markerById.get(record.id);
      if (!marker) return;
      marker.getElement().hidden = !matches.includes(record);
    });
    const prioritized = [...matches].sort((a, b) => {
      if (a.record_type !== b.record_type) return a.record_type === 'data_center' ? -1 : 1;
      return a.name.localeCompare(b.name);
    }).slice(0, query ? 80 : 30);
    const list = document.getElementById('result-list');
    list.innerHTML = `<p><strong>${number(matches.length)}</strong> matching records${matches.length > prioritized.length ? `; first ${prioritized.length} shown` : ''}</p>`;
    prioritized.forEach((record) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.dataset.recordId = record.id;
      button.classList.toggle('is-selected', record.id === selectedRecordId);
      button.innerHTML = `<strong>${escapeHtml(record.name)}</strong><small>${escapeHtml(record.record_type === 'data_center' ? record.status : `Existing · ${record.primary_technology || 'Power plant'} · ${number(record.nameplate_capacity_mw || 0, 1)} MW`)}</small>`;
      button.addEventListener('click', () => {
        const marker = markerById.get(record.id);
        if (marker) {
          map.easeTo({ center: marker.getLngLat(), zoom: Math.max(map.getZoom(), 11) });
          marker.getElement().click();
        }
      });
      list.appendChild(button);
    });
  }

  function selectRecord(record, sourceById) {
    selectedRecordId = record.id;
    renderDetail(record, sourceById);
    document.querySelectorAll('.dc-result-list button').forEach((button) => {
      button.classList.toggle('is-selected', button.dataset.recordId === record.id);
    });
  }

  function matchesFilters(record, query, statusFilter, energyFilter, sentimentFilter) {
      if (!visibleType(record)) return false;
      if (statusFilter !== 'all' && lifecycleStage(record) !== statusFilter) return false;
      if (!matchesEnergySource(record, energyFilter)) return false;
      if (sentimentFilter !== 'all') {
        if (record.record_type !== 'data_center') return false;
        const score = record.public_sentiment_score;
        if (sentimentFilter === 'opposed' && !(score < 0)) return false;
        if (sentimentFilter === 'supportive' && !(score > 0)) return false;
        if (sentimentFilter === 'mixed' && score !== 0) return false;
        if (sentimentFilter === 'unknown' && score !== null) return false;
      }
      const haystack = [record.name, record.operator, record.county, record.city, record.primary_technology]
        .filter(Boolean).join(' ').toLowerCase();
      return !query || haystack.includes(query);
  }

  function renderDetail(record, sourceById) {
    const detail = document.getElementById('record-detail');
    if (record.record_type === 'data_center') {
      detail.innerHTML = `
        <h2>${escapeHtml(record.name)}</h2>
        <p class="dc-type">Data center · ${escapeHtml(record.status)}</p>
        ${renderFactGroup('Facility', [
          ['Operator', known(record.operator)],
          ['Owner', known(record.owner)],
          ['Address', known([record.street_address, record.city, record.state, record.postal_code].filter(Boolean).join(', '))],
          ['Plan', known(record.plan_detail)],
          ['Buildings', known(record.building_count)],
          ['Personnel', known(record.employees_current)],
          ['Committed jobs', known(record.employees_committed)],
        ])}
        ${renderFactGroup('Energy and resilience', [
          ['Power capacity', record.reported_power_capacity_mw == null ? known(null) : `${number(record.reported_power_capacity_mw, 2)} MW · ${escapeHtml(record.reported_power_capacity_basis)}`],
          ['Grid demand', known(record.reported_grid_demand_mw, ' MW')],
          ['Annual energy', known(record.reported_annual_energy_mwh, ' MWh')],
          ['PUE', known(record.reported_pue)],
          ['Gas plant', known(record.on_site_natural_gas_power_plant)],
          ['Backup', known(record.backup_generator_detail)],
          ['Backup total', known(record.backup_generator_capacity_mw, ' MW')],
          ['UPS', known(record.ups_technology)],
          ['UPS power', known(record.ups_capacity_mw, ' MW')],
          ['UPS energy', known(record.ups_energy_mwh, ' MWh')],
          ['Cooling/water', known(record.cooling_water_detail)],
        ])}
        ${renderFactGroup('Permits, finance, and public response', [
          ['Permits', known(record.permit_detail)],
          ['Financing', known(record.financing_detail)],
          ['Investment', record.capital_investment_usd == null ? known(null) : `$${number(record.capital_investment_usd)}`],
          ['Public funding', known(record.public_funding_detail)],
          ['Opposition', known(record.public_opposition_status)],
          ['Sentiment', renderSentiment(record)],
          ['Rating basis', known(record.sentiment_basis)],
        ])}
        <p class="dc-record-note">${escapeHtml(record.notes)}</p>
        ${renderRecordSources(record.source_ids, sourceById)}
      `;
    } else {
      detail.innerHTML = `
        <h2>${escapeHtml(record.name)}</h2>
        <p class="dc-type">Power plant · EIA plant ${record.eia_plant_code}</p>
        ${renderPlantImage(record)}
        ${renderFactGroup('Plant profile', [
          ['Operator', known(record.operator)],
          ['County', known(record.county)],
          ['Technology', known(record.primary_technology)],
          ['Fuel codes', known(record.energy_source_codes.join(', '))],
        ])}
        ${renderFactGroup('Production', [
          ['Capacity', known(record.nameplate_capacity_mw, ' MW')],
          ['Generators', known(record.generator_count)],
          [`${record.generation_year} generation`, record.net_generation_mwh == null ? known(null) : `${number(record.net_generation_mwh, 1)} MWh`],
        ])}
        ${renderRecordSources([record.capacity_source_id, record.generation_source_id], sourceById)}
      `;
      bindPlantImageFallback(detail, record);
    }
  }

  function renderPlantImage(record) {
    const verified = plantImageById.get(record.id);
    if (verified) {
      return `
        <figure class="dc-plant-image dc-plant-image--verified">
          <img src="${escapeHtml(verified.local_path)}" alt="${escapeHtml(verified.alt)}" data-fallback="${PLANT_IMAGE_FALLBACK}" decoding="async">
          <figcaption>
            <strong>Verified site photograph</strong>
            <span>${escapeHtml(verified.creator)} · ${escapeHtml(verified.license)}</span>
            <a href="${escapeHtml(verified.source_page_url)}" target="_blank" rel="noopener noreferrer">Image source</a>
          </figcaption>
        </figure>`;
    }

    return `
      <figure class="dc-plant-image dc-plant-image--aerial">
        <img src="${escapeHtml(usgsAerialImageUrl(record))}" alt="Aerial imagery centered on ${escapeHtml(record.name)} at its reported EIA coordinates" data-fallback="${PLANT_IMAGE_FALLBACK}" decoding="async">
        <figcaption>
          <strong>Coordinate-specific aerial context</strong>
          <span>USGS imagery centered on the reported EIA location; not independent facility verification.</span>
          <a href="${USGS_IMAGERY_SOURCE}" target="_blank" rel="noopener noreferrer">USGS source</a>
        </figcaption>
      </figure>`;
  }

  function usgsAerialImageUrl(record) {
    const halfLongitude = .016;
    const halfLatitude = .009;
    const bbox = [
      record.longitude - halfLongitude,
      record.latitude - halfLatitude,
      record.longitude + halfLongitude,
      record.latitude + halfLatitude,
    ].join(',');
    const parameters = new URLSearchParams({
      bbox,
      bboxSR: '4326',
      imageSR: '4326',
      size: '800,450',
      format: 'jpg',
      transparent: 'false',
      f: 'image',
    });
    return `${USGS_IMAGERY_SOURCE}/export?${parameters}`;
  }

  function bindPlantImageFallback(detail, record) {
    const image = detail.querySelector('.dc-plant-image img');
    if (!image) return;
    image.addEventListener('error', () => {
      if (image.dataset.fallbackApplied) return;
      image.dataset.fallbackApplied = 'true';
      image.src = image.dataset.fallback;
      image.alt = `Generated energy infrastructure illustration for ${record.name}`;
      const figure = image.closest('.dc-plant-image');
      figure.className = 'dc-plant-image dc-plant-image--illustration';
      figure.querySelector('figcaption').innerHTML = `
        <strong>Generated fallback illustration</strong>
        <span>Illustrative energy infrastructure; not a depiction of ${escapeHtml(record.name)}.</span>`;
    }, { once: true });
  }

  function renderFactGroup(title, rows) {
    const facts = rows.map(([label, value]) => `<dt>${escapeHtml(label)}</dt><dd>${value}</dd>`).join('');
    return `<section class="dc-fact-group"><h3>${escapeHtml(title)}</h3><dl class="dc-facts">${facts}</dl></section>`;
  }

  function renderSentiment(record) {
    if (record.public_sentiment_score === null) {
      return `<span class="dc-sentiment dc-sentiment--unknown">Not scored · ${escapeHtml(record.public_sentiment_label)}</span>`;
    }
    const modifier = record.public_sentiment_score < 0 ? 'negative' : record.public_sentiment_score > 0 ? 'positive' : 'mixed';
    const signed = record.public_sentiment_score > 0 ? `+${record.public_sentiment_score}` : record.public_sentiment_score;
    return `<span class="dc-sentiment dc-sentiment--${modifier}">${signed} · ${escapeHtml(record.public_sentiment_label)}</span> <small>(${escapeHtml(record.sentiment_confidence)} confidence; assessed ${escapeHtml(record.sentiment_assessed_date)})</small>`;
  }

  function renderRecordSources(ids, sourceById) {
    const links = (ids || []).map((id) => sourceById.get(id)).filter(Boolean).map((source) => {
      const href = source.local_path || source.url;
      return `<li><a href="${escapeHtml(href)}"${source.local_path ? '' : ' target="_blank" rel="noopener noreferrer"'}>${escapeHtml(source.title)}</a></li>`;
    }).join('');
    return links ? `<div class="dc-record-sources"><strong>Sources</strong><ul>${links}</ul></div>` : '';
  }

  function renderSources(sources) {
    document.getElementById('source-list').innerHTML = sources.map((source) => `
      <article class="dc-source-card">
        <h3>${escapeHtml(source.title)}</h3>
        <p>${escapeHtml(source.publisher)} · ${escapeHtml(source.source_tier)} · retrieved ${escapeHtml(source.retrieved_date)}</p>
        <p>${escapeHtml(source.used_for)}</p>
        <a href="${escapeHtml(source.local_path || source.url)}"${source.local_path ? '' : ' target="_blank" rel="noopener noreferrer"'}>${source.local_path ? 'Open archived copy' : 'Open source'}</a>${source.local_path ? ` · <a href="${escapeHtml(source.url)}" target="_blank" rel="noopener noreferrer">Publisher copy</a>` : ''}
      </article>
    `).join('');
  }
})();
