import { afterEach, describe, expect, it, vi } from 'vitest'
import { emptyResearchSelection } from '../research/selection'
import { flushSync, render } from '../test/mount'
import PopulationPanel from './PopulationPanel.svelte'

const calls: string[] = []

function envelope(tick: number, overrides: Record<string, unknown> = {}) {
  return {
    schema_version: 'observer-demographics-v1',
    run_id: 'run-1',
    requested_tick: tick,
    requested_through_sequence: null,
    resolved_tick: tick,
    revision: 3,
    evidence_class: 'objective',
    availability: 'available',
    reason_code: null,
    section: 'generations',
    selection_state: 'all',
    population: { living: tick === 10 ? 2 : 3, admitted: 5, dead: 1, max_generation_index: 2 },
    stage_counts_truncated: false,
    stage_rows: [{ stage: 'adult', life_status: 'alive', count: 3 }],
    agents: [],
    cohorts: [],
    generations: [{ generation_index: 0, admitted: 5, living: 3, dead: 1 }],
    next_after_agent_id: null,
    next_after_group_key: null,
    limit: 100,
    ...overrides,
  }
}

function installFetch() {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      calls.push(url)
      const parsed = new URL(url, 'http://localhost')
      if (url.includes('/observer/run')) {
        return json({
          run_id: 'run-1',
          world_id: 'world-1',
          tick: 20,
          latest_tick: 40,
          latest_sequence: 1,
          parent_run_id: null,
          fork_tick: null,
          intervention_summary: null,
          branch_id: null,
          protocol_version: 'observer-protocol-v1',
        })
      }
      if (url.includes('/observer/generation-markers')) {
        return json({
          schema_version: 'observer-generation-markers-v1',
          run_id: 'run-1',
          requested_tick: Number(parsed.searchParams.get('tick')),
          resolved_tick: Number(parsed.searchParams.get('tick')),
          revision: 3,
          evidence_class: 'objective',
          availability: 'available',
          reason_code: null,
          markers: [
            { generation_index: 0, first_entry_tick: 0, seek_tick: 0, admitted_count: 5, label_code: 'founders' },
            { generation_index: 1, first_entry_tick: 10, seek_tick: 10, admitted_count: 2, label_code: 'generation_first_admission' },
            { generation_index: 2, first_entry_tick: 20, seek_tick: 20, admitted_count: 2, label_code: 'generation_first_admission' },
          ],
          next_after_generation_index: null,
          limit: 100,
        })
      }
      if (url.includes('/observer/demographics')) {
        const section = parsed.searchParams.get('section')
        const tick = Number(parsed.searchParams.get('tick'))
        if (section === 'agents') {
          const after = parsed.searchParams.get('after_agent_id')
          return json(
            envelope(tick, {
              section: 'agents',
              agents: after === null
                ? [
                    {
                      agent_id: 'agent-a',
                      entity_id: 'entity-a',
                      entry_tick: 0,
                      generation_index: 0,
                      cohort_id: 'cohort-a',
                      stage: 'adult',
                      dependency_status: 'independent',
                      life_status: 'alive',
                      age_ticks: 10,
                    },
                  ]
                : [
                    {
                      agent_id: 'agent-b',
                      entity_id: 'entity-b',
                      entry_tick: 10,
                      generation_index: 1,
                      cohort_id: 'cohort-b',
                      stage: 'adult',
                      dependency_status: 'independent',
                      life_status: 'dead',
                      age_ticks: null,
                    },
                  ],
              next_after_agent_id: after === null ? 'agent-a' : null,
            }),
          )
        }
        if (section === 'cohorts') {
          return json(envelope(tick, { section: 'cohorts' }))
        }
        return json(envelope(tick))
      }
      return json({}, 404)
    }),
  )
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  })
}

async function settle(): Promise<void> {
  await Promise.resolve()
  await new Promise((resolve) => setTimeout(resolve, 0))
  await Promise.resolve()
  flushSync()
}

