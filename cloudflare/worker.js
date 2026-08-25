function trimTrailingSlash(value) {
  return (value || "").replace(/\/+$/, "");
}

function buildTargetUrl(requestUrl, targetOrigin, stripPrefix = "") {
  const url = new URL(requestUrl);
  const normalizedPath = stripPrefix && pathMatchesPrefix(url.pathname, stripPrefix)
    ? url.pathname.slice(stripPrefix.length) || "/"
    : url.pathname;
  return `${trimTrailingSlash(targetOrigin)}${normalizedPath}${url.search}`;
}

function pathMatchesPrefix(path, prefix) {
  return path === prefix || path.startsWith(`${prefix}/`);
}

async function proxyRequest(request, targetOrigin, options = {}) {
  const origin = trimTrailingSlash(targetOrigin);
  if (!origin) {
    return new Response("Upstream origin is not configured", { status: 502 });
  }

  const targetUrl = buildTargetUrl(request.url, origin, options.stripPrefix || "");
  const headers = new Headers(request.headers);
  const requestUrl = new URL(request.url);
  headers.delete("host");
  headers.set("x-forwarded-host", requestUrl.host);
  headers.set("x-forwarded-proto", requestUrl.protocol.replace(":", ""));

  const upstream = await fetch(targetUrl, {
    method: request.method,
    headers,
    body: request.body,
    redirect: "manual",
    cf: { cacheEverything: false },
  });

  return new Response(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: upstream.headers,
  });
}

function isHtmlNavigation(request) {
  if (request.method !== "GET") return false;
  const accept = request.headers.get("accept") || "";
  return accept.includes("text/html");
}

function looksLikeSpaRoute(path) {
  const lastSegment = path.split("/").filter(Boolean).pop() || "";
  return !lastSegment.includes(".");
}

function spaEntrypointRequest(url, request, pathname) {
  return new Request(`${url.origin}${pathname}`, {
    method: "GET",
    headers: request.headers,
  });
}

function applyStaticCachePolicy(path, response) {
  const headers = new Headers(response.headers);

  if (path.startsWith("/p/assets/") || path.startsWith("/r8-rowhome/assets/")) {
    headers.set("cache-control", "public, max-age=31536000, immutable");
  } else if (
    /\.(?:png|jpg|jpeg|gif|webp|avif|svg|ico|woff|woff2|ttf|otf|mp4|webm|mp3|wav)$/i.test(path)
  ) {
    headers.set("cache-control", "public, max-age=2592000");
  } else if (path.endsWith(".html") || path === "/" || path === "/p/" || path === "/p") {
    headers.set("cache-control", "public, max-age=300");
  }

  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers,
  });
}

function jsonResponse(payload, status = 200, headers = {}) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "public, max-age=60",
      "access-control-allow-origin": "*",
      ...headers,
    },
  });
}

const PUBLIC_MAP_FEEDS = {
  flock: "https://flocklocations.com/api/cameras/export?format=geojson",
  chartIncidents: "https://chartexp1.sha.maryland.gov/CHARTExportClientService/getEventMapDataJSON.do",
  chartSpeeds: "https://chartexp1.sha.maryland.gov/CHARTExportClientService/getTSSMapDataJSON.do",
};

function parseMapBbox(url, { maxArea = Infinity } = {}) {
  const values = (url.searchParams.get("bbox") || "").split(",").map(Number);
  if (values.length !== 4 || values.some((value) => !Number.isFinite(value))) return null;
  const [west, south, east, north] = values;
  if (west < -180 || east > 180 || south < -90 || north > 90 || west >= east || south >= north) return null;
  if ((east - west) * (north - south) > maxArea) return null;
  return values;
}

function pointInBbox(longitude, latitude, bbox) {
  return Number.isFinite(longitude) && Number.isFinite(latitude)
    && longitude >= bbox[0] && longitude <= bbox[2]
    && latitude >= bbox[1] && latitude <= bbox[3];
}

async function fetchPublicMapJson(url, cacheTtl) {
  const response = await fetch(url, {
    headers: { accept: "application/json", "user-agent": "CodeCollective public map/1.0" },
    cf: { cacheEverything: true, cacheTtl },
  });
  if (!response.ok) throw new Error(`Upstream returned HTTP ${response.status}`);
  return response.json();
}

