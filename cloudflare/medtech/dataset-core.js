const DEFAULT_PAGE_SIZE = 100
const MAX_PAGE_SIZE = 500
const JSON_HEADERS = { 'content-type': 'application/json; charset=utf-8' }
let registryMemo = null
const MEDTECH_SPECIALTY_PREFIX = '/specialty/baltimore-medtech'

function medtechAssetPath(path) {
  if (typeof path !== 'string') return path
  if (path === MEDTECH_SPECIALTY_PREFIX) return '/'
  if (path.startsWith(`${MEDTECH_SPECIALTY_PREFIX}/`)) return path.slice(MEDTECH_SPECIALTY_PREFIX.length) || '/'
  return path
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value))
}

function integer(value, fallback) {
  const parsed = Number.parseInt(value, 10)
  return Number.isFinite(parsed) ? parsed : fallback
}

function nowIso() {
  return new Date().toISOString()
}

function responseJson(payload, status = 200, headers = {}) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { ...JSON_HEADERS, ...headers },
  })
}

function timeoutSignal(ms = 20000) {
  if (typeof AbortSignal !== 'undefined' && typeof AbortSignal.timeout === 'function') {
    return AbortSignal.timeout(ms)
  }
  return undefined
}

async function fetchUpstream(url, options = {}) {
  const { timeout = 20000, headers = {}, ...fetchOptions } = options
  const response = await fetch(url, {
    ...fetchOptions,
    signal: fetchOptions.signal || timeoutSignal(timeout),
    headers: {
      accept: 'application/json, text/plain;q=0.9, text/html;q=0.8, */*;q=0.5',
      ...headers,
    },
  })
  if (!response.ok) {
    const body = await response.text().catch(() => '')
    throw new Error(`Upstream ${response.status}: ${body.slice(0, 240) || response.statusText}`)
  }
  return response
}

async function loadRegistry(env, origin) {
  if (registryMemo) return registryMemo
  const response = await env.ASSETS.fetch(new Request(`${origin}/dataset-registry.json`))
  if (!response.ok) throw new Error('Dataset registry is unavailable')
  const manifest = await response.json()
  if (!Array.isArray(manifest.parts)) {
    registryMemo = manifest
    return registryMemo
  }
  const parts = await Promise.all(manifest.parts.map(async (path) => {
    const partPath = medtechAssetPath(path)
    const part = await env.ASSETS.fetch(new Request(`${origin}${partPath}`))
    if (!part.ok) throw new Error(`Dataset registry part is unavailable: ${path}`)
    return part.json()
  }))
  registryMemo = { meta: manifest.meta, datasets: parts.flatMap((part) => part.datasets || []) }
  return registryMemo
}

async function loadAssetJson(env, origin, path) {
  const assetPath = medtechAssetPath(path)
  const response = await env.ASSETS.fetch(new Request(`${origin}${assetPath}`))
  if (!response.ok) throw new Error(`Repository dataset unavailable: ${assetPath}`)
  return response.json()
}

function scalar(value) {
  if (value === null || value === undefined) return ''
  if (Array.isArray(value)) return value.map(scalar).filter(Boolean).join('; ')
  if (typeof value === 'object') return JSON.stringify(value)
  return value
}

function normalizeRows(rows) {
  return rows.map((row) => Object.fromEntries(
    Object.entries(row || {}).map(([key, value]) => [key, scalar(value)]),
  ))
}

function deriveColumns(rows, preferred = []) {
  const seen = new Set()
  const columns = []
  for (const key of preferred) {
    if (!seen.has(key)) {
      seen.add(key)
      columns.push(key)
    }
  }
  for (const row of rows) {
    for (const key of Object.keys(row)) {
      if (!seen.has(key)) {
        seen.add(key)
        columns.push(key)
      }
    }
  }
  return columns
}

function compareValues(left, right) {
  const leftNumber = typeof left === 'number' ? left : Number(String(left).replaceAll(',', ''))
  const rightNumber = typeof right === 'number' ? right : Number(String(right).replaceAll(',', ''))
  if (Number.isFinite(leftNumber) && Number.isFinite(rightNumber)) return leftNumber - rightNumber
  return String(left ?? '').localeCompare(String(right ?? ''), undefined, { numeric: true, sensitivity: 'base' })
}

