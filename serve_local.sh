#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SITE_DIR="${SITE_DIR:-$ROOT_DIR/.cloudflare/site}"
SERVER_FILE="${SERVER_FILE:-$ROOT_DIR/.cloudflare/local-node-server.mjs}"
CERT_DIR="${CERT_DIR:-$ROOT_DIR/.cloudflare/local-certs}"
NODE_IMAGE="${NODE_IMAGE:-node:22-alpine}"
CONTAINER_NAME="${CONTAINER_NAME:-codecollective-local-site}"
NETWORK_NAME="${NETWORK_NAME:-codecollective-local}"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8080}"
SKIP_BUILD="${SKIP_BUILD:-0}"
MODE="${MODE:-dev}"
DETACH=0
CLEAN=0

usage() {
  cat <<'EOF'
Usage: ./serve_local.sh [options]

Serve Code Collective locally with Dockerized Node.

Default mode is fast iteration:
  - / is served from the repo working tree
  - /p/ is proxied to the portal Vite dev server
  - /r8-rowhome/ is proxied to the r8-rowhome Vite dev server

Options:
  --port <port>       Host port to bind (default: 8080)
  --host <host>       Host address to bind (default: 127.0.0.1; use 0.0.0.0 for LAN)
  --build             Build and serve the production-style .cloudflare/site bundle
  --skip-build        With --build, reuse the existing .cloudflare/site bundle
  --detach            Run the Docker container in the background
  --clean             Stop local containers and exit
  -h, --help          Show this help

Environment:
  NODE_IMAGE                 Docker Node image (default: node:22-alpine)
  CONTAINER_NAME             Docker container name (default: codecollective-local-site)
  NETWORK_NAME               Docker network name (default: codecollective-local)
  CERT_DIR                   Local self-signed cert directory (default: .cloudflare/local-certs)
  VITE_PIDP_BASE_URL         Portal PIdP base (default: https://id.codecollective.us)
  GOVERNANCE_API_ORIGIN      Optional proxy origin for /api/governance
  ORG_API_ORIGIN             Optional proxy origin for /api/org, with /api/org stripped
  PIDP_API_ORIGIN            Optional proxy origin for /pidp, with /pidp stripped
  PIDP_PROXY_ORIGIN          Optional proxy origin for /pidp; overrides PIDP_API_ORIGIN

Examples:
  ./serve_local.sh
  PORT=8787 ./serve_local.sh --host 0.0.0.0
  ./serve_local.sh --build
  ./serve_local.sh --clean
EOF
}

while (($#)); do
  case "$1" in
    --port)
      PORT="$2"
      shift 2
      ;;
    --host)
      HOST="$2"
      shift 2
      ;;
    --build)
      MODE=build
      shift
      ;;
    --skip-build)
      SKIP_BUILD=1
      shift
      ;;
    --detach)
      DETACH=1
      shift
      ;;
    --clean)
      CLEAN=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "[serve-local] unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if ! command -v docker >/dev/null 2>&1; then
  echo "[serve-local] docker not found; install Docker first" >&2
  exit 1
fi

if [[ "$CLEAN" -eq 1 ]]; then
  docker rm -f "$CONTAINER_NAME" "$CONTAINER_NAME-portal" "$CONTAINER_NAME-r8-rowhome" >/dev/null 2>&1 || true
  echo "[serve-local] stopped local containers"
  exit 0
fi

if [[ "$MODE" != "dev" && "$MODE" != "build" ]]; then
  echo "[serve-local] invalid MODE: $MODE (expected dev or build)" >&2
  exit 1
fi

if [[ "$MODE" == "build" && "$SKIP_BUILD" -eq 0 ]]; then
  echo "[serve-local] building full static bundle"
  "$ROOT_DIR/scripts/build_cloudflare_site.sh"
elif [[ "$MODE" == "build" ]]; then
  echo "[serve-local] skipping build; using $SITE_DIR"
fi

if [[ "$MODE" == "build" && ! -f "$SITE_DIR/index.html" ]]; then
  echo "[serve-local] missing site entrypoint: $SITE_DIR/index.html" >&2
  exit 1
fi

if [[ "$MODE" == "build" && ! -f "$SITE_DIR/p/index.html" ]]; then
  echo "[serve-local] missing portal entrypoint: $SITE_DIR/p/index.html" >&2
  echo "[serve-local] rerun without --skip-build to build the portal" >&2
  exit 1
fi

mkdir -p "$CERT_DIR"
CERT_FILE="$CERT_DIR/localhost.crt"
KEY_FILE="$CERT_DIR/localhost.key"