afterEach(() => {
  vi.unstubAllGlobals()
  calls.length = 0
})

describe('population panel', () => {
  it('shows totals, stages, generations and keeps totals after appending agent pages', async () => {
    installFetch()
    const mounted = render(PopulationPanel as never, {
      runId: 'run-1',
      selection: emptyResearchSelection({
        runId: 'run-1',
        view: 'population',
        tick: 10,
        generationIndex: 1,
      }),
      onSelectionChange: vi.fn(),
    })
    await settle()
    expect(mounted.target.textContent).toContain('Population timeline')
    expect(mounted.target.textContent).toContain('Living')
    expect(mounted.target.textContent).toContain('adult')
    expect(mounted.target.textContent).toContain('Generation distribution')
    expect(mounted.target.textContent).toContain('40')

    const loadAgents = [...mounted.target.querySelectorAll('button')].find((button) =>
      button.textContent?.includes('Load agent page'),
    )
    loadAgents?.click()
    await settle()
    expect(mounted.target.textContent).toContain('agent-a')
    const before = mounted.target.textContent
    const more = [...mounted.target.querySelectorAll('button')].find((button) =>
      button.textContent?.includes('Load more agents'),
    )
    more?.click()
    await settle()
    expect(mounted.target.textContent).toContain('agent-b')
    expect(mounted.target.textContent).toContain('Dead age is unknown')
    expect(mounted.target.textContent).toContain('Living')
    expect(before).toContain('Living')
    mounted.cleanup()
  })

  it('uses marker high water for discovery while view tick changes', async () => {
    installFetch()
    const onSelectionChange = vi.fn()
    const mounted = render(PopulationPanel as never, {
      runId: 'run-1',
      selection: emptyResearchSelection({
        runId: 'run-1',
        view: 'population',
        tick: 10,
        generationIndex: 1,
      }),
      onSelectionChange,
    })
    await settle()
    const markerCalls = calls.filter((url) => url.includes('generation-markers'))
    expect(markerCalls.length).toBeGreaterThan(0)
    for (const url of markerCalls) {
      expect(url).toContain('tick=40')
    }
    const next = [...mounted.target.querySelectorAll('button')].find((button) =>
      button.textContent?.includes('Next'),
    )
    next?.click()
    flushSync()
    expect(onSelectionChange).toHaveBeenCalledWith(
      expect.objectContaining({ tick: 20, generationIndex: 2 }),
    )
    mounted.cleanup()
  })

  it('distinguishes lifecycle-disabled from zero', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input)
        if (url.includes('/observer/run')) {
          return json({
            run_id: 'run-1',
            world_id: 'world-1',
            tick: 0,
            latest_tick: 0,
            latest_sequence: null,
            parent_run_id: null,
            fork_tick: null,
            intervention_summary: null,
            branch_id: null,
            protocol_version: 'observer-protocol-v1',
          })
        }
        if (url.includes('generation-markers')) {
          return json({
            schema_version: 'observer-generation-markers-v1',
            run_id: 'run-1',
            requested_tick: 0,
            resolved_tick: 0,
            revision: 1,
            evidence_class: 'objective',
            availability: 'unavailable',
            reason_code: 'lifecycle_disabled',
            markers: [],
            next_after_generation_index: null,
            limit: 100,
          })
        }
        return json(
          envelope(0, {
            availability: 'unavailable',
            reason_code: 'lifecycle_disabled',
            population: null,
            stage_rows: [],
            generations: [],
          }),
        )
      }),
    )
    const mounted = render(PopulationPanel as never, {
      runId: 'run-1',
      selection: emptyResearchSelection({ runId: 'run-1', view: 'population', tick: 0 }),
      onSelectionChange: vi.fn(),
    })
    await settle()
    expect(mounted.target.textContent).toContain('Evidence unavailable')
    expect(mounted.target.textContent).toContain('lifecycle_disabled')
    mounted.cleanup()
  })
})
