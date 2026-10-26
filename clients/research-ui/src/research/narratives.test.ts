import { describe, expect, it } from 'vitest'
import { narrativeSummary } from './narratives'

describe('narrative metadata summaries', () => {
  it('counts roots, branches, merges, carriers and source-linked variants', () => {
    const summary = narrativeSummary({
      agent_id: 'agent-a',
      variants: [
        {
          variant_id: 'v1',
          parent_variant_ids: [],
          carrier_agent_ids: ['a', 'b'],
          merged_into_id: null,
          source_event_id: 'evt-1',
        },
        {
          variant_id: 'v2',
          parent_variant_ids: ['v0', 'v1'],
          carrier_agent_ids: ['b'],
          merged_into_id: 'v3',
          source_event_id: null,
        },
      ],
    })
    expect(summary).toMatchObject({
      ownerId: 'agent-a',
      count: 2,
      roots: 1,
      branches: 1,
      merges: 1,
      sourceLinked: 1,
      carriers: 2,
    })
  })
})