if [[ ! -f "$CERT_FILE" || ! -f "$KEY_FILE" ]]; then
  if ! command -v openssl >/dev/null 2>&1; then
    echo "[serve-local] openssl not found; install it or set CERT_DIR with localhost.crt and localhost.key" >&2
    exit 1
  fi

  echo "[serve-local] generating self-signed HTTPS certificate"
  openssl req -x509 -newkey rsa:2048 -nodes -days 825 \
    -keyout "$KEY_FILE" \
    -out "$CERT_FILE" \
    -subj "/CN=localhost" \
    -addext "subjectAltName=DNS:localhost,IP:127.0.0.1,IP:::1" >/dev/null 2>&1
fi

mkdir -p "$(dirname "$SERVER_FILE")"

cat > "$SERVER_FILE" <<'NODE'
import { createReadStream } from 'node:fs'
import { readFileSync } from 'node:fs'
import { stat } from 'node:fs/promises'
import http from 'node:http'
import https from 'node:https'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const siteRoot = process.env.SITE_ROOT || '/site'
const port = Number.parseInt(process.env.CONTAINER_PORT || '8080', 10)
const certFile = process.env.TLS_CERT_FILE || '/certs/localhost.crt'
const keyFile = process.env.TLS_KEY_FILE || '/certs/localhost.key'

const mimeTypes = new Map([
  ['.html', 'text/html; charset=utf-8'],
  ['.css', 'text/css; charset=utf-8'],
  ['.js', 'text/javascript; charset=utf-8'],
  ['.mjs', 'text/javascript; charset=utf-8'],
  ['.json', 'application/json; charset=utf-8'],
  ['.svg', 'image/svg+xml'],
  ['.png', 'image/png'],
  ['.jpg', 'image/jpeg'],
  ['.jpeg', 'image/jpeg'],
  ['.gif', 'image/gif'],
  ['.webp', 'image/webp'],
  ['.avif', 'image/avif'],
  ['.ico', 'image/x-icon'],
  ['.woff', 'font/woff'],
  ['.woff2', 'font/woff2'],
  ['.ttf', 'font/ttf'],
  ['.otf', 'font/otf'],
  ['.mp4', 'video/mp4'],
  ['.webm', 'video/webm'],
  ['.mp3', 'audio/mpeg'],
  ['.wav', 'audio/wav'],
  ['.ics', 'text/calendar; charset=utf-8'],
  ['.txt', 'text/plain; charset=utf-8'],
])

const proxies = [
  {
    prefix: '/p',
    origin: process.env.PORTAL_ORIGIN || '',
    stripPrefix: '',
  },
  {
    prefix: '/r8-rowhome',
    origin: process.env.R8_ROWHOME_ORIGIN || '',
    stripPrefix: '',
  },
  {
    prefix: '/pidp',
    origin: process.env.PIDP_PROXY_ORIGIN || process.env.PIDP_API_ORIGIN || '',
    stripPrefix: '/pidp',
  },
  {
    prefix: '/api/org',
    origin: process.env.ORG_API_ORIGIN || '',
    stripPrefix: '/api/org',
  },
  {
    prefix: '/api/governance',
    origin: process.env.GOVERNANCE_API_ORIGIN || '',
    stripPrefix: '',
  },
]

function send(res, status, body, headers = {}) {
  res.writeHead(status, {
    'cache-control': 'no-store',
    ...headers,
  })
  res.end(body)
}

function isHtmlNavigation(req) {
  if (req.method !== 'GET' && req.method !== 'HEAD') return false
  return String(req.headers.accept || '').includes('text/html')
}

function looksLikeSpaRoute(urlPath) {
  return !path.posix.basename(urlPath).includes('.')
}

function cleanPathname(rawPathname) {
  let pathname
  try {
    pathname = decodeURIComponent(rawPathname)
  } catch {
    pathname = rawPathname
  }
  const normalized = path.posix.normalize(`/${pathname}`)
  return normalized === '/.' ? '/' : normalized
}

function filePathForUrlPath(urlPath) {
  const relative = urlPath.replace(/^\/+/, '')
  const resolved = path.resolve(siteRoot, relative)
  const root = path.resolve(siteRoot)
  if (resolved !== root && !resolved.startsWith(`${root}${path.sep}`)) {
    return null
  }
  return resolved
}

async function existingFile(urlPath) {
  const direct = filePathForUrlPath(urlPath)
  if (!direct) return null

  try {
    const info = await stat(direct)
    if (info.isFile()) return direct
    if (info.isDirectory()) {
      const indexPath = path.join(direct, 'index.html')
      const indexInfo = await stat(indexPath)
      if (indexInfo.isFile()) return indexPath
    }
  } catch {
    return null
  }

  return null
}