function mapFeedResponse(features, source, generatedAt = new Date().toISOString()) {
  return jsonResponse({
    type: "FeatureCollection",
    metadata: { source, generated_at: generatedAt, feature_count: features.length },
    features,
  }, 200, { "cache-control": "public, max-age=60, s-maxage=300" });
}

async function handleFlockCameraMap(url) {
  const bbox = parseMapBbox(url, { maxArea: 25 });
  if (!bbox) return jsonResponse({ error: "bbox is invalid or too large; zoom in before requesting camera records" }, 400);
  const data = await fetchPublicMapJson(PUBLIC_MAP_FEEDS.flock, 900);
  const features = (data.features || []).filter((feature) => {
    const [longitude, latitude] = feature.geometry?.coordinates || [];
    return feature.geometry?.type === "Point" && pointInBbox(Number(longitude), Number(latitude), bbox);
  }).map((feature) => ({
    type: "Feature",
    geometry: feature.geometry,
    properties: {
      id: feature.properties?.id,
      address: feature.properties?.address,
      city: feature.properties?.city,
      state: feature.properties?.state,
      camera_type: feature.properties?.camera_type,
      mounted_on: feature.properties?.mounted_on,
      verified: Boolean(feature.properties?.verified),
      confirm_count: Number(feature.properties?.confirm_count) || 0,
      reported_at: feature.properties?.reported_at,
      source_url: feature.properties?.source_url,
    },
  }));
  return mapFeedResponse(features, data.source || "https://flocklocations.com", data.generated);
}

function overpassFeature(element) {
  const latitude = Number(element.lat ?? element.center?.lat);
  const longitude = Number(element.lon ?? element.center?.lon);
  if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) return null;
  const tags = element.tags || {};
  return {
    type: "Feature",
    geometry: { type: "Point", coordinates: [longitude, latitude] },
    properties: {
      osm_id: `${element.type}/${element.id}`,
      operator: tags.operator,
      brand: tags.brand,
      manufacturer: tags.manufacturer,
      direction: tags.direction,
      camera_mount: tags.camera_mount || tags.mounting,
      surveillance_type: tags["surveillance:type"],
      source_url: `https://www.openstreetmap.org/${element.type}/${element.id}`,
    },
  };
}

async function handleAlprMap(url) {
  const bbox = parseMapBbox(url, { maxArea: 4 });
  if (!bbox) return jsonResponse({ error: "bbox is invalid or too large; zoom in before requesting ALPR records" }, 400);
  const [west, south, east, north] = bbox;
  const query = `[out:json][timeout:20];node["man_made"="surveillance"]["surveillance:type"="ALPR"](${south},${west},${north},${east});out body qt;`;
  const response = await fetch("https://overpass-api.de/api/interpreter", {
    method: "POST",
    headers: { "content-type": "application/x-www-form-urlencoded", "user-agent": "CodeCollective public map/1.0" },
    body: new URLSearchParams({ data: query }),
  });
  if (!response.ok) throw new Error(`Overpass returned HTTP ${response.status}`);
  const data = await response.json();
  return mapFeedResponse((data.elements || []).map(overpassFeature).filter(Boolean), "OpenStreetMap Overpass API", data.osm3s?.timestamp_osm_base);
}

function chartPoint(record, properties) {
  const latitude = Number(record.lat);
  const longitude = Number(record.lon);
  if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) return null;
  return { type: "Feature", geometry: { type: "Point", coordinates: [longitude, latitude] }, properties };
}

