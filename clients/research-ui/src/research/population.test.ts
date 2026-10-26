import { describe, expect, it } from 'vitest'
import type { DemographicsEnvelope } from '../api/researchSchemas'
import {
  demographicNotice,
  generationBars,
  generationTickMismatch,
  markersInRange,
  populationSeries,
  resolveGeneration,
  stageBars,
} from './population'

function envelope(overrides: Partial<DemographicsEnvelope> = {}): DemographicsEnvelope {
  return {
    schema_version: 'observer-demographics-v1',
    run_id: 'run-1',
    requested_tick: 10,
    requested_through_sequence: null,
    resolved_tick: 10,
    revision: 1,
    evidence_class: 'objective',
    availability: 'available',
    reason_code: null,
    section: 'generations',
    selection_state: 'all',
    population: { living: 3, admitted: 4, dead: 1, max_generation_index: 1 },
    stage_counts_truncated: false,
    stage_rows: [{ stage: 'adult', life_status: 'alive', count: 3 }],
    agents: [],
    cohorts: [],
    generations: [{ generation_index: 0, admitted: 4, living: 3, dead: 1 }],
    next_after_agent_id: null,
    next_after_group_key: null,
    limit: 100,
    ...overrides,
  }
}

describe('population adapters', () => {
  it('uses exact totals and never sums repeated pages', () => {
    const first = envelope()
    const second = envelope({ agents: [], population: { ...first.population! } })
    const series = populationSeries([
      { tick: 10, envelope: first },
      { tick: 20, envelope: second },
    ])
    expect(series.map((item) => item.label)).toEqual([
      'Admitted',
      'Living',
      'Dead',
    ])
    expect(series[0]?.points.map((point) => point.value)).toEqual([4, 4])
    expect(series[1]?.points.map((point) => point.value)).toEqual([3, 3])
  })

  it('keeps unknown ticks as chart gaps instead of zero', () => {
    const series = populationSeries([
      { tick: 0, envelope: envelope() },
      { tick: 10, envelope: null, reasonCode: 'replay_unavailable' },
    ])
    expect(series[0]?.points[1]?.value).toBeNull()
  })

  it('maps stages, generations and truncated notices', () => {
    expect(stageBars(envelope())[0]).toEqual({
      stage: 'adult',
      lifeStatus: 'alive',
      count: 3,
    })
    expect(generationBars(envelope())[0]?.generationIndex).toBe(0)
    expect(demographicNotice(envelope({ stage_counts_truncated: true }))).toEqual({
      status: 'partial',
      reason: 'stage_counts_truncated',
    })
  })

  it('distinguishes lifecycle-disabled from known zero', () => {
    expect(
      demographicNotice(
        envelope({ availability: 'unavailable', reason_code: 'lifecycle_disabled' }),
      ),
    ).toEqual({ status: 'unavailable', reason: 'lifecycle_disabled' })
    expect(
      demographicNotice(
        envelope({
          population: { living: 0, admitted: 0, dead: 0, max_generation_index: 0 },
        }),
      ),
    ).toEqual({ status: 'empty', reason: 'known_zero_population' })
  })

  it('resolves actual admission markers without schedule arithmetic', () => {
    const markers = [
      {
        generation_index: 0,
        first_entry_tick: 0,
        seek_tick: 0,
        admitted_count: 5,
        label_code: 'founders' as const,
      },
      {
        generation_index: 2,
        first_entry_tick: 44,
        seek_tick: 45,
        admitted_count: 2,
        label_code: 'generation_first_admission' as const,
      },
    ]
    expect(resolveGeneration(markers, 2)?.seek_tick).toBe(45)
    expect(generationTickMismatch(markers, 2, 40)).toBe(true)
    expect(generationTickMismatch(markers, 2, 45)).toBe(false)
    expect(markersInRange(markers, 0, 45).map((item) => item.generation_index)).toEqual([
      0,
      2,
    ])
  })
})