async function serveFile(req, res, filePath, cachePath) {
  const ext = path.extname(filePath).toLowerCase()
  const headers = {
    'content-type': mimeTypes.get(ext) || 'application/octet-stream',
  }

  if (cachePath.startsWith('/p/assets/') || cachePath.startsWith('/r8-rowhome/assets/')) {
    headers['cache-control'] = 'public, max-age=31536000, immutable'
  } else {
    headers['cache-control'] = 'no-store'
  }

  res.writeHead(200, headers)
  if (req.method === 'HEAD') {
    res.end()
    return
  }
  createReadStream(filePath).pipe(res)
}

async function proxyRequest(req, res, requestUrl, proxy) {
  if (!proxy.origin) {
    send(res, 502, `Proxy origin is not configured for ${proxy.prefix}\n`, {
      'content-type': 'text/plain; charset=utf-8',
    })
    return
  }

  const targetPath = proxy.stripPrefix && requestUrl.pathname.startsWith(proxy.stripPrefix)
    ? requestUrl.pathname.slice(proxy.stripPrefix.length) || '/'
    : requestUrl.pathname
  const target = new URL(targetPath + requestUrl.search, proxy.origin.replace(/\/+$/, ''))

  await new Promise((resolve) => {
    const headers = { ...req.headers }
    delete headers.host
    headers['x-forwarded-host'] = req.headers.host || ''
    headers['x-forwarded-proto'] = 'http'

    const transport = target.protocol === 'https:' ? https : http
    const upstreamReq = transport.request(
      target,
      {
        method: req.method,
        headers,
        rejectUnauthorized: false,
      },
      (upstreamRes) => {
        res.writeHead(upstreamRes.statusCode || 502, upstreamRes.headers)
        if (req.method === 'HEAD') {
          upstreamRes.resume()
          res.end()
          resolve()
          return
        }
        upstreamRes.pipe(res)
        upstreamRes.on('end', resolve)
      },
    )

    upstreamReq.on('error', (error) => {
      console.error(error)
      if (!res.headersSent) {
        send(res, 502, 'Proxy request failed\n', { 'content-type': 'text/plain; charset=utf-8' })
      } else {
        res.end()
      }
      resolve()
    })

    if (['GET', 'HEAD'].includes(req.method || '')) {
      upstreamReq.end()
    } else {
      req.pipe(upstreamReq)
    }
  })
}

const server = https.createServer(
  {
    cert: readFileSync(certFile),
    key: readFileSync(keyFile),
  },
  async (req, res) => {
  try {
    const requestUrl = new URL(req.url || '/', `https://${req.headers.host || 'localhost'}`)
    const originalPath = cleanPathname(requestUrl.pathname)

    if (originalPath === '/favicon.ico') {
      res.writeHead(308, { location: '/images/favicons/favicon.png' })
      res.end()
      return
    }

    if (originalPath === '/R8-rowhome' || originalPath.startsWith('/R8-rowhome/')) {
      requestUrl.pathname = `/r8-rowhome${originalPath.slice('/R8-rowhome'.length)}`
      res.writeHead(308, { location: requestUrl.pathname + requestUrl.search })
      res.end()
      return
    }

    if (req.method === 'OPTIONS' && proxies.some((proxy) => originalPath === proxy.prefix || originalPath.startsWith(`${proxy.prefix}/`))) {
      res.writeHead(204, {
        'access-control-allow-origin': '*',
        'access-control-allow-methods': 'GET,HEAD,POST,PUT,PATCH,DELETE,OPTIONS',
        'access-control-allow-headers': 'authorization,content-type,x-requested-with',
      })
      res.end()
      return
    }

    const proxy = proxies.find((item) => originalPath === item.prefix || originalPath.startsWith(`${item.prefix}/`))
    if (proxy && proxy.origin) {
      await proxyRequest(req, res, requestUrl, proxy)
      return
    }

    const filePath = await existingFile(originalPath)
    if (filePath) {
      await serveFile(req, res, filePath, originalPath)
      return
    }

    if (isHtmlNavigation(req) || looksLikeSpaRoute(originalPath)) {
      if (originalPath === '/p' || originalPath.startsWith('/p/')) {
        const portalIndex = await existingFile('/p/index.html')
        if (portalIndex) {
          await serveFile(req, res, portalIndex, '/p/index.html')
          return
        }
      }

      if (originalPath === '/r8-rowhome' || originalPath.startsWith('/r8-rowhome/')) {
        const rowhomeIndex = await existingFile('/r8-rowhome/index.html')
        if (rowhomeIndex) {
          await serveFile(req, res, rowhomeIndex, '/r8-rowhome/index.html')
          return
        }
      }
    }

    send(res, 404, 'Not found\n', { 'content-type': 'text/plain; charset=utf-8' })
  } catch (error) {
    console.error(error)
    send(res, 500, 'Internal server error\n', { 'content-type': 'text/plain; charset=utf-8' })
  }
})

