import {
  addPdcCondition, extractRows, extractTotal, fetchUpstream,
  filterAndSortRows, metadataDate, timeoutSignal,
} from './dataset-core.js'

const CMS_DOCTORS_URL = 'https://data.cms.gov/provider-data/api/1/datastore/query/mj5m-pzi6/0'
const CMS_DOCTORS_META_URL = 'https://data.cms.gov/provider-data/api/1/metastore/schemas/dataset/items/mj5m-pzi6'
const CMS_SERVICES_URL = 'https://data.cms.gov/data-api/v1/dataset/92396110-2aed-4d63-a6a2-5d6207d46a29/data'
const NPPES_URL = 'https://npiregistry.cms.hhs.gov/api/'

async function cmsDoctorsClinicians(dataset, query) {
  const upstream = new URL(CMS_DOCTORS_URL)
  upstream.searchParams.set('offset', String((query.page - 1) * query.pageSize))
  upstream.searchParams.set('limit', String(query.pageSize))
  let index = 0
  index = addPdcCondition(upstream, index, 'state', query.params.get('state') || 'MD')
  index = addPdcCondition(upstream, index, 'citytown', query.params.get('city'), 'CONTAINS')
  index = addPdcCondition(upstream, index, 'pri_spec', query.params.get('specialty'), 'CONTAINS')
  index = addPdcCondition(upstream, index, 'npi', query.params.get('npi'))
  const allowedSearchFields = new Set(['provider_last_name', 'provider_first_name', 'facility_name'])
  const searchField = allowedSearchFields.has(query.params.get('search_field')) ? query.params.get('search_field') : 'provider_last_name'
  index = addPdcCondition(upstream, index, searchField, query.params.get('q'), 'CONTAINS')

  const [response, metadataResponse] = await Promise.all([
    fetchUpstream(upstream),
    fetch(CMS_DOCTORS_META_URL, { headers: { accept: 'application/json' }, signal: timeoutSignal(10000) }).catch(() => null),
  ])
  const payload = await response.json()
  const rows = extractRows(payload)
  const metadata = metadataResponse?.ok ? await metadataResponse.json().catch(() => null) : null
  const sortedRows = filterAndSortRows(rows, new URLSearchParams({
    sort: query.params.get('sort') || '',
    direction: query.params.get('direction') || '',
  }))

  return {
    rows: sortedRows,
    total: extractTotal(payload, rows.length),
    totalKnown: Number.isFinite(Number(payload?.count ?? payload?.total ?? payload?.meta?.count)),
    sourceUpdatedAt: metadataDate(metadata) || response.headers.get('last-modified'),
    upstream: { url: upstream.toString(), status: response.status },
    warnings: [
      'One clinician may appear on multiple rows for different enrollments, groups, or practice addresses.',
    ],
  }
}

function addCmsFilter(url, key, path, value, operator = '=') {
  if (!value) return
  if (operator === '=') {
    url.searchParams.set(`filter[${path}]`, value)
    return
  }
  url.searchParams.set(`filter[${key}][condition][path]`, path)
  url.searchParams.set(`filter[${key}][condition][operator]`, operator)
  url.searchParams.set(`filter[${key}][condition][value]`, value)
}

