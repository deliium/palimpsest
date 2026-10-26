import { describe, expect, it } from 'vitest'
import { culturalSeries, summarizeCulturalPage, vocabularyRows } from './culture'

function page(overrides: Record<string, unknown> = {}) {
  return {
    schema_version: 'research-cultural-evidence-page-v1',
    run_id: 'run-1',
    matrix_id: 'm1',
    cell_id: 'cell-a',
    section: 'traits',
    artifact_digest: 'a'.repeat(64),
    source_revision: 'rev-1',
    binding_state: 'runtime_bound',
    requested_window: { from_tick: 0, to_tick: 10 },
    capture_status: { active: true, failed: false },
    gaps: [],
    rows: [
      { boundary_tick: 0, owner_id: 'a', dimension: 'belief', content_digest: 'x' },
      { boundary_tick: 0, owner_id: 'b', dimension: 'belief', content_digest: 'y' },
      { boundary_tick: 5, owner_id: 'a', dimension: 'belief', content_digest: 'x' },
      { boundary_tick: 0, owner_id: 'a', dimension: 'vocabulary', content_digest: 'v1' },
      { boundary_tick: 0, owner_id: 'b', dimension: 'vocabulary', content_digest: 'v2' },
    ],
    next_cursor: null,
    truncated: false,
    coverage: 1,
    ...overrides,
  }
}

describe('cultural inventory summaries', () => {
  it('keeps dimensions separate with exact carrier and distinct counts', () => {
    const summary = summarizeCulturalPage(page())
    expect(summary.dimensions.map((item) => item.dimension)).toEqual([
      'belief',
      'vocabulary',
    ])
    const belief = summary.dimensions[0]!
    expect(belief.points[0]).toMatchObject({
      tick: 0,
      carrierOwners: 2,
      distinctForms: 2,
    })
    expect(belief.points[1]).toMatchObject({
      tick: 5,
      carrierOwners: 1,
      distinctForms: 1,
    })
    expect(summary.partial).toBe(false)
  })

  it('marks truncated pages partial and never claims a complete total', () => {
    const summary = summarizeCulturalPage(page({ truncated: true }))
    expect(summary.partial).toBe(true)
    expect(summary.dimensions[0]?.partial).toBe(true)
    expect(summary.dimensions[0]?.points[0]?.complete).toBe(false)
  })

  it('keeps gaps and legacy binding visible', () => {
    const summary = summarizeCulturalPage(
      page({ binding_state: 'legacy_unverified', gaps: [{ tick: 3 }] }),
    )
    expect(summary.binding).toBe('legacy_unverified')
    expect(summary.gaps).toHaveLength(1)
  })

  it('builds descriptive series and vocabulary rows without new metrics', () => {
    const summary = summarizeCulturalPage(page())
    const series = culturalSeries(summary, 'carrierOwners')
    expect(series.map((item) => item.id)).toContain('belief:carrierOwners')
    expect(series[0]?.evidenceClass).toBe('research_inference')
    expect(vocabularyRows(summary)).toHaveLength(1)
  })

  it('does not treat unjoinable opaque digests as equal labels', () => {
    const summary = summarizeCulturalPage(
      page({ rows: [
        { boundary_tick: 0, owner_id: 'a', dimension: 'vocabulary', content_digest: 'digest-a' },
        { boundary_tick: 0, owner_id: 'b', dimension: 'vocabulary', content_digest: 'digest-b' },
      ] }),
    )
    expect(summary.dimensions[0]?.points[0]?.distinctForms).toBe(2)
  })
})
