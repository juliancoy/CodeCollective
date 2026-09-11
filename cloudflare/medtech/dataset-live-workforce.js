import { fetchUpstream, paginateLocal, timeoutSignal, nowIso } from './dataset-core.js'

const BLS_API_URL = 'https://api.bls.gov/publicAPI/v2/timeseries/data/'
const BLS_DATATYPE_URL = 'https://download.bls.gov/pub/time.series/oe/oe.datatype'
const AHRF_RELEASES = [
  { release: 'AHRF 2024–2025', level: 'County-level primary file', format: 'CSV ZIP', url: 'https://data.hrsa.gov/DataDownload/AHRF/AHRF_2024-2025_CSV.zip' },
  { release: 'AHRF 2024–2025', level: 'State and national file', format: 'CSV ZIP', url: 'https://data.hrsa.gov/DataDownload/AHRF/AHRF_SN_2024-2025_CSV.zip' },
]
const OEWS_AREAS = {
  baltimore: { areatype: 'M', code: '0012580', label: 'Baltimore-Columbia-Towson, MD' },
  maryland: { areatype: 'S', code: '2400000', label: 'Maryland' },
}
const OEWS_OCCUPATIONS = [
  ['119111', 'Medical and Health Services Managers', 'Administration'],
  ['291071', 'Physician Assistants', 'Advanced practice'],
  ['291122', 'Occupational Therapists', 'Rehabilitation'],
  ['291123', 'Physical Therapists', 'Rehabilitation'],
  ['291124', 'Radiation Therapists', 'Oncology treatment'],
  ['291127', 'Speech-Language Pathologists', 'Rehabilitation'],
  ['291141', 'Registered Nurses', 'Nursing'],
  ['291171', 'Nurse Practitioners', 'Advanced practice'],
  ['291217', 'Neurologists', 'Physicians'],
  ['291224', 'Radiologists', 'Physicians'],
  ['291229', 'Physicians, All Other', 'Physicians'],
  ['292010', 'Clinical Laboratory Technologists and Technicians', 'Laboratory'],
  ['292032', 'Diagnostic Medical Sonographers', 'Imaging'],
  ['292033', 'Nuclear Medicine Technologists', 'Imaging'],
  ['292034', 'Radiologic Technologists and Technicians', 'Imaging'],
  ['292035', 'Magnetic Resonance Imaging Technologists', 'Imaging'],
  ['292036', 'Medical Dosimetrists', 'Oncology treatment'],
  ['292072', 'Medical Records Specialists', 'Health information'],
  ['299021', 'Health Information Technologists and Medical Registrars', 'Health information'],
  ['299092', 'Genetic Counselors', 'Genomics'],
].map(([code, occupation, group]) => ({ code, occupation, group }))
let blsDatatypeMemo = null

function parseTsv(text) {
  const lines = text.replace(/^\uFEFF/, '').split(/\r?\n/).filter(Boolean)
  if (!lines.length) return []
  const headers = lines.shift().split('\t').map((item) => item.trim()).filter(Boolean)
  return lines.map((line) => {
    const values = line.split('\t')
    return Object.fromEntries(headers.map((header, index) => [header, (values[index] || '').trim()]))
  })
}

async function blsDatatypeCodes() {
  if (blsDatatypeMemo) return blsDatatypeMemo
  const fallback = {
    employment: '01',
    annual_mean_wage: '04',
    annual_median_wage: '13',
    location_quotient: '17',
  }
  try {
    const response = await fetchUpstream(BLS_DATATYPE_URL, { headers: { accept: 'text/plain,*/*' }, timeout: 12000 })
    const rows = parseTsv(await response.text())
    const lookup = new Map(rows.map((row) => [String(row.datatype_name || '').trim().toLocaleLowerCase(), String(row.datatype_code || '').padStart(2, '0')]))
    const find = (pattern) => rows.find((row) => pattern.test(String(row.datatype_name || '').trim()))?.datatype_code
    blsDatatypeMemo = {
      employment: lookup.get('employment') || fallback.employment,
      annual_mean_wage: lookup.get('annual mean wage') || fallback.annual_mean_wage,
      annual_median_wage: lookup.get('annual median wage') || fallback.annual_median_wage,
      location_quotient: find(/^location quotient$/i) || fallback.location_quotient,
    }
  } catch {
    blsDatatypeMemo = fallback
  }
  return blsDatatypeMemo
}

export function buildOewsSeriesId(area, occupationCode, datatypeCode) {
  return `OEU${area.areatype}${area.code}000000${occupationCode}${String(datatypeCode).padStart(2, '0')}`
}