async function cmsProviderServices(dataset, query) {
  const upstream = new URL(CMS_SERVICES_URL)
  upstream.searchParams.set('size', String(query.pageSize))
  upstream.searchParams.set('offset', String((query.page - 1) * query.pageSize))
  addCmsFilter(upstream, 'state', 'Rndrng_Prvdr_State_Abrvtn', query.params.get('state') || 'MD')
  addCmsFilter(upstream, 'npi', 'Rndrng_NPI', query.params.get('npi'))
  addCmsFilter(upstream, 'hcpcs', 'HCPCS_Cd', query.params.get('hcpcs'))
  addCmsFilter(upstream, 'provider-type', 'Rndrng_Prvdr_Type', query.params.get('provider_type'), 'CONTAINS')
  const allowedSearchFields = new Set(['HCPCS_Desc', 'Rndrng_Prvdr_Last_Org_Name', 'Rndrng_Prvdr_City'])
  const searchField = allowedSearchFields.has(query.params.get('search_field')) ? query.params.get('search_field') : 'HCPCS_Desc'
  addCmsFilter(upstream, 'search', searchField, query.params.get('q'), 'CONTAINS')

  const response = await fetchUpstream(upstream)
  const payload = await response.json()
  const rows = extractRows(payload)
  const sortedRows = filterAndSortRows(rows, new URLSearchParams({
    sort: query.params.get('sort') || '',
    direction: query.params.get('direction') || '',
  }))
  const total = extractTotal(payload, rows.length)
  return {
    rows: sortedRows,
    total,
    totalKnown: total !== rows.length || Boolean(payload?.meta?.count || payload?.count || payload?.total),
    sourceUpdatedAt: response.headers.get('last-modified') || '2024 data; CMS page updated 2026-05-21',
    upstream: { url: upstream.toString(), status: response.status },
    warnings: [
      'This file covers Original Medicare fee-for-service and does not represent every service a provider delivers.',
      'CMS suppresses rows involving fewer than 11 beneficiaries.',
    ],
  }
}

function withWildcard(value) {
  if (!value) return null
  return value.includes('*') ? value : `${value}*`
}

function flattenNppes(result) {
  const basic = result.basic || {}
  const address = (result.addresses || []).find((item) => item.address_purpose === 'LOCATION') || result.addresses?.[0] || {}
  const primary = (result.taxonomies || []).find((item) => item.primary) || result.taxonomies?.[0] || {}
  const name = basic.organization_name || [basic.first_name, basic.middle_name, basic.last_name, basic.suffix].filter(Boolean).join(' ')
  return {
    number: result.number,
    enumeration_type: result.enumeration_type,
    name,
    credential: basic.credential || basic.authorized_official_credential || '',
    status: basic.status,
    primary_taxonomy_code: primary.code,
    primary_taxonomy: primary.desc,
    all_taxonomies: (result.taxonomies || []).map((item) => `${item.code} — ${item.desc}`).join('; '),
    address_1: address.address_1,
    address_2: address.address_2,
    city: address.city,
    state: address.state,
    postal_code: address.postal_code,
    telephone_number: address.telephone_number,
    last_updated_epoch: basic.last_updated_epoch,
    enumeration_date: basic.enumeration_date,
  }
}

async function nppesRegistry(dataset, query) {
  const upstream = new URL(NPPES_URL)
  upstream.searchParams.set('version', '2.1')
  upstream.searchParams.set('limit', String(Math.min(200, query.pageSize)))
  upstream.searchParams.set('skip', String((query.page - 1) * query.pageSize))
  const npi = query.params.get('npi')
  if (npi) upstream.searchParams.set('number', npi)
  else {
    upstream.searchParams.set('state', query.params.get('state') || 'MD')
    if (query.params.get('city')) upstream.searchParams.set('city', withWildcard(query.params.get('city')))
    if (query.params.get('taxonomy')) upstream.searchParams.set('taxonomy_description', withWildcard(query.params.get('taxonomy')))
    if (query.params.get('last_name')) upstream.searchParams.set('last_name', withWildcard(query.params.get('last_name')))
    if (query.params.get('organization')) upstream.searchParams.set('organization_name', withWildcard(query.params.get('organization')))
  }

  const response = await fetchUpstream(upstream)
  const payload = await response.json()
  const rows = (payload.results || []).map(flattenNppes)
  const sortedRows = filterAndSortRows(rows, new URLSearchParams({
    sort: query.params.get('sort') || '',
    direction: query.params.get('direction') || '',
  }))
  return {
    rows: sortedRows,
    total: Number(payload.result_count || rows.length),
    totalKnown: false,
    sourceUpdatedAt: response.headers.get('last-modified'),
    upstream: { url: upstream.toString(), status: response.status },
    warnings: ['NPI enumeration is not evidence of licensure, credentialing, active practice, appointment availability, or payer participation.'],
  }
}


export { cmsDoctorsClinicians, cmsProviderServices, nppesRegistry }
