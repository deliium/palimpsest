/** Shared display adapters for stored cultural/generational measurement rows. */

import {
  culturalComparisonFacets,
  facetLabel,
  intervalUsable,
  scalarMetricFacets,
  type MetricFacet,
} from './matrixMetrics'

export type MetricDisplayRow = {
  key: string
  family: string
  measurementId: string
  selectors: string
  value: string
  units: string | null
  availability: string | null
  coverage: string | null
  interval: string | null
  inferenceUsable: boolean
  status: string
  binding: string | null
}

export function adaptFacet(
  facet: MetricFacet,
  binding: string | null = null,
): MetricDisplayRow {
  return {
    key: [
      facet.cellId ?? 'matrix',
      facet.family,
      facet.measurementId,
      facet.dimension,
      facet.representation,
      facet.scope,
      facet.partitionId,
      facet.baselineTick,
      facet.endTick,
    ].join(':'),
    family: facet.family,
    measurementId: facet.measurementId,
    selectors: facetLabel(facet),
    value:
      facet.meanDifference !== null
        ? String(facet.meanDifference)
        : facet.value === null
          ? '—'
          : String(facet.value),
    units: facet.units,
    availability: facet.availability,
    coverage:
      facet.n !== null
        ? `n ${facet.n}`
        : facet.rawCellCount !== null
          ? `cells ${facet.rawCellCount}`
          : null,
    interval:
      facet.ciLow !== null && facet.ciHigh !== null
        ? `${facet.ciLow} … ${facet.ciHigh}`
        : null,
    inferenceUsable: intervalUsable(facet),
    status: facet.inferenceStatus ?? 'not_comparable',
    binding,
  }
}

export function adaptScalarMetrics(
  cellId: string | null,
  payload: unknown,
  binding: string | null = null,
): MetricDisplayRow[] {
  return scalarMetricFacets(cellId, payload).map((facet) =>
    adaptFacet(facet, binding),
  )
}

export function adaptCulturalComparison(
  payload: unknown,
  binding: string | null = null,
): MetricDisplayRow[] {
  return culturalComparisonFacets(null, payload).map((facet) =>
    adaptFacet(facet, binding),
  )
}

export function groupByFamily(
  rows: readonly MetricDisplayRow[],
): Map<string, MetricDisplayRow[]> {
  const result = new Map<string, MetricDisplayRow[]>()
  for (const row of rows) {
    const list = result.get(row.family) ?? []
    list.push(row)
    result.set(row.family, list)
  }
  return result
}