server.listen(port, '0.0.0.0', () => {
  console.log(`Serving ${siteRoot} on https://0.0.0.0:${port}`)
  console.log('Boundaries: / static, /p/ portal, /r8-rowhome/ rowhome')
})
NODE

docker rm -f "$CONTAINER_NAME" "$CONTAINER_NAME-portal" "$CONTAINER_NAME-r8-rowhome" >/dev/null 2>&1 || true
docker network create "$NETWORK_NAME" >/dev/null 2>&1 || true

if [[ "$MODE" == "dev" ]]; then
  if [[ -f "$ROOT_DIR/portal/web/package.json" ]]; then
    echo "[serve-local] starting portal Vite dev server"
    docker run -d --rm \
      --name "$CONTAINER_NAME-portal" \
      --network "$NETWORK_NAME" \
      -v "$ROOT_DIR/portal/web:/app" \
      -w /app \
      -e "VITE_PUBLIC_BASE=/p/" \
      -e "VITE_PIDP_BASE_URL=${VITE_PIDP_BASE_URL:-https://id.codecollective.us}" \
      -e "VITE_UPDATE_MANIFEST_URL=/p/mobile-update.json" \
      -e "VITE_ALLOWED_HOSTS=localhost,127.0.0.1,$CONTAINER_NAME,$CONTAINER_NAME-portal" \
      "$NODE_IMAGE" \
      sh -lc 'if [ ! -d node_modules ]; then npm ci || npm install; fi; npx vite --host 0.0.0.0 --port 5173' >/dev/null
  else
    echo "[serve-local] portal/web missing; /p/ will use any existing static files"
  fi

  if [[ -f "$ROOT_DIR/r8-rowhome/package.json" ]]; then
    echo "[serve-local] starting r8-rowhome Vite dev server"
    docker run -d --rm \
      --name "$CONTAINER_NAME-r8-rowhome" \
      --network "$NETWORK_NAME" \
      -v "$ROOT_DIR/r8-rowhome:/app" \
      -w /app \
      -e "VITE_PUBLIC_BASE=/r8-rowhome/" \
      "$NODE_IMAGE" \
      sh -lc 'if [ ! -d node_modules ]; then npm ci || npm install; fi; npx vite --host 0.0.0.0 --port 5173' >/dev/null
  else
    echo "[serve-local] r8-rowhome missing; /r8-rowhome/ will use any existing static files"
  fi
fi

DOCKER_ARGS=(
  run
  --rm
  --name "$CONTAINER_NAME"
  --network "$NETWORK_NAME"
  -p "${HOST}:${PORT}:8080"
  -v "$SERVER_FILE:/server.mjs:ro"
  -v "$CERT_DIR:/certs:ro"
  -e "CONTAINER_PORT=8080"
  -e "TLS_CERT_FILE=/certs/localhost.crt"
  -e "TLS_KEY_FILE=/certs/localhost.key"
)

if [[ "$MODE" == "build" ]]; then
  DOCKER_ARGS+=(-v "$SITE_DIR:/site:ro" -e "SITE_ROOT=/site")
else
  DOCKER_ARGS+=(
    -v "$ROOT_DIR:/site:ro"
    -e "SITE_ROOT=/site"
    -e "PORTAL_ORIGIN=http://$CONTAINER_NAME-portal:5173"
    -e "R8_ROWHOME_ORIGIN=http://$CONTAINER_NAME-r8-rowhome:5173"
  )
fi

for name in PIDP_PROXY_ORIGIN PIDP_API_ORIGIN ORG_API_ORIGIN GOVERNANCE_API_ORIGIN PORTAL_ORIGIN R8_ROWHOME_ORIGIN; do
  if [[ -n "${!name:-}" ]]; then
    DOCKER_ARGS+=(-e "$name=${!name}")
  fi
done

if [[ "$DETACH" -eq 1 ]]; then
  DOCKER_ARGS+=(-d)
elif [[ -t 0 && -t 1 ]]; then
  DOCKER_ARGS+=(-it)
fi

DOCKER_ARGS+=("$NODE_IMAGE" node /server.mjs)

echo "[serve-local] starting $CONTAINER_NAME with $NODE_IMAGE"
echo "[serve-local] URL: https://$HOST:$PORT/"
echo "[serve-local] self-signed cert: use browser trust flow or curl -k"
echo "[serve-local] mode: $MODE"
docker "${DOCKER_ARGS[@]}"
