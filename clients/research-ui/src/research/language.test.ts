import { describe, expect, it } from 'vitest'
import { currentMetadataCard, semanticTimeline } from './language'

function history(overrides: Record<string, unknown> = {}) {
  return {
    schema_version: 'observer-semantic-history-v1',
    run_id: 'run-1',
    agent_id: 'agent-a',
    source: 'label',
    requested_tick: null,
    checkpoint_tick: 9,
    history_first_tick: 1,
    history_last_tick: 5,
    retained_only: true,
    prefix_complete: false,
    availability: 'available',
    reason: null,
    terms: [],
    rows: [
      {
        ordinal: 3,
        tick: 1,
        trigger: 'promoted',
        term_source: 'label',
        term_digest: 'term-a',
        local_id: 'binding-1',
        referent_kind: 'entity',
        referent_digest: 'ref-a',
        associated_digests: [],
        confidence: 0.4,
      },
      {
        ordinal: 4,
        tick: 5,
        trigger: 'shifted',
        term_source: 'label',
        term_digest: 'term-a',
        local_id: 'binding-1',
        referent_kind: 'entity',
        referent_digest: 'ref-b',
        associated_digests: [],
        confidence: 0.7,
      },
      {
        ordinal: 0,
        tick: 1,
        trigger: 'merged',
        term_source: 'label',
        term_digest: 'term-a',
        local_id: 'binding-2',
        referent_kind: 'entity',
        referent_digest: 'ref-c',
        associated_digests: [],
        confidence: null,
      },
    ],
    next_cursor: null,
    count: 3,
    ...overrides,
  }
}

describe('semantic history adapters', () => {
  it('groups by owner/source/local id/term and keeps multiple meanings separate', () => {
    const timeline = semanticTimeline(history())
    expect(timeline.checkpointTick).toBe(9)
    expect(timeline.retainedOnly).toBe(true)
    expect(timeline.prefixComplete).toBe(false)
    expect(timeline.groups).toHaveLength(2)
    expect(timeline.groups[0]?.rows[0]?.ordinal).toBe(3)
  })

  it('derives retained transitions but not a new drift score', () => {
    const timeline = semanticTimeline(history())
    expect(timeline.transitions).toHaveLength(1)
    expect(timeline.transitions[0]).toMatchObject({
      fromTick: 1,
      toTick: 5,
      changed: true,
      trigger: 'shifted',
      confidence: 0.7,
    })
  })

  it('keeps composition history separate and marks current metadata as-of', () => {
    const timeline = semanticTimeline(
      history({ source: 'composition', rows: [] }),
    )
    expect(timeline.source).toBe('composition')
    expect(timeline.groups).toEqual([])
    expect(
      currentMetadataCard({ agent_id: 'agent-a', count: 2 }, 'labels', 'current'),
    ).toEqual({
      layer: 'labels',
      ownerId: 'agent-a',
      count: 2,
      asOf: 'current_checkpoint',
      note: 'current',
    })
  })
})
