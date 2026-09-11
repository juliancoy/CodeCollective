import { calculateNeedAvailabilityMetrics } from './need-availability-metrics.js'
import { loadAssetJson, loadRegistry, paginateLocal } from './dataset-core.js'

async function localMetaIndex(dataset, query, env, origin) {
  const [metaIndex, registry] = await Promise.all([
    loadAssetJson(env, origin, '/medtech-meta-index.json'),
    loadRegistry(env, origin),
  ])
  const components = new Map(registry.datasets.map((component) => [component.id, component]))
  let rows = metaIndex.sources.map((source) => {
    const component = components.get(source.source_id)
    if (!component) throw new Error(`Meta Index component is not registered: ${source.source_id}`)
    return {
      decision_rank: source.decision_rank,
      source_id: source.source_id,
      source_name: component.title,
      publisher: component.publisher,
      source_tier: source.source_tier,
      source_tier_label: source.source_tier_label,
      authority_class: source.authority_class,
      evidence_type: source.evidence_type,
      unit_of_observation: source.unit_of_observation,
      data_layer: source.data_layer,
      availability_layer: source.availability_layer,
      mode: component.mode,
      geography: component.geography,
      coverage: component.coverage,
      refresh: component.refresh,
      decision_role: source.decision_role,
      quality_strength: source.quality_strength,
      principal_caveat: source.principal_caveat,
      join_keys: source.join_keys,
      dependencies: source.dependencies,
      component_sheet: component.page,
      live_endpoint: `/api/datasets/${component.id}`,
      source_url: component.source_url,
    }
  })

  const sourceTier = query.params.get('source_tier')
  const dataLayer = query.params.get('data_layer')?.trim().toLocaleLowerCase()
  const mode = query.params.get('mode')
  if (sourceTier) rows = rows.filter((row) => row.source_tier === sourceTier)
  if (dataLayer) rows = rows.filter((row) => row.data_layer.toLocaleLowerCase().includes(dataLayer))
  if (mode) rows = rows.filter((row) => row.mode === mode)

  return {
    ...paginateLocal(rows, query),
    sourceUpdatedAt: metaIndex.meta?.as_of || null,
    upstream: { url: '/medtech-meta-index.json + /dataset-registry.json', status: 200 },
    warnings: metaIndex.meta?.limitations || [],
  }
}

async function localMedicalScienceFieldAtlas(dataset, query, env, origin) {
  const payload = await loadAssetJson(env, origin, '/medical-science-field-atlas.json')
  const records = Array.isArray(payload) ? payload : payload.records || payload.fields || payload.items || []
  const rows = records.map((record) => ({
    id: record.id,
    name: record.name,
    scientific_lineage: record.scientific_lineage,
    body_parts: record.body_parts,
    methods: record.methods,
    scale: record.scale,
    population: record.population,
    translation: record.translation,
    subdisciplines: record.subdisciplines,
    tags: record.tags,
  }))
  return {
    ...paginateLocal(rows, query),
    sourceUpdatedAt: payload.meta?.as_of || payload.meta?.generated_at || null,
    upstream: { url: '/medical-science-field-atlas.json', status: 200 },
  }
}

async function localSystems(dataset, query, env, origin) {
  const payload = await loadAssetJson(env, origin, dataset.asset)
  const systems = payload.systems || payload.records || []
  const rows = systems.map((system) => ({
    id: system.id,
    short_name: system.short_name,
    name: system.name,
    kind: system.kind || '',
    stage: system.stage || '',
    layer: system.layer || '',
    role: system.role || '',
    question: system.question || '',
    scope: system.scope || '',
    steward: system.steward || '',
    identifier_shape: system.identifier_shape || '',
    source_urls: system.source_url || (system.source_links || []).map((link) => `${link.label}: ${link.url}`).join('; '),
    licensed: system.licensed ?? system.licensed_descriptions ?? '',
    tags: system.tags || system.match_terms || [],
    note: system.note || '',
  }))
  return {
    ...paginateLocal(rows, query),
    sourceUpdatedAt: payload.meta?.as_of || null,
    upstream: { url: dataset.asset, status: 200 },
  }
}