function filterAndSortRows(rows, params) {
  const q = (params.get('q') || '').trim().toLocaleLowerCase()
  let output = q
    ? rows.filter((row) => Object.values(row).some((value) => String(value).toLocaleLowerCase().includes(q)))
    : rows
  const sort = params.get('sort')
  if (sort && output.some((row) => Object.hasOwn(row, sort))) {
    const direction = params.get('direction') === 'desc' ? -1 : 1
    output = [...output].sort((left, right) => direction * compareValues(left[sort], right[sort]))
  }
  return output
}

function paginateLocal(rows, query) {
  const filtered = filterAndSortRows(rows, query.params)
  const start = (query.page - 1) * query.pageSize
  return {
    rows: filtered.slice(start, start + query.pageSize),
    total: filtered.length,
    totalKnown: true,
    sortScope: 'all matching rows',
  }
}

function extractRows(payload) {
  if (Array.isArray(payload)) return payload
  for (const key of ['results', 'data', 'items', 'records']) {
    if (Array.isArray(payload?.[key])) return payload[key]
  }
  return []
}

function extractTotal(payload, fallback) {
  const candidates = [payload?.count, payload?.total, payload?.total_count, payload?.result_count, payload?.meta?.count, payload?.meta?.total]
  for (const candidate of candidates) {
    const value = Number(candidate)
    if (Number.isFinite(value)) return value
  }
  return fallback
}

function metadataDate(payload) {
  const candidates = [
    payload?.modified,
    payload?.last_modified,
    payload?.metadata?.modified,
    payload?.distribution?.[0]?.modified,
    payload?.issued,
  ]
  return candidates.find(Boolean) || null
}

function parseQuery(url, dataset) {
  const pageSize = clamp(integer(url.searchParams.get('page_size'), dataset.default_page_size || DEFAULT_PAGE_SIZE), 1, dataset.max_page_size || MAX_PAGE_SIZE)
  return {
    page: Math.max(1, integer(url.searchParams.get('page'), 1)),
    pageSize,
    params: url.searchParams,
  }
}

function makePayload(dataset, query, adapterResult) {
  const rows = normalizeRows(adapterResult.rows || [])
  const columns = deriveColumns(rows, dataset.preferred_columns || [])
  return {
    ok: true,
    dataset: {
      id: dataset.id,
      title: dataset.title,
      short_title: dataset.short_title,
      publisher: dataset.publisher,
      category: dataset.category,
      mode: dataset.mode,
      coverage: dataset.coverage,
      refresh: dataset.refresh,
      geography: adapterResult.geography || dataset.geography,
      description: dataset.description,
      source_url: dataset.source_url,
      api_url: dataset.api_url || null,
      limitations: dataset.limitations || [],
    },
    live: dataset.mode.startsWith('live-'),
    fetched_at: nowIso(),
    source_updated_at: adapterResult.sourceUpdatedAt || null,
    page: query.page,
    page_size: query.pageSize,
    total: adapterResult.total ?? rows.length,
    total_known: adapterResult.totalKnown ?? false,
    sort_scope: adapterResult.sortScope || 'current upstream page',
    columns,
    rows,
    warnings: adapterResult.warnings || [],
    upstream: adapterResult.upstream || null,
    query: Object.fromEntries([...query.params.entries()].filter(([key]) => !['refresh', '_'].includes(key))),
  }
}

function csvCell(value) {
  const text = String(value ?? '')
  return /[",\n\r]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text
}

function payloadToCsv(payload) {
  const lines = [payload.columns.map(csvCell).join(',')]
  for (const row of payload.rows) lines.push(payload.columns.map((column) => csvCell(row[column])).join(','))
  return lines.join('\r\n')
}

function addPdcCondition(url, index, property, value, operator = '=') {
  if (!value) return index
  url.searchParams.set(`conditions[${index}][property]`, property)
  url.searchParams.set(`conditions[${index}][value]`, value)
  url.searchParams.set(`conditions[${index}][operator]`, operator)
  return index + 1
}


export {
  clamp, integer, nowIso, responseJson, timeoutSignal, fetchUpstream,
  loadRegistry, loadAssetJson, scalar, normalizeRows, deriveColumns,
  compareValues, filterAndSortRows, paginateLocal, extractRows, extractTotal,
  metadataDate, parseQuery, makePayload, payloadToCsv, addPdcCondition,
}
