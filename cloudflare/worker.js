function trimTrailingSlash(value) {
  return (value || "").replace(/\/+$/, "");
}

function buildTargetUrl(requestUrl, targetOrigin, stripPrefix = "") {
  const url = new URL(requestUrl);
  const normalizedPath = stripPrefix && url.pathname.startsWith(stripPrefix)
    ? url.pathname.slice(stripPrefix.length) || "/"
    : url.pathname;
  return `${trimTrailingSlash(targetOrigin)}${normalizedPath}${url.search}`;
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

    if (request.method === "OPTIONS" && (path.startsWith("/api/governance") || path.startsWith("/api/org") || path.startsWith("/api/chat") || path.startsWith("/pidp") || path.startsWith("/auth/avatar/upload") || path.startsWith("/api/jobs") || path.startsWith("/api/vacants") || path.startsWith("/api/vacants_parcels"))) {
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

    if (path.startsWith("/api/org")) {
      return proxyRequest(request, env.ORG_API_ORIGIN || env.GOVERNANCE_API_ORIGIN, { stripPrefix: "/api/org" });
    }

    if (path.startsWith("/api/chat")) {
      return proxyRequest(request, env.CHAT_API_ORIGIN, { stripPrefix: "/api/chat" });
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
