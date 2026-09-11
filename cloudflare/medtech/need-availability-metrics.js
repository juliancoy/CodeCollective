export const DISTORTION_METHOD = Object.freeze({
  normalizationFloor: 20,
  normalizationCeiling: 100,
  pressureWeight: 0.8,
  renewalWeight: 0.2,
  availabilityWorkforceWeight: 0.8,
  availabilityPipelineWeight: 0.2,
})

function assertFinitePositive(value, label) {
  if (!Number.isFinite(value) || value <= 0) {
    throw new TypeError(`${label} must be a finite positive number`)
  }
}

function logNormalize(values, floor = DISTORTION_METHOD.normalizationFloor, ceiling = DISTORTION_METHOD.normalizationCeiling) {
  if (!Array.isArray(values) || values.length === 0) return []
  values.forEach((value, index) => assertFinitePositive(value, `values[${index}]`))
  const logs = values.map((value) => Math.log10(value))
  const min = Math.min(...logs)
  const max = Math.max(...logs)
  if (min === max) return values.map(() => (floor + ceiling) / 2)
  return logs.map((value) => floor + (ceiling - floor) * ((value - min) / (max - min)))
}

function round(value, digits = 1) {
  const factor = 10 ** digits
  return Math.round(value * factor) / factor
}

export function calculateNeedAvailabilityMetrics(fields) {
  if (!Array.isArray(fields) || fields.length < 2) {
    throw new TypeError('At least two field records are required')
  }

  const ids = new Set()
  for (const field of fields) {
    if (!field?.id || ids.has(field.id)) throw new TypeError('Field ids must be present and unique')
    ids.add(field.id)
    assertFinitePositive(field.need?.value, `${field.id}.need.value`)
    assertFinitePositive(field.workforce?.value, `${field.id}.workforce.value`)
    assertFinitePositive(field.pipeline?.value, `${field.id}.pipeline.value`)
  }

  const needScores = logNormalize(fields.map((field) => field.need.value))
  const workforceScores = logNormalize(fields.map((field) => field.workforce.value))
  const pipelineScores = logNormalize(fields.map((field) => field.pipeline.value))
  const peoplePerSpecialist = fields.map((field) => field.need.value / field.workforce.value)
  const renewalYears = fields.map((field) => field.workforce.value / field.pipeline.value)
  const pressureScores = logNormalize(peoplePerSpecialist)
  const renewalFragilityScores = logNormalize(renewalYears)

  const records = fields.map((field, index) => {
    const availabilityScore = (
      DISTORTION_METHOD.availabilityWorkforceWeight * workforceScores[index]
      + DISTORTION_METHOD.availabilityPipelineWeight * pipelineScores[index]
    )
    const distortionIndex = (
      DISTORTION_METHOD.pressureWeight * pressureScores[index]
      + DISTORTION_METHOD.renewalWeight * renewalFragilityScores[index]
    )

    return {
      id: field.id,
      name: field.name,
      field,
      needScore: round(needScores[index]),
      workforceScore: round(workforceScores[index]),
      pipelineScore: round(pipelineScores[index]),
      availabilityScore: round(availabilityScore),
      signedNeedAvailabilityGap: round(needScores[index] - availabilityScore),
      peoplePerSpecialist: round(peoplePerSpecialist[index], 0),
      entrantsPerThousandSpecialists: round((field.pipeline.value / field.workforce.value) * 1000),
      renewalYears: round(renewalYears[index]),
      coveragePressureScore: round(pressureScores[index]),
      renewalFragilityScore: round(renewalFragilityScores[index]),
      distortionIndex: round(distortionIndex),
    }
  })

  records.sort((left, right) => right.distortionIndex - left.distortionIndex || left.name.localeCompare(right.name))
  records.forEach((record, index) => { record.rank = index + 1 })

  return {
    method: DISTORTION_METHOD,
    records,
    leader: records[0],
  }
}