async function handleChartMap(url, kind) {
  const bbox = parseMapBbox(url);
  if (!bbox) return jsonResponse({ error: "bbox must be west,south,east,north" }, 400);
  const feedUrl = kind === "speeds" ? PUBLIC_MAP_FEEDS.chartSpeeds : PUBLIC_MAP_FEEDS.chartIncidents;
  const data = await fetchPublicMapJson(feedUrl, kind === "speeds" ? 60 : 120);
  const policeOnly = kind === "incidents" && url.searchParams.get("kind") === "police";
  const features = (data.data || []).filter((record) => pointInBbox(Number(record.lon), Number(record.lat), bbox)).filter((record) => (
    !policeOnly || String(record.incidentType).toLowerCase() === "police activity"
  )).map((record) => {
    if (kind === "speeds") {
      const zones = (record.zones || []).filter((zone) => Number(zone.speed) >= 0 && Number(zone.speed) <= 120);
      const speeds = zones.map((zone) => Number(zone.speed));
      return chartPoint(record, {
        id: record.id,
        name: record.name,
        description: record.description,
        operating_status: record.opStatus,
        owner: record.owningOrg,
        speed_mph: speeds.length ? Math.round(speeds.reduce((sum, speed) => sum + speed, 0) / speeds.length) : null,
        directions: zones.map((zone) => zone.direction).filter(Boolean).join(", "),
        last_updated: record.lastUpdateTime,
      });
    }
    return chartPoint(record, {
      id: record.id,
      name: record.name,
      description: record.description,
      incident_type: record.incidentType,
      county: record.county,
      direction: record.direction,
      lanes_status: record.lanesStatus,
      closed: Boolean(record.closed),
      traffic_alert: Boolean(record.trafficAlert),
      traffic_alert_text: record.trafficAlertTextMsg,
      started_at: record.startDateTime,
      last_updated: record.lastCachedDataUpdateTime,
    });
  }).filter(Boolean);
  return mapFeedResponse(features, "Maryland CHART", data.lastCachedDataUpdateTime);
}

async function handlePublicMapData(request, url) {
  if (request.method !== "GET" && request.method !== "HEAD") return jsonResponse({ error: "Method not allowed" }, 405);
  try {
    if (url.pathname === "/api/map-data/flock-cameras") return await handleFlockCameraMap(url);
    if (url.pathname === "/api/map-data/alpr") return await handleAlprMap(url);
    if (url.pathname === "/api/map-data/chart/incidents") return await handleChartMap(url, "incidents");
    if (url.pathname === "/api/map-data/chart/speeds") return await handleChartMap(url, "speeds");
    return jsonResponse({ error: "Map feed not found" }, 404);
  } catch (error) {
    return jsonResponse({ error: `Public map feed unavailable: ${error.message}` }, 502);
  }
}

function getRangeContentLength(range) {
  if (!range || typeof range.offset !== "number" || typeof range.length !== "number") {
    return null;
  }

  return String(range.length);
}

function getContentRangeHeader(range, size) {
  if (!range || typeof range.offset !== "number" || typeof range.length !== "number") {
    return null;
  }

  const end = range.offset + range.length - 1;
  return `bytes ${range.offset}-${end}/${size}`;
}

async function handleAudioRequest(request, env, path) {
  if (!env.MEDIA_BUCKET || !pathMatchesPrefix(path, "/audio")) {
    return null;
  }

  const key = path.replace(/^\/+/, "");
  const object =
    request.method === "HEAD"
      ? await env.MEDIA_BUCKET.head(key)
      : await env.MEDIA_BUCKET.get(key, { range: request.headers });

  if (!object) {
    return null;
  }

  const headers = new Headers();
  object.writeHttpMetadata(headers);
  headers.set("etag", object.httpEtag);
  headers.set("accept-ranges", "bytes");
  headers.set("cache-control", headers.get("cache-control") || "public, max-age=2592000");

  const contentLength = getRangeContentLength(object.range) || String(object.size);
  headers.set("content-length", contentLength);

  const contentRange = getContentRangeHeader(object.range, object.size);
  if (contentRange) {
    headers.set("content-range", contentRange);
  }

  return new Response(request.method === "HEAD" ? null : object.body, {
    status: object.range ? 206 : 200,
    headers,
  });
}

async function readLatestJobsPointer(env) {
  if (!env.JOBS_BUCKET) return null;
  const object = await env.JOBS_BUCKET.get("jobs/latest.json");
  if (!object) return null;
  return object.json();
}

