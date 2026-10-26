import { describe, expect, it } from 'vitest'
import type { DemographicsEnvelope } from '../api/researchSchemas'
import {
  cohortKey,
  cohortRows,
  compareCohorts,
  resolveCohortSelection,
  survivalShare,
} from './cohorts'

function envelope(overrides: Partial<DemographicsEnvelope> = {}): DemographicsEnvelope {
  return {
    schema_version: 'observer-demographics-v1',
    run_id: 'run-1',
    requested_tick: 50,
    requested_through_sequence: null,
    resolved_tick: 50,
    revision: 1,
    evidence_class: 'objective',
    availability: 'available',
    reason_code: null,
    section: 'cohorts',
    selection_state: 'all',
    population: null,
    stage_counts_truncated: false,
    stage_rows: [],
    agents: [],
    cohorts: [
      { generation_index: 2, entry_tick: 10, cohort_id: 'cohort-a', admitted: 4, living: 2, dead: 2 },
      { generation_index: 3, entry_tick: 50, cohort_id: 'cohort-a', admitted: 0, living: 0, dead: 0 },
      { generation_index: 2, entry_tick: 20, cohort_id: 'cohort-b', admitted: 2, living: 2, dead: 0 },
    ],
    generations: [],
    next_after_agent_id: null,
    next_after_group_key: null,
    limit: 100,
    ...overrides,
  }
}

describe('composite cohort identity', () => {
  it('keeps reused cohort IDs separate by generation and entry tick', () => {
    const rows = cohortRows('run-1', [envelope()])
    expect(rows).toHaveLength(3)
    const reused = rows.filter((row) => row.cohortId === 'cohort-a')
    expect(reused.map((row) => row.entryTick)).toEqual([10, 50])
    expect(
      cohortKey({ runId: 'run-1', generationIndex: 2, entryTick: 10, cohortId: 'cohort-a' }),
    ).not.toBe(
      cohortKey({ runId: 'run-1', generationIndex: 3, entryTick: 50, cohortId: 'cohort-a' }),
    )
  })

  it('resolves the exact composite tuple and never first-matches a reused ID', () => {
    const rows = cohortRows('run-1', [envelope()])
    const exact = resolveCohortSelection(rows, {
      cohortGenerationIndex: 3,
      cohortEntryTick: 50,
      cohortId: 'cohort-a',
    })
    expect(exact.kind).toBe('resolved')
    if (exact.kind === 'resolved') {
      expect(exact.row.generationIndex).toBe(3)
      expect(exact.row.entryTick).toBe(50)
    }
    expect(
      resolveCohortSelection(rows, { cohortId: 'cohort-a' }).kind,
    ).toBe('ambiguous')
    expect(
      resolveCohortSelection(rows, { cohortGenerationIndex: 2, cohortId: 'cohort-a' })
        .kind,
    ).toBe('incomplete')
  })

  it('returns null share for a zero denominator', () => {
    const rows = cohortRows('run-1', [envelope()])
    const zero = rows.find((row) => row.entryTick === 50)
    expect(zero).toBeDefined()
    if (zero !== undefined) {
      expect(survivalShare(zero)).toBeNull()
    }
  })

  it('keeps exposure and descriptive provenance visible', () => {
    const rows = cohortRows('run-1', [envelope()])
    const first = rows.find((row) => row.entryTick === 10)
    const zero = rows.find((row) => row.entryTick === 50)
    expect(first).toBeDefined()
    expect(zero).toBeDefined()
    const facets = compareCohorts(
      [first, zero].filter((row): row is NonNullable<typeof row> => row !== undefined),
    )
    expect(facets[0]?.exposureTicks).toBe(40)
    expect(facets[1]?.exposureTicks).toBe(0)
    expect(facets[0]?.provenance).toContain('not Kaplan–Meier')
  })
})
