(() => {
  const DATA_URLS = {
    datacenters: '/datacenters/data/datacenters.json',
    plants: '/datacenters/data/power-plants.json',
    rates: '/datacenters/data/residential-electricity-rates.json',
    sources: '/datacenters/data/sources.json',
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
    const map = L.map('datacenter-map', { zoomControl: true }).setView([39.05, -76.75], 8);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);

    const layers = {
      data_center: L.layerGroup().addTo(map),
      power_plant: L.layerGroup().addTo(map),
    };
    const markerById = new Map();
    const allRecords = [...data.datacenters, ...data.plants];

    allRecords.forEach((record) => {
      if (!Number.isFinite(record.latitude) || !Number.isFinite(record.longitude)) return;
      const isCenter = record.record_type === 'data_center';
      const marker = L.marker([record.latitude, record.longitude], {
        icon: L.divIcon({
          className: '',
          html: `<span class="dc-map-icon dc-map-icon--${isCenter ? 'center' : 'plant'}"></span>`,
          iconSize: [22, 22],
          iconAnchor: [11, 11],
        }),
        title: record.name,
      });
      marker.bindTooltip(`${escapeHtml(record.name)}${isCenter ? '' : ` · ${number(record.nameplate_capacity_mw, 1)} MW`}`);
      marker.on('click', () => renderDetail(record, sourceById));
      marker.addTo(layers[record.record_type]);
      markerById.set(record.id, marker);
    });

    document.getElementById('show-datacenters').addEventListener('change', (event) => {
      toggleLayer(map, layers.data_center, event.target.checked);
      renderResults(allRecords, markerById, map);
    });
    document.getElementById('show-plants').addEventListener('change', (event) => {
      toggleLayer(map, layers.power_plant, event.target.checked);
      renderResults(allRecords, markerById, map);
    });
    document.getElementById('map-search').addEventListener('input', () => renderResults(allRecords, markerById, map));
    document.getElementById('status-filter').addEventListener('change', () => renderResults(allRecords, markerById, map));
    document.getElementById('sentiment-filter').addEventListener('change', () => renderResults(allRecords, markerById, map));

    document.getElementById('datacenter-count').textContent = number(data.datacenters.length);
    document.getElementById('plant-count').textContent = number(data.plants.length);
    const generation = data.plants.reduce((sum, plant) => sum + (plant.net_generation_mwh || 0), 0);
    document.getElementById('generation-total').textContent = `${number(generation / 1_000_000, 2)} million MWh`;
    const rate = data.rates[0];
    document.getElementById('residential-rate').textContent = rate ? `${rate.average_price_cents_per_kwh}¢/kWh` : 'Unknown';

    renderResults(allRecords, markerById, map);
    renderSources(data.sources);
  }

  function toggleLayer(map, layer, enabled) {
    if (enabled) layer.addTo(map);
    else layer.removeFrom(map);
  }

  function visibleType(record) {
    return record.record_type === 'data_center'
      ? document.getElementById('show-datacenters').checked
      : document.getElementById('show-plants').checked;
  }

  function renderResults(records, markerById, map) {
    const query = document.getElementById('map-search').value.trim().toLowerCase();
    const statusFilter = document.getElementById('status-filter').value;
    const sentimentFilter = document.getElementById('sentiment-filter').value;
    const matches = records.filter((record) => {
      if (!visibleType(record)) return false;
      if (record.record_type === 'data_center' && statusFilter !== 'all') {
        const status = record.status.toLowerCase();
        const statusMatches = statusFilter === 'operating'
          ? status === 'operating'
          : statusFilter === 'development'
            ? status.includes('permit') || status.includes('development') || status.includes('construction')
            : status.includes('proposed') || status.includes('concept') || status.includes('planned');
        if (!statusMatches) return false;
      }
      if (record.record_type === 'data_center' && sentimentFilter !== 'all') {
        const score = record.public_sentiment_score;
        if (sentimentFilter === 'opposed' && !(score < 0)) return false;
        if (sentimentFilter === 'mixed' && score !== 0) return false;
        if (sentimentFilter === 'unknown' && score !== null) return false;
      }
      const haystack = [record.name, record.operator, record.county, record.city, record.primary_technology]
        .filter(Boolean).join(' ').toLowerCase();
      return !query || haystack.includes(query);
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
      button.innerHTML = `<strong>${escapeHtml(record.name)}</strong><small>${escapeHtml(record.record_type === 'data_center' ? record.status : `${record.primary_technology || 'Power plant'} · ${number(record.nameplate_capacity_mw || 0, 1)} MW`)}</small>`;
      button.addEventListener('click', () => {
        const marker = markerById.get(record.id);
        if (marker) {
          map.setView(marker.getLatLng(), Math.max(map.getZoom(), 11));
          marker.fire('click');
          marker.openTooltip();
        }
      });
      list.appendChild(button);
    });
  }

  function renderDetail(record, sourceById) {
    const detail = document.getElementById('record-detail');
    if (record.record_type === 'data_center') {
      detail.innerHTML = `
        <h2>${escapeHtml(record.name)}</h2>
        <p class="dc-type">Data center · ${escapeHtml(record.status)}</p>
        <dl class="dc-facts">
          <dt>Operator</dt><dd>${known(record.operator)}</dd>
          <dt>Address</dt><dd>${known([record.street_address, record.city, record.state, record.postal_code].filter(Boolean).join(', '))}</dd>
          <dt>Status</dt><dd>${known(record.status)}</dd>
          <dt>Plan</dt><dd>${known(record.plan_detail)}</dd>
          <dt>Permits</dt><dd>${known(record.permit_detail)}</dd>
          <dt>Financing</dt><dd>${known(record.financing_detail)}</dd>
          <dt>Public opposition</dt><dd>${known(record.public_opposition_status)}</dd>
          <dt>Sentiment rating</dt><dd>${renderSentiment(record)}</dd>
          <dt>Sentiment basis</dt><dd>${known(record.sentiment_basis)}</dd>
          <dt>Buildings</dt><dd>${known(record.building_count)}</dd>
          <dt>Power capacity</dt><dd>${record.reported_power_capacity_mw == null ? known(null) : `${number(record.reported_power_capacity_mw, 2)} MW · ${escapeHtml(record.reported_power_capacity_basis)}`}</dd>
          <dt>Grid demand</dt><dd>${known(record.reported_grid_demand_mw, ' MW')}</dd>
          <dt>Annual energy</dt><dd>${known(record.reported_annual_energy_mwh, ' MWh')}</dd>
          <dt>PUE</dt><dd>${known(record.reported_pue)}</dd>
          <dt>Gas plant</dt><dd>${known(record.on_site_natural_gas_power_plant)}</dd>
          <dt>Backup</dt><dd>${known(record.backup_generator_detail)}</dd>
          <dt>Backup total</dt><dd>${known(record.backup_generator_capacity_mw, ' MW')}</dd>
          <dt>UPS</dt><dd>${known(record.ups_technology)}</dd>
          <dt>UPS power</dt><dd>${known(record.ups_capacity_mw, ' MW')}</dd>
          <dt>UPS energy</dt><dd>${known(record.ups_energy_mwh, ' MWh')}</dd>
          <dt>Cooling/water</dt><dd>${known(record.cooling_water_detail)}</dd>
          <dt>Personnel</dt><dd>${known(record.employees_current)}</dd>
          <dt>Committed jobs</dt><dd>${known(record.employees_committed)}</dd>
          <dt>Investment</dt><dd>${record.capital_investment_usd == null ? known(null) : `$${number(record.capital_investment_usd)}`}</dd>
          <dt>Public support</dt><dd>${known(record.public_funding_detail)}</dd>
        </dl>
        <p>${escapeHtml(record.notes)}</p>
        ${renderRecordSources(record.source_ids, sourceById)}
      `;
    } else {
      detail.innerHTML = `
        <h2>${escapeHtml(record.name)}</h2>
        <p class="dc-type">Power plant · EIA plant ${record.eia_plant_code}</p>
        <dl class="dc-facts">
          <dt>Operator</dt><dd>${known(record.operator)}</dd>
          <dt>County</dt><dd>${known(record.county)}</dd>
          <dt>Technology</dt><dd>${known(record.primary_technology)}</dd>
          <dt>Fuel codes</dt><dd>${known(record.energy_source_codes.join(', '))}</dd>
          <dt>Capacity</dt><dd>${known(record.nameplate_capacity_mw, ' MW')}</dd>
          <dt>Generators</dt><dd>${known(record.generator_count)}</dd>
          <dt>${record.generation_year} generation</dt><dd>${record.net_generation_mwh == null ? known(null) : `${number(record.net_generation_mwh, 1)} MWh`}</dd>
        </dl>
        ${renderRecordSources([record.capacity_source_id, record.generation_source_id], sourceById)}
      `;
    }
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