async function readJobsManifest(env, version = "") {
  if (!env.JOBS_BUCKET) return null;
  let manifestKey = "";
  let resolvedVersion = version;

  if (resolvedVersion) {
    manifestKey = `jobs/${resolvedVersion}/manifest.json`;
  } else {
    const latest = await readLatestJobsPointer(env);
    if (!latest || !latest.manifest_key) return null;
    manifestKey = String(latest.manifest_key);
    resolvedVersion = String(latest.version || "");
  }

  const object = await env.JOBS_BUCKET.get(manifestKey);
  if (!object) return null;
  const manifest = await object.json();
  return { manifest, version: resolvedVersion, manifestKey };
}

function normalizeStateParam(raw) {
  const value = String(raw || "ALL").trim().toUpperCase();
  if (!value) return "ALL";
  return value;
}

async function handleJobsMeta(request, env) {
  const url = new URL(request.url);
  const version = url.searchParams.get("version") || "";
  const loaded = await readJobsManifest(env, version);
  if (!loaded) {
    return jsonResponse({ error: "Jobs manifest not found" }, 404);
  }

  return jsonResponse({
    version: loaded.version || loaded.manifest.version || "",
    manifest_key: loaded.manifestKey,
    ...loaded.manifest,
  });
}

async function handleJobsPage(request, env) {
  const url = new URL(request.url);
  const version = url.searchParams.get("version") || "";
  const state = normalizeStateParam(url.searchParams.get("state"));
  const page = Number.parseInt(url.searchParams.get("page") || "1", 10);

  if (!Number.isInteger(page) || page < 1) {
    return jsonResponse({ error: "Invalid page query parameter" }, 400);
  }

  const loaded = await readJobsManifest(env, version);
  if (!loaded) {
    return jsonResponse({ error: "Jobs manifest not found" }, 404);
  }

  const manifest = loaded.manifest;
  const states = manifest.states || {};
  const stateEntry = states[state] || states.ALL;
  if (!stateEntry) {
    return jsonResponse({ error: `State not found: ${state}` }, 404);
  }

  const shard = (stateEntry.shards || []).find((item) => Number(item.page) === page);
  if (!shard || !shard.key) {
    return jsonResponse({ error: `Page not found for state ${state}: ${page}` }, 404);
  }

  const object = await env.JOBS_BUCKET.get(String(shard.key));
  if (!object) {
    return jsonResponse({ error: "Shard object not found" }, 404);
  }

  const headers = new Headers();
  object.writeHttpMetadata(headers);
  headers.set("etag", object.httpEtag);
  headers.set("cache-control", "public, max-age=300");
  headers.set("access-control-allow-origin", "*");

  return new Response(object.body, { status: 200, headers });
}

async function readLatestVacantsPointer(env) {
  if (!env.VACANTS_BUCKET) return null;
  const object = await env.VACANTS_BUCKET.get("vacants/latest.json");
  if (!object) return null;
  return object.json();
}

async function readVacantsManifest(env, version = "") {
  if (!env.VACANTS_BUCKET) return null;
  let manifestKey = "";
  let resolvedVersion = version;

  if (resolvedVersion) {
    manifestKey = `vacants/${resolvedVersion}/manifest.json`;
  } else {
    const latest = await readLatestVacantsPointer(env);
    if (!latest || !latest.manifest_key) return null;
    manifestKey = String(latest.manifest_key);
    resolvedVersion = String(latest.version || "");
  }

  const object = await env.VACANTS_BUCKET.get(manifestKey);
  if (!object) return null;
  const manifest = await object.json();
  return { manifest, version: resolvedVersion, manifestKey };
}

function normalizeVacantsGroup(raw) {
  const value = String(raw || "ALL").trim().toUpperCase();
  return value || "ALL";
}

async function handleVacantsMeta(request, env) {
  const url = new URL(request.url);
  const version = url.searchParams.get("version") || "";
  const loaded = await readVacantsManifest(env, version);
  if (!loaded) {
    return jsonResponse({ error: "Vacants manifest not found" }, 404);
  }

  return jsonResponse({
    version: loaded.version || loaded.manifest.version || "",
    manifest_key: loaded.manifestKey,
    ...loaded.manifest,
  });
}