const STRATEGY_PATHS = ['/strategy-neurology.json', '/strategy-oncology.json', '/strategy-radiology.json', '/strategy-genomics.json']

async function loadStrategyFields(env, origin) {
  return Promise.all(STRATEGY_PATHS.map((path) => loadAssetJson(env, origin, path)))
}

async function localStrategyFields(dataset, query, env, origin) {
  const fields = await loadStrategyFields(env, origin)
  const rows = fields.map((field) => ({
    id: field.id,
    field: field.name,
    workforce: field.workforce?.value,
    workforce_year: field.workforce?.year,
    workforce_definition: field.workforce?.definition,
    pipeline: field.pipeline?.value,
    pipeline_year: field.pipeline?.year,
    pipeline_definition: field.pipeline?.definition,
    need: field.need?.value,
    need_year: field.need?.year,
    need_type: field.need?.type,
    funding_proxy: field.funding?.proxy_label,
    funding_fy2024: field.funding?.values?.find((item) => Number(item.year) === 2024)?.value || field.funding?.values?.at(-1)?.value,
    digital_leverage: field.digital_leverage?.score,
    stance: field.stance,
    labor_strategy: field.strategy?.labor,
    application_strategy: field.strategy?.applications,
  }))
  return {
    ...paginateLocal(rows, query),
    sourceUpdatedAt: fields.map((field) => field.meta?.as_of).filter(Boolean).sort().at(-1) || null,
    upstream: { url: 'repository strategy field files', status: 200 },
  }
}

async function localDistortions(dataset, query, env, origin) {
  const fields = await loadStrategyFields(env, origin)
  const result = calculateNeedAvailabilityMetrics(fields)
  const rows = result.records.map((record) => ({
    rank: record.rank,
    id: record.id,
    field: record.name,
    need_proxy: record.field.need?.value,
    need_type: record.field.need?.type,
    physician_workforce: record.field.workforce?.value,
    physician_pipeline: record.field.pipeline?.value,
    need_per_physician: record.peoplePerSpecialist,
    entrants_per_1000_physicians: record.entrantsPerThousandSpecialists,
    need_score: record.needScore,
    availability_score: record.availabilityScore,
    signed_gap: record.signedNeedAvailabilityGap,
    distortion_index: record.distortionIndex,
  }))
  const editorial = await loadAssetJson(env, origin, '/need-availability-distortions.json')
  return {
    ...paginateLocal(rows, query),
    sourceUpdatedAt: editorial.meta?.as_of || null,
    upstream: { url: '/need-availability-distortions.json', status: 200 },
    warnings: [editorial.meta?.comparability_guardrail].filter(Boolean),
  }
}

async function localCareTeams(dataset, query, env, origin) {
  const payload = await loadAssetJson(env, origin, '/need-availability-care-teams.json')
  const rows = (payload.groups || []).flatMap((group) => (group.roles || []).map((role) => ({
    field: group.name,
    mapping_strength: group.mapping_strength,
    occupation: role.title,
    soc: role.soc,
    jobs_2025: role.jobs,
    annual_openings_2025_2035: role.annual_openings,
    source_url: role.source_url,
    field_scope_note: group.scope_note,
  })))
  return {
    ...paginateLocal(rows, query),
    sourceUpdatedAt: payload.meta?.as_of || null,
    upstream: { url: '/need-availability-care-teams.json', status: 200 },
    warnings: [payload.meta?.index_policy, payload.meta?.remaining_gap].filter(Boolean),
  }
}

export {
  localMetaIndex,
  localMedicalScienceFieldAtlas,
  localSystems,
  localStrategyFields,
  localDistortions,
  localCareTeams,
}
