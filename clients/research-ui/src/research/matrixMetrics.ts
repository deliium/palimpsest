/** Matrix metric adapters: store selectors, never calculate new science. */

import { decodeRowsJson } from './json'
import { isRecord, requireArray, requireRecord, requireString } from '../api/researchSchemas'

export type MetricFacet = {
  cellId: string | null
  family: string
  measurementId: string
  dimension: string | null
  representation: string | null
  scope: string | null
  partitionId: string | null
  populationBasis: string | null
  denominatorCode: string | null
  units: string | null
  baselineTick: number | null
  endTick: number | null
  value: number | null
  meanDifference: number | null
  n: number | null
  rawCellCount: number | null
  duplicateCellCount: number | null
  ciLow: number | null
  ciHigh: number | null
  df: number | null
  inferenceStatus: string | null
  availability: string | null
  method: string | null
  confidence: number | null
  sharedStreamStatus: string | null
  channelAlignment: string | null
  excluded: number | null
  contrastId: string | null
  controlConditionId: string | null
  treatmentConditionId: string | null
  selectorsComplete: boolean
}

function num(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

function int(value: unknown): number | null {
  return typeof value === 'number' && Number.isSafeInteger(value) ? value : null
}

function str(value: unknown): string | null {
  return typeof value === 'string' && value !== '' ? value : null
}

function baseFacet(cellId: string | null, family: string): MetricFacet {
  return {
    cellId,
    family,
    measurementId: '',
    dimension: null,
    representation: null,
    scope: null,
    partitionId: null,
    populationBasis: null,
    denominatorCode: null,
    units: null,
    baselineTick: null,
    endTick: null,
    value: null,
    meanDifference: null,
    n: null,
    rawCellCount: null,
    duplicateCellCount: null,
    ciLow: null,
    ciHigh: null,
    df: null,
    inferenceStatus: null,
    availability: null,
    method: null,
    confidence: null,
    sharedStreamStatus: null,
    channelAlignment: null,
    excluded: null,
    contrastId: null,
    controlConditionId: null,
    treatmentConditionId: null,
    selectorsComplete: false,
  }
}

function selectorFields(
  measurement: Record<string, unknown>,
  facet: MetricFacet,
): MetricFacet {
  facet.measurementId =
    str(measurement.measurement_id) ?? str(measurement.row_id) ?? facet.measurementId
  facet.dimension = str(measurement.dimension)
  facet.representation = str(measurement.representation)
  facet.scope = str(measurement.scope)
  facet.partitionId = str(measurement.partition_id)
  facet.populationBasis = str(measurement.population_basis)
  facet.denominatorCode = str(measurement.denominator_code)
  facet.units = str(measurement.units)
  facet.baselineTick = int(measurement.baseline_tick)
  facet.endTick = int(measurement.end_tick)
  facet.selectorsComplete =
    facet.measurementId !== '' &&
    facet.dimension !== null &&
    facet.representation !== null &&
    facet.scope !== null &&
    facet.populationBasis !== null &&
    facet.denominatorCode !== null &&
    facet.baselineTick !== null &&
    facet.endTick !== null
  return facet
}

export function metricDocuments(payload: unknown): Record<string, unknown>[] {
  if (Array.isArray(payload)) {
    return payload.filter(isRecord)
  }
  if (isRecord(payload) && Array.isArray(payload.documents)) {
    return payload.documents.filter(isRecord)
  }
  return []
}

export function scalarMetricFacets(
  cellId: string | null,
  payload: unknown,
): MetricFacet[] {
  const facets: MetricFacet[] = []
  for (const document of metricDocuments(payload)) {
    const family = str(document.metric_family) ?? 'unknown'
    const values = isRecord(document.values) ? document.values : {}
    const rowsRaw = values.rows_json
    if (typeof rowsRaw === 'string') {
      for (const row of decodeRowsJson(rowsRaw)) {
        const facet = selectorFields(row, baseFacet(cellId, family))
        facet.value = num(row.value)
        facet.n = int(row.coverage_observed)
        facet.availability = str(row.availability)
        facet.units = str(row.units) ?? facet.units
        facets.push(facet)
      }
      continue
    }
    for (const [key, value] of Object.entries(values)) {
      if (typeof value !== 'number' || !Number.isFinite(value)) {
        continue
      }
      const facet = baseFacet(cellId, family)
      facet.measurementId = key
      facet.value = value
      facet.availability = str(document.availability)
      facets.push(facet)
    }
  }
  return facets
}

export function culturalComparisonFacets(
  cellId: string | null,
  payload: unknown,
): MetricFacet[] {
  if (!isRecord(payload)) {
    return []
  }
  const facets: MetricFacet[] = []
  for (const condition of requireArray(payload.conditions)) {
    const conditionRow = requireRecord(condition)
    const conditionId = str(conditionRow.condition_id) ?? ''
    for (const item of requireArray(conditionRow.measurements)) {
      const row = requireRecord(item)
      const measurement = requireRecord(row.measurement)
      const facet = selectorFields(
        measurement,
        baseFacet(cellId, str(measurement.family) ?? 'unknown'),
      )
      facet.value = num(row.mean)
      facet.n = int(row.n)
      facet.rawCellCount = int(row.raw_cell_count)
      facet.duplicateCellCount = int(row.duplicate_cell_count)
      facet.ciLow = num(row.ci_low)
      facet.ciHigh = num(row.ci_high)
      facet.df = int(row.df)
      facet.inferenceStatus = str(row.inference_status)
      facet.method = str(row.method)
      facet.confidence = num(row.confidence)
      facet.availability = str(row.inference_status)
      facet.contrastId = conditionId
      facets.push(facet)
    }
  }
  for (const contrast of requireArray(payload.contrasts)) {
    const row = requireRecord(contrast)
    const measurement = requireRecord(row.measurement)
    const facet = selectorFields(
      measurement,
      baseFacet(cellId, str(measurement.family) ?? 'unknown'),
    )
    facet.contrastId = str(row.contrast_id)
    facet.controlConditionId = str(row.control_condition_id)
    facet.treatmentConditionId = str(row.treatment_condition_id)
    facet.meanDifference = num(row.mean_difference)
    facet.n = int(row.n)
    facet.ciLow = num(row.ci_low)
    facet.ciHigh = num(row.ci_high)
    facet.df = int(row.df)
    facet.inferenceStatus = str(row.inference_status)
    facet.method = str(row.method)
    facet.confidence = num(row.confidence)
    facet.sharedStreamStatus = str(row.shared_stream_status)
    const alignment = row.channel_alignment
    facet.channelAlignment = Array.isArray(alignment)
      ? JSON.stringify(alignment)
      : null
    facet.excluded = int(row.excluded_pairs)
    facets.push(facet)
  }
  return facets
}

export function intervalUsable(facet: MetricFacet): boolean {
  return (
    facet.ciLow !== null &&
    facet.ciHigh !== null &&
    facet.inferenceStatus === 'present'
  )
}

export function facetLabel(facet: MetricFacet): string {
  return [
    facet.family,
    facet.measurementId,
    facet.dimension,
    facet.representation,
    facet.scope,
    facet.partitionId,
  ]
    .filter((value): value is string => value !== null && value !== '')
    .join(' · ')
}

export function incompatibleSelectors(
  facets: readonly MetricFacet[],
): Array<[string, string]> {
  const groups = new Map<string, MetricFacet>()
  const conflicts: Array<[string, string]> = []
  for (const facet of facets) {
    if (!facet.selectorsComplete) {
      continue
    }
    const key = `${facet.family}\u0000${facet.measurementId}`
    const previous = groups.get(key)
    if (previous === undefined) {
      groups.set(key, facet)
      continue
    }
    const selector = (item: MetricFacet) =>
      `${item.dimension}|${item.representation}|${item.scope}|${item.partitionId}|${item.populationBasis}|${item.denominatorCode}|${item.baselineTick}|${item.endTick}|${item.units}`
    if (selector(previous) !== selector(facet)) {
      conflicts.push([previous.family, previous.measurementId])
    }
  }
  return conflicts
}