function chunks(items, size) {
  const output = []
  for (let index = 0; index < items.length; index += size) output.push(items.slice(index, index + size))
  return output
}

async function blsOews(dataset, query) {
  const area = OEWS_AREAS[query.params.get('area')] || OEWS_AREAS.baltimore
  const codes = await blsDatatypeCodes()
  const measures = [
    ['employment', codes.employment],
    ['annual_mean_wage', codes.annual_mean_wage],
    ['annual_median_wage', codes.annual_median_wage],
    ['location_quotient', codes.location_quotient],
  ]
  const requests = []
  const seriesMap = new Map()
  for (const occupation of OEWS_OCCUPATIONS) {
    for (const [measure, datatypeCode] of measures) {
      const seriesId = buildOewsSeriesId(area, occupation.code, datatypeCode)
      seriesMap.set(seriesId, { occupation, measure })
      requests.push(seriesId)
    }
  }

  const responses = await Promise.all(chunks(requests, 25).map((seriesid) => fetchUpstream(BLS_API_URL, {
    method: 'POST',
    headers: { 'content-type': 'application/json', accept: 'application/json' },
    body: JSON.stringify({ seriesid }),
  })))
  const payloads = await Promise.all(responses.map((response) => response.json()))
  const output = new Map(OEWS_OCCUPATIONS.map((occupation) => [occupation.code, {
    area: area.label,
    occupation_code: occupation.code.replace(/^(\d{2})(\d{4})$/, '$1-$2'),
    occupation: occupation.occupation,
    occupational_group: occupation.group,
    employment: '',
    annual_mean_wage: '',
    annual_median_wage: '',
    location_quotient: '',
    reference_year: '',
    footnotes: '',
  }]))
  const warnings = []

  for (const payload of payloads) {
    if (payload.status && payload.status !== 'REQUEST_SUCCEEDED') warnings.push(...(payload.message || ['BLS request did not report success']))
    for (const series of payload.Results?.series || []) {
      const metadata = seriesMap.get(series.seriesID)
      if (!metadata) continue
      const row = output.get(metadata.occupation.code)
      const datum = series.data?.[0]
      if (!datum) continue
      const value = Number(String(datum.value || '').replaceAll(',', ''))
      row[metadata.measure] = Number.isFinite(value) ? value : datum.value || ''
      row.reference_year = datum.year || row.reference_year
      const footnotes = (datum.footnotes || []).map((item) => item?.text).filter(Boolean)
      if (footnotes.length) row.footnotes = [...new Set([row.footnotes, ...footnotes].filter(Boolean))].join('; ')
    }
  }

  const local = paginateLocal([...output.values()], query)
  return {
    ...local,
    geography: area.label,
    sourceUpdatedAt: `${[...output.values()].map((row) => row.reference_year).filter(Boolean).sort().at(-1) || 'Latest'} May OEWS release`,
    upstream: { url: BLS_API_URL, status: 200 },
    warnings: [
      ...new Set(warnings),
      'Detailed OEWS estimates may be blank or suppressed; broad occupations do not equal specialty-specific clinical capacity.',
    ],
  }
}

async function headMetadata(item) {
  const checkedAt = nowIso()
  let response
  try {
    response = await fetch(item.url, { method: 'HEAD', redirect: 'follow', signal: timeoutSignal(15000) })
    if (!response.ok) throw new Error('HEAD unavailable')
  } catch {
    response = await fetch(item.url, {
      method: 'GET',
      headers: { range: 'bytes=0-0' },
      redirect: 'follow',
      signal: timeoutSignal(15000),
    })
  }
  return {
    ...item,
    http_status: response.status,
    content_type: response.headers.get('content-type') || '',
    content_length: response.headers.get('content-length') || response.headers.get('content-range')?.split('/').at(-1) || '',
    last_modified: response.headers.get('last-modified') || '',
    etag: response.headers.get('etag') || '',
    checked_at: checkedAt,
  }
}

async function hrsaAhrfReleases(dataset, query) {
  const rows = await Promise.all(AHRF_RELEASES.map(headMetadata))
  return {
    ...paginateLocal(rows, query),
    sourceUpdatedAt: rows.map((row) => row.last_modified).filter(Boolean).sort().at(-1) || 'HRSA release files updated 2025-12-18',
    upstream: { url: dataset.source_url, status: 200 },
    warnings: ['The live table verifies release files and their HTTP metadata; it does not unpack the 6,000-plus-variable archive in the browser.'],
  }
}


export { blsOews, hrsaAhrfReleases }