async function handleVacantsPage(request, env) {
  const url = new URL(request.url);
  const version = url.searchParams.get("version") || "";
  const group = normalizeVacantsGroup(url.searchParams.get("group"));
  const page = Number.parseInt(url.searchParams.get("page") || "1", 10);

  if (!Number.isInteger(page) || page < 1) {
    return jsonResponse({ error: "Invalid page query parameter" }, 400);
  }

  const loaded = await readVacantsManifest(env, version);
  if (!loaded) {
    return jsonResponse({ error: "Vacants manifest not found" }, 404);
  }

  const groups = loaded.manifest.groups || {};
  const groupEntry = groups[group] || groups.ALL;
  if (!groupEntry) {
    return jsonResponse({ error: `Group not found: ${group}` }, 404);
  }

  const shard = (groupEntry.shards || []).find((item) => Number(item.page) === page);
  if (!shard || !shard.key) {
    return jsonResponse({ error: `Page not found for group ${group}: ${page}` }, 404);
  }

  const object = await env.VACANTS_BUCKET.get(String(shard.key));
  if (!object) {
    return jsonResponse({ error: "Shard object not found" }, 404);
  }

  const headers = new Headers();
  object.writeHttpMetadata(headers);
  headers.set("etag", object.httpEtag);
  headers.set("cache-control", "public, max-age=300");
  headers.set("access-control-allow-origin", "*");

  return new Response(object.body, { status: 200, headers });
}

async function readLatestVacantsParcelsPointer(env) {
  if (!env.VACANTS_BUCKET) return null;
  const object = await env.VACANTS_BUCKET.get("vacants_parcels/latest.json");
  if (!object) return null;
  return object.json();
}

async function readVacantsParcelsManifest(env, version = "") {
  if (!env.VACANTS_BUCKET) return null;
  let manifestKey = "";
  let resolvedVersion = version;

  if (resolvedVersion) {
    manifestKey = `vacants_parcels/${resolvedVersion}/manifest.json`;
  } else {
    const latest = await readLatestVacantsParcelsPointer(env);
    if (!latest || !latest.manifest_key) return null;
    manifestKey = String(latest.manifest_key);
    resolvedVersion = String(latest.version || "");
  }

  const object = await env.VACANTS_BUCKET.get(manifestKey);
  if (!object) return null;
  const manifest = await object.json();
  return { manifest, version: resolvedVersion, manifestKey };
}

function normalizeVacantsParcelsGroup(raw) {
  const value = String(raw || "ALL").trim().toUpperCase();
  return value || "ALL";
}

async function handleVacantsParcelsMeta(request, env) {
  const url = new URL(request.url);
  const version = url.searchParams.get("version") || "";
  const loaded = await readVacantsParcelsManifest(env, version);
  if (!loaded) {
    return jsonResponse({ error: "Vacants parcels manifest not found" }, 404);
  }

  return jsonResponse({
    version: loaded.version || loaded.manifest.version || "",
    manifest_key: loaded.manifestKey,
    ...loaded.manifest,
  });
}

