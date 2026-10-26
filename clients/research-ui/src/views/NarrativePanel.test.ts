import { afterEach, describe, expect, it, vi } from 'vitest'
import { emptyResearchSelection } from '../research/selection'
import { flushSync, render } from '../test/mount'
import NarrativePanel from './NarrativePanel.svelte'

vi.mock('cytoscape', () => ({ default: () => ({ on: () => undefined, destroy: () => undefined }) }))

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } })
}

async function settle(): Promise<void> {
  await Promise.resolve()
  await new Promise((resolve) => setTimeout(resolve, 0))
  await Promise.resolve()
  flushSync()
}

afterEach(() => vi.unstubAllGlobals())

describe('narrative panel', () => {
  it('shows metadata-only roots/branches/merges and separates objective records', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input)
        if (url.includes('/narrative-hops')) {
          return json({
            run_id: 'run-1',
            owner_id: 'agent-a',
            layer: 'subjective_narrative_hops',
            count: 2,
            variants: [
              { variant_id: 'v1', status: 'active', origin: 'witness', carrier_agent_ids: ['a'], location_ids: [], parent_variant_ids: [], merged_into_id: null, transmission_root_id: 'r1', source_event_id: 'evt-1', last_communication_id: null, strength_band: 'mid' },
              { variant_id: 'v2', status: 'merged', origin: 'retelling', carrier_agent_ids: ['b'], location_ids: [], parent_variant_ids: ['v0', 'v1'], merged_into_id: 'v3', transmission_root_id: 'r1', source_event_id: null, last_communication_id: null, strength_band: 'low' },
            ],
          })
        }
        if (url.includes('/lineage/families')) return json([])
        if (url.includes('/observer/run')) {
          return json({ run_id: 'run-1', world_id: 'w', tick: 9, latest_tick: 9, latest_sequence: null, parent_run_id: null, fork_tick: null, intervention_summary: null, branch_id: null, protocol_version: 'observer-protocol-v1' })
        }
        return json({}, 404)
      }),
    )
    const mounted = render(NarrativePanel as never, {
      runId: 'run-1',
      selection: emptyResearchSelection({ runId: 'run-1', view: 'narratives', tick: 9, scopeOwnerId: 'agent-a' }),
      onSelectionChange: vi.fn(),
    })
    await settle()
    const load = [...mounted.target.querySelectorAll('button')].find((item) =>
      item.textContent?.includes('Load current narrative metadata'),
    )
    load?.click()
    await settle()
    expect(mounted.target.textContent).toContain('Roots')
    expect(mounted.target.textContent).toContain('Branches')
    expect(mounted.target.textContent).toContain('Merges')
    expect(mounted.target.textContent).toContain('restored history')
    mounted.cleanup()
  })
})
