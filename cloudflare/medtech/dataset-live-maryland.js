import { fetchUpstream, nowIso, paginateLocal } from './dataset-core.js'

const MD_PVS_URL = 'https://emedicaid.health.maryland.gov/searchableProv/main.action'
const MD_PROVIDER_FINDER_INFO_URL = 'https://health.maryland.gov/mmcp/Pages/provider-finder.aspx'
const MD_PROVIDER_FINDER_TOOL_URL = 'https://maryland.providersearch.com/'

function decodeHtml(value) {
  return value
    .replace(/<[^>]+>/g, ' ')
    .replace(/&nbsp;/gi, ' ')
    .replace(/&amp;/gi, '&')
    .replace(/&#39;/g, "'")
    .replace(/&quot;/gi, '"')
    .replace(/\s+/g, ' ')
    .trim()
}

async function marylandMedicaidPvs(dataset, query) {
  const response = await fetchUpstream(MD_PVS_URL, { headers: { accept: 'text/html' } })
  const html = await response.text()
  const options = [...html.matchAll(/<option\b[^>]*value\s*=\s*["']?([^"' >]*)[^>]*>([\s\S]*?)<\/option>/gi)]
    .map((match) => ({ code: decodeHtml(match[1]), label: decodeHtml(match[2]) }))
    .filter((option) => option.code || option.label)
    .filter((option, index, all) => all.findIndex((item) => item.code === option.code && item.label === option.label) === index)
  const notice = 'An active PVS result verifies fee-for-service enrollment status for a date; it does not necessarily mean the provider accepts payment or every HealthChoice plan.'
  const rows = options.length
    ? options.map((option) => ({
      provider_type_code: option.code,
      provider_type: option.label,
      source_status: 'Live provider-type option from the public PVS form',
      lookup_url: MD_PVS_URL,
      checked_at: nowIso(),
      notice,
    }))
    : [{
      provider_type_code: '',
      provider_type: 'Official provider lookup',
      source_status: 'PVS reachable; provider-type options were not exposed in parseable HTML',
      lookup_url: MD_PVS_URL,
      checked_at: nowIso(),
      notice,
    }]
  return {
    ...paginateLocal(rows, query),
    sourceUpdatedAt: response.headers.get('last-modified'),
    upstream: { url: MD_PVS_URL, status: response.status },
    warnings: [
      'Maryland exposes PVS as an interactive verification system, not a documented public bulk API.',
      notice,
    ],
  }
}


function htmlTitle(html) {
  const match = html.match(/<title[^>]*>([\s\S]*?)<\/title>/i)
  return match ? decodeHtml(match[1]) : ''
}

async function inspectHtmlResource(resource) {
  const response = await fetchUpstream(resource.url, {
    headers: { accept: 'text/html,application/xhtml+xml' },
    timeout: 15000,
  })
  const html = await response.text()
  return {
    resource: resource.resource,
    role: resource.role,
    http_status: response.status,
    page_title: htmlTitle(html),
    option_count: (html.match(/<option\b/gi) || []).length,
    last_modified: response.headers.get('last-modified') || '',
    checked_at: nowIso(),
    url: resource.url,
    capability: resource.capability,
    access_note: resource.access_note,
  }
}

async function marylandMedicaidProviderFinder(dataset, query) {
  const accessNote = 'Maryland states that all providers and facilities listed in the directory accept Medicaid, but not every provider accepts every HealthChoice managed-care plan.'
  const resources = [
    {
      resource: 'Maryland Medicaid Provider Finder guidance',
      role: 'Official program guidance and entry point',
      url: MD_PROVIDER_FINDER_INFO_URL,
      capability: 'Explains Medicaid and HealthChoice provider search and links to the official directory.',
      access_note: accessNote,
    },
    {
      resource: 'Maryland ProviderSearch directory',
      role: 'Interactive provider and facility lookup',
      url: MD_PROVIDER_FINDER_TOOL_URL,
      capability: 'Search by location, specialty, facility, provider, and plan through the official interactive directory.',
      access_note: accessNote,
    },
  ]
  const settled = await Promise.allSettled(resources.map(inspectHtmlResource))
  const rows = settled.map((result, index) => result.status === 'fulfilled' ? result.value : {
    resource: resources[index].resource,
    role: resources[index].role,
    http_status: 'unavailable',
    page_title: '',
    option_count: '',
    last_modified: '',
    checked_at: nowIso(),
    url: resources[index].url,
    capability: resources[index].capability,
    access_note: `${accessNote} Live inspection error: ${result.reason instanceof Error ? result.reason.message : String(result.reason)}`,
  })
  const status = rows.every((row) => Number(row.http_status) >= 200 && Number(row.http_status) < 400) ? 200 : 207
  return {
    ...paginateLocal(rows, query),
    sourceUpdatedAt: rows.map((row) => row.last_modified).filter(Boolean).sort().at(-1) || null,
    upstream: { url: MD_PROVIDER_FINDER_INFO_URL, status },
    warnings: [
      'The official directory is an interactive lookup, not a documented public bulk API; this sheet reports live source status and links to the search rather than scraping provider results.',
      accessNote,
    ],
  }
}


export { marylandMedicaidPvs, marylandMedicaidProviderFinder }
