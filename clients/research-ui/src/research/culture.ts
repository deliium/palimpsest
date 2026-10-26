/** Descriptive cultural inventory adapters. No new metric families. */

import type { ChartSeries } from '../components/research/SeriesChart.svelte'

export type CulturalTraitPoint = {
  tick: number
  carrierOwners: number
  distinctForms: number
  complete: boolean
}

export type CulturalDimensionSeries = {
  dimension: string
  points: CulturalTraitPoint[]
  coverage: number | null
  partial: boolean
}

export type CulturalPageSummary = {
  runId: string
  matrixId: string
  cellId: string
  binding: string
  artifactDigest: string
  dimensions: CulturalDimensionSeries[]
  requestedWindow: { from_tick: number | null; to_tick: number | null }
  captureStatus: Record<string, unknown>
  gaps: unknown[]
  partial: boolean
}

function value(record: Record<string, unknown>, key: string): unknown {
  return record[key]
}

function tickOf(row: Record<string, unknown>): number | null {
  const raw = value(row, 'boundary_tick')
  return typeof raw === 'number' && Number.isSafeInteger(raw) && raw >= 0
    ? raw
    : null
}

export function summarizeCulturalPage(
  page: Record<string, unknown>,
): CulturalPageSummary {
  const rows = Array.isArray(page.rows)
    ? page.rows.filter(
        (row): row is Record<string, unknown> =>
          row !== null && typeof row === 'object' && !Array.isArray(row),
      )
    : []
  const byDimension = new Map<
    string,
    Map<number, { owners: Set<string>; forms: Set<string> }>
  >()
  for (const row of rows) {
    const dimension = value(row, 'dimension')
    const tick = tickOf(row)
    const owner = value(row, 'owner_id')
    const digest = value(row, 'content_digest')
    if (
      typeof dimension !== 'string' ||
      dimension === '' ||
      tick === null ||
      typeof owner !== 'string'
    ) {
      continue
    }
    const byTick = byDimension.get(dimension) ?? new Map()
    const state = byTick.get(tick) ?? { owners: new Set<string>(), forms: new Set<string>() }
    state.owners.add(owner)
    if (typeof digest === 'string' && digest !== '') {
      state.forms.add(digest)
    }
    byTick.set(tick, state)
    byDimension.set(dimension, byTick)
  }
  const coverageRaw = value(page, 'coverage')
  const coverage =
    typeof coverageRaw === 'number' && Number.isFinite(coverageRaw)
      ? coverageRaw
      : null
  const truncated = page.truncated === true
  const partial = truncated || (coverage !== null && coverage < 1)
  const requestedWindowRaw = value(page, 'requested_window')
  const requestedWindow =
    requestedWindowRaw !== null && typeof requestedWindowRaw === 'object'
      ? {
          from_tick:
            typeof (requestedWindowRaw as Record<string, unknown>).from_tick ===
            'number'
              ? Number(
                  (requestedWindowRaw as Record<string, unknown>).from_tick,
                )
              : null,
          to_tick:
            typeof (requestedWindowRaw as Record<string, unknown>).to_tick ===
            'number'
              ? Number((requestedWindowRaw as Record<string, unknown>).to_tick)
              : null,
        }
      : { from_tick: null, to_tick: null }
  return {
    runId: String(value(page, 'run_id') ?? ''),
    matrixId: String(value(page, 'matrix_id') ?? ''),
    cellId: String(value(page, 'cell_id') ?? ''),
    binding: String(value(page, 'binding_state') ?? ''),
    artifactDigest: String(value(page, 'artifact_digest') ?? ''),
    dimensions: [...byDimension.entries()]
      .map(([dimension, ticks]) => ({
        dimension,
        points: [...ticks.entries()]
          .map(([tick, state]) => ({
            tick,
            carrierOwners: state.owners.size,
            distinctForms: state.forms.size,
            complete: !partial,
          }))
          .sort((left, right) => left.tick - right.tick),
        coverage,
        partial,
      }))
      .sort((left, right) => left.dimension.localeCompare(right.dimension)),
    requestedWindow,
    captureStatus:
      page.capture_status !== null && typeof page.capture_status === 'object'
        ? (page.capture_status as Record<string, unknown>)
        : {},
    gaps: Array.isArray(page.gaps) ? page.gaps : [],
    partial,
  }
}

export function culturalSeries(
  summary: CulturalPageSummary,
  measure: 'carrierOwners' | 'distinctForms',
): ChartSeries[] {
  return summary.dimensions.map((dimension) => ({
    id: `${dimension.dimension}:${measure}`,
    label: `${dimension.dimension} · ${measure === 'carrierOwners' ? 'carriers' : 'distinct forms'}`,
    evidenceClass: 'research_inference',
    ownerId: null,
    unit: 'owners',
    coverage: dimension.coverage,
    sourceRef: `${summary.binding}:${summary.artifactDigest.slice(0, 12)}`,
    points: dimension.points.map((point) => ({
      tick: point.tick,
      value: point[measure],
    })),
  }))
}

export type VocabularyRow = {
  ownerId: string
  dimension: string
  tick: number
  distinctForms: number
  contentDigests: string[]
  complete: boolean
}

export function vocabularyRows(summary: CulturalPageSummary): VocabularyRow[] {
  const rows = summary.dimensions.filter(
    (dimension) => dimension.dimension === 'vocabulary',
  )
  return rows.flatMap((dimension) =>
    dimension.points.map((point) => ({
      ownerId: 'aggregate',
      dimension: dimension.dimension,
      tick: point.tick,
      distinctForms: point.distinctForms,
      contentDigests: [],
      complete: point.complete,
    })),
  )
}
