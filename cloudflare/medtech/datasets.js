import { loadRegistry, makePayload, nowIso, parseQuery, payloadToCsv, responseJson } from './dataset-core.js'
import { cmsDoctorsClinicians, cmsProviderServices, nppesRegistry } from './dataset-live-cms.js'
import { blsOews, hrsaAhrfReleases } from './dataset-live-workforce.js'
import { marylandMedicaidProviderFinder, marylandMedicaidPvs } from './dataset-live-maryland.js'
import {
  localCareTeams,
  localDistortions,
  localMedicalScienceFieldAtlas,
  localMetaIndex,
  localStrategyFields,
  localSystems,
} from './dataset-snapshots.js'

const API_PREFIX = '/api/datasets'

const ADAPTERS = {
  cms_doctors_clinicians: cmsDoctorsClinicians,
  cms_provider_services: cmsProviderServices,
  nppes_registry: nppesRegistry,
  bls_oews: blsOews,
  hrsa_ahrf_releases: hrsaAhrfReleases,
  maryland_medicaid_pvs: marylandMedicaidPvs,
  maryland_medicaid_provider_finder: marylandMedicaidProviderFinder,
  local_meta_index: localMetaIndex,
  local_medical_science_field_atlas: localMedicalScienceFieldAtlas,
  local_systems: localSystems,
  local_strategy_fields: localStrategyFields,
  local_distortions: localDistortions,
  local_care_teams: localCareTeams,
}

function cacheHeaders(dataset) {
  const seconds = dataset.cache_seconds || 300
  return {
    'cache-control': `public, max-age=0, s-maxage=${seconds}, stale-while-revalidate=${Math.max(60, seconds * 2)}`,
    'x-dataset-mode': dataset.mode,
    'x-dataset-id': dataset.id,
  }
}

export async function handleDatasetApi(request, env, url = new URL(request.url), assetOrigin = url.origin) {
  if (!url.pathname.startsWith(API_PREFIX)) return null
  if (!['GET', 'HEAD'].includes(request.method)) {
    return responseJson({ ok: false, error: 'Method not allowed' }, 405, { allow: 'GET, HEAD' })
  }

  const registry = await loadRegistry(env, assetOrigin)
  const rest = url.pathname.slice(API_PREFIX.length).replace(/^\//, '')
  if (!rest) {
    return responseJson({ ok: true, fetched_at: nowIso(), ...registry }, 200, { 'cache-control': 'public, max-age=300' })
  }

  const csv = rest.endsWith('.csv')
  const id = decodeURIComponent(csv ? rest.slice(0, -4) : rest)
  const dataset = registry.datasets.find((item) => item.id === id)
  if (!dataset) return responseJson({ ok: false, error: `Unknown dataset: ${id}` }, 404)
  const adapter = ADAPTERS[dataset.adapter]
  if (!adapter) return responseJson({ ok: false, error: `Dataset adapter is not configured: ${dataset.adapter}` }, 500)
  const query = parseQuery(url, dataset)

  const cache = globalThis.caches?.default
  const shouldRefresh = url.searchParams.get('refresh') === '1'
  const cacheUrl = new URL(url)
  cacheUrl.searchParams.delete('refresh')
  cacheUrl.searchParams.delete('_')
  const cacheKey = new Request(cacheUrl.toString(), { method: 'GET' })
  if (cache && !shouldRefresh) {
    const cached = await cache.match(cacheKey)
    if (cached) return cached
  }

  let response
  try {
    const adapterResult = await adapter(dataset, query, env, assetOrigin)
    const payload = makePayload(dataset, query, adapterResult)
    if (csv) {
      response = new Response(payloadToCsv(payload), {
        status: 200,
        headers: {
          'content-type': 'text/csv; charset=utf-8',
          'content-disposition': `attachment; filename="${dataset.id}-page-${query.page}.csv"`,
          ...cacheHeaders(dataset),
        },
      })
    } else {
      response = responseJson(payload, 200, cacheHeaders(dataset))
    }
  } catch (error) {
    response = responseJson({
      ok: false,
      dataset: { id: dataset.id, title: dataset.title, source_url: dataset.source_url, mode: dataset.mode },
      fetched_at: nowIso(),
      error: error instanceof Error ? error.message : 'Dataset request failed',
    }, 502, { 'cache-control': 'no-store', 'x-dataset-id': dataset.id })
  }

  if (cache && response.ok && !shouldRefresh) await cache.put(cacheKey, response.clone())
  return request.method === 'HEAD' ? new Response(null, { status: response.status, headers: response.headers }) : response
}

export { buildOewsSeriesId } from './dataset-live-workforce.js'
