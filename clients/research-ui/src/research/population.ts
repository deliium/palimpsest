/** Adapters from demographic envelopes to bounded chart/table data. */

import type {
  ChartSeries,
  SeriesPoint,
} from '../components/research/SeriesChart.svelte'
import type { DemographicsEnvelope } from '../api/researchSchemas'
import type { GenerationMarker } from './generationTypes'

export type { GenerationMarker }

export type BoundarySample = {
  tick: number
  envelope: DemographicsEnvelope | null
  reasonCode?: string | null
}

export function resolveGeneration(
  markers: readonly GenerationMarker[],
  generationIndex: number,
): GenerationMarker | null {
  return (
    markers.find((marker) => marker.generation_index === generationIndex) ?? null
  )
}

export function generationTickMismatch(
  markers: readonly GenerationMarker[],
  generationIndex: number | null,
  tick: number | null,
): boolean {
  if (generationIndex === null || tick === null) {
    return false
  }
  const marker = resolveGeneration(markers, generationIndex)
  return marker !== null && marker.seek_tick !== tick
}

export function markersInRange(
  markers: readonly GenerationMarker[],
  fromTick: number,
  toTick: number,
): GenerationMarker[] {
  const from = Math.min(fromTick, toTick)
  const to = Math.max(fromTick, toTick)
  return markers
    .filter((marker) => marker.seek_tick >= from && marker.seek_tick <= to)
    .sort((left, right) => left.seek_tick - right.seek_tick)
}

export function populationSeries(samples: readonly BoundarySample[]): ChartSeries[] {
  const ordered = [...samples].sort((left, right) => left.tick - right.tick)
  const make = (key: 'admitted' | 'living' | 'dead', label: string): ChartSeries => ({
    id: key,
    label,
    evidenceClass: 'objective_world',
    ownerId: null,
    unit: 'agents',
    coverage: null,
    sourceRef: 'observer-demographics-v1',
    points: ordered.map<SeriesPoint>((sample) => ({
      tick: sample.tick,
      value: sample.envelope?.population?.[key] ?? null,
    })),
  })
  return [make('admitted', 'Admitted'), make('living', 'Living'), make('dead', 'Dead')]
}

export type StageBar = {
  stage: string
  lifeStatus: 'alive' | 'dead'
  count: number
}

export function stageBars(envelope: DemographicsEnvelope | null): StageBar[] {
  return (
    envelope?.stage_rows.map((row) => ({
      stage: row.stage,
      lifeStatus: row.life_status,
      count: row.count,
    })) ?? []
  )
}

export type GenerationBar = {
  generationIndex: number
  admitted: number
  living: number
  dead: number
}

export function generationBars(
  envelope: DemographicsEnvelope | null,
): GenerationBar[] {
  return (
    envelope?.generations.map((row) => ({
      generationIndex: row.generation_index,
      admitted: row.admitted,
      living: row.living,
      dead: row.dead,
    })) ?? []
  )
}

export function demographicNotice(
  envelope: DemographicsEnvelope | null,
  reasonCode?: string | null,
): {
  status: 'available' | 'empty' | 'unavailable' | 'partial'
  reason: string | null
} {
  if (envelope === null) {
    return { status: 'unavailable', reason: reasonCode ?? 'demographics_unavailable' }
  }
  if (envelope.availability === 'unavailable') {
    return { status: 'unavailable', reason: envelope.reason_code }
  }
  if (
    envelope.population !== null &&
    envelope.population.admitted === 0 &&
    envelope.population.living === 0 &&
    envelope.population.dead === 0
  ) {
    return { status: 'empty', reason: 'known_zero_population' }
  }
  if (envelope.stage_counts_truncated) {
    return { status: 'partial', reason: 'stage_counts_truncated' }
  }
  return { status: 'available', reason: null }
}
