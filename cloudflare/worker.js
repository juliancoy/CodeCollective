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

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const path = url.pathname;

    if (request.method === "OPTIONS" && (path.startsWith("/api/governance") || path.startsWith("/pidp") || path.startsWith("/api/jobs"))) {
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
      return proxyRequest(request, env.GOVERNANCE_API_ORIGIN);
    }

    if (path === "/api/jobs/meta") {
      return handleJobsMeta(request, env);
    }

    if (path === "/api/jobs") {
      return handleJobsPage(request, env);
    }

    if (path.startsWith("/pidp")) {
      return proxyRequest(request, env.PIDP_API_ORIGIN, { stripPrefix: "/pidp" });
    }

    const assetResponse = await env.ASSETS.fetch(request);
    if (assetResponse.status !== 404) {
      return assetResponse;
    }

    if ((path === "/p" || path.startsWith("/p/")) && isHtmlNavigation(request)) {
      return env.ASSETS.fetch(new Request(`${url.origin}/p/index.html`, request));
    }

    return assetResponse;
  },
};