async function handleVacantsParcelsPage(request, env) {
  const url = new URL(request.url);
  const version = url.searchParams.get("version") || "";
  const group = normalizeVacantsParcelsGroup(url.searchParams.get("group"));
  const page = Number.parseInt(url.searchParams.get("page") || "1", 10);

  if (!Number.isInteger(page) || page < 1) {
    return jsonResponse({ error: "Invalid page query parameter" }, 400);
  }

  const loaded = await readVacantsParcelsManifest(env, version);
  if (!loaded) {
    return jsonResponse({ error: "Vacants parcels manifest not found" }, 404);
  }

  const groups = loaded.manifest.groups || {};
  const groupEntry = groups[group] || groups.ALL;
  if (!groupEntry) {
    return jsonResponse({ error: `Group not found: ${group}` }, 404);
  }

  const shard = (groupEntry.shards || []).find((item) => Number(item.page) === page);
  if (!shard || !shard.key) {
    return jsonResponse({ error: `Page not found for group ${group}: ${page}` }, 404);
  }

  const object = await env.VACANTS_BUCKET.get(String(shard.key));
  if (!object) {
    return jsonResponse({ error: "Shard object not found" }, 404);
  }

  const headers = new Headers();
  object.writeHttpMetadata(headers);
  headers.set("etag", object.httpEtag);
  headers.set("cache-control", "public, max-age=300");
  headers.set("access-control-allow-origin", "*");

  return new Response(object.body, { status: 200, headers });
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const path = url.pathname;

    if (path === "/favicon.ico") {
      url.pathname = "/images/favicons/favicon.png";
      return Response.redirect(url.toString(), 308);
    }

    if (path === "/R8-rowhome" || path.startsWith("/R8-rowhome/")) {
      url.pathname = `/r8-rowhome${path.slice("/R8-rowhome".length)}`;
      return Response.redirect(url.toString(), 308);
    }

    if (request.method === "OPTIONS" && (path.startsWith("/api/governance") || pathMatchesPrefix(path, "/api/org") || pathMatchesPrefix(path, "/api/chat") || path.startsWith("/pidp") || path.startsWith("/auth/avatar/upload") || path.startsWith("/api/jobs") || path.startsWith("/api/vacants") || path.startsWith("/api/vacants_parcels") || path.startsWith("/api/map-data"))) {
      return new Response(null, {
        status: 204,
        headers: {
          "access-control-allow-origin": "*",
          "access-control-allow-methods": "GET,HEAD,POST,PUT,PATCH,DELETE,OPTIONS",
          "access-control-allow-headers": "authorization,content-type,x-requested-with",
        },
      });
    }

    if (path.startsWith("/api/governance")) {
      return proxyRequest(request, env.ORG_API_ORIGIN || env.GOVERNANCE_API_ORIGIN);
    }

    if (pathMatchesPrefix(path, "/api/org")) {
      return proxyRequest(request, env.ORG_API_ORIGIN || env.GOVERNANCE_API_ORIGIN, { stripPrefix: "/api/org" });
    }

    if (pathMatchesPrefix(path, "/api/chat")) {
      return proxyRequest(request, env.CHAT_API_ORIGIN, { stripPrefix: "/api/chat" });
    }

    if (pathMatchesPrefix(path, "/api/map-data")) {
      return handlePublicMapData(request, url);
    }

    if (path === "/api/jobs/meta") {
      return handleJobsMeta(request, env);
    }

    if (path === "/api/jobs") {
      return handleJobsPage(request, env);
    }

    if (path === "/api/vacants/meta") {
      return handleVacantsMeta(request, env);
    }

    if (path === "/api/vacants") {
      return handleVacantsPage(request, env);
    }

    if (path === "/api/vacants_parcels/meta") {
      return handleVacantsParcelsMeta(request, env);
    }

    if (path === "/api/vacants_parcels") {
      return handleVacantsParcelsPage(request, env);
    }

    if (path.startsWith("/pidp")) {
      return proxyRequest(request, env.PIDP_PROXY_ORIGIN || env.PIDP_API_ORIGIN, { stripPrefix: "/pidp" });
    }

    if (path.startsWith("/auth/avatar/upload")) {
      return proxyRequest(request, env.PIDP_PROXY_ORIGIN || env.PIDP_API_ORIGIN);
    }

    if (path === "/auth/callback") {
      url.pathname = "/p/auth/callback";
      return Response.redirect(url.toString(), 308);
    }

    if (pathMatchesPrefix(path, "/audio")) {
      const audioResponse = await handleAudioRequest(request, env, path);
      if (audioResponse) {
        return audioResponse;
      }
    }

    const assetResponse = await env.ASSETS.fetch(request);
    if (assetResponse.status !== 404) {
      return applyStaticCachePolicy(path, assetResponse);
    }

    if ((path === "/p" || path.startsWith("/p/")) && (isHtmlNavigation(request) || looksLikeSpaRoute(path))) {
      // Request the directory entrypoint directly to avoid index.html -> /p/ redirects
      // that can interfere with hash-token deep links after auth callbacks.
      const spaResponse = await env.ASSETS.fetch(spaEntrypointRequest(url, request, "/p/"));
      return applyStaticCachePolicy("/p/index.html", spaResponse);
    }

    if ((path === "/r8-rowhome" || path.startsWith("/r8-rowhome/")) && (isHtmlNavigation(request) || looksLikeSpaRoute(path))) {
      const spaResponse = await env.ASSETS.fetch(spaEntrypointRequest(url, request, "/r8-rowhome/"));
      return applyStaticCachePolicy("/r8-rowhome/index.html", spaResponse);
    }

    return assetResponse;
  },
};
