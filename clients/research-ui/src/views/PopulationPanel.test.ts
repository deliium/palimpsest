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

function agentRow(agentId: string, generation: number, lifeStatus: string) {
  return {
    agent_id: agentId,
    entity_id: `entity-${agentId}`,
    entry_tick: generation * 10,
    generation_index: generation,
    cohort_id: `cohort-${generation}`,
    stage: 'adult',
    dependency_status: 'independent',
    life_status: lifeStatus,
    age_ticks: lifeStatus === 'dead' ? null : 10,
  }
}

function cohortRow(generation: number, dead: number) {
  return {
    generation_index: generation,
    entry_tick: generation * 10,
    cohort_id: `cohort-${generation}`,
    admitted: 3,
    living: 3 - dead,
    dead,
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

  it('continues marker discovery past 25 pages only through explicit continuation', async () => {
    let markerCalls = 0
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input)
        const parsed = new URL(url, 'http://localhost')
        if (url.includes('/observer/run')) {
          return json({
            run_id: 'run-1',
            world_id: 'world-1',
            tick: 1000,
            latest_tick: 1000,
            latest_sequence: 1,
            parent_run_id: null,
            fork_tick: null,
            intervention_summary: null,
            branch_id: null,
            protocol_version: 'observer-protocol-v1',
          })
        }
        if (url.includes('/observer/generation-markers')) {
          markerCalls += 1
          const raw = parsed.searchParams.get('after_generation_index')
          const index = raw === null ? 0 : Number(raw)
          return json({
            schema_version: 'observer-generation-markers-v1',
            run_id: 'run-1',
            requested_tick: 1000,
            resolved_tick: 1000,
            revision: 5,
            evidence_class: 'objective',
            availability: 'available',
            reason_code: null,
            markers: [
              {
                generation_index: index,
                first_entry_tick: index * 10,
                seek_tick: index * 10,
                admitted_count: 1,
                label_code: index === 0 ? 'founders' : 'generation_first_admission',
              },
            ],
            next_after_generation_index: index < 25 ? index + 1 : null,
            limit: 200,
          })
        }
        if (url.includes('/observer/demographics')) {
          return json(envelope(1000))
        }
        return json({}, 404)
      }),
    )
    const mounted = render(PopulationPanel as never, {
      runId: 'run-1',
      selection: emptyResearchSelection({
        runId: 'run-1',
        view: 'population',
        tick: 1000,
      }),
      onSelectionChange: vi.fn(),
    })
    await settle()
    expect(markerCalls).toBe(1)
    expect(mounted.target.textContent).toContain('Generation 0')
    expect(mounted.target.textContent).not.toContain('Generation 25')
    expect(mounted.target.textContent).toContain('Discovery is incomplete')
    for (let index = 0; index < 25; index += 1) {
      const more = [...mounted.target.querySelectorAll('button')].find((button) =>
        button.textContent?.includes('Load more generations'),
      )
      expect(more).toBeDefined()
      more?.click()
      await settle()
    }
    expect(markerCalls).toBe(26)
    expect(mounted.target.textContent).toContain('Generation 25')
    expect(mounted.target.textContent).not.toContain('Discovery is incomplete')
    mounted.cleanup()
  })

  it('refreshes the head before advancing marker high water', async () => {
    let latest = 40
    const markerTicks: number[] = []
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input)
        const parsed = new URL(url, 'http://localhost')
        if (url.includes('/observer/run')) {
          return json({
            run_id: 'run-1',
            world_id: 'world-1',
            tick: 20,
            latest_tick: latest,
            latest_sequence: 1,
            parent_run_id: null,
            fork_tick: null,
            intervention_summary: null,
            branch_id: null,
            protocol_version: 'observer-protocol-v1',
          })
        }
        if (url.includes('/observer/generation-markers')) {
          markerTicks.push(Number(parsed.searchParams.get('tick')))
          return json({
            schema_version: 'observer-generation-markers-v1',
            run_id: 'run-1',
            requested_tick: Number(parsed.searchParams.get('tick')),
            resolved_tick: Number(parsed.searchParams.get('tick')),
            revision: 4,
            evidence_class: 'objective',
            availability: 'available',
            reason_code: null,
            markers: [
              {
                generation_index: 0,
                first_entry_tick: 0,
                seek_tick: 0,
                admitted_count: 5,
                label_code: 'founders',
              },
            ],
            next_after_generation_index: null,
            limit: 200,
          })
        }
        if (url.includes('/observer/demographics')) {
          return json(envelope(20))
        }
        return json({}, 404)
      }),
    )
    const mounted = render(PopulationPanel as never, {
      runId: 'run-1',
      selection: emptyResearchSelection({
        runId: 'run-1',
        view: 'population',
        tick: 20,
      }),
      onSelectionChange: vi.fn(),
    })
    await settle()
    expect(markerTicks[0]).toBe(40)
    latest = 80
    const refresh = [...mounted.target.querySelectorAll('button')].find((button) =>
      button.textContent?.includes('Refresh markers'),
    )
    refresh?.click()
    await settle()
    expect(markerTicks.at(-1)).toBe(80)
    expect(mounted.target.textContent).toContain('80')
    mounted.cleanup()
  })

  it('retains a long-dead cohort row across explicit agent continuations', async () => {
    const pages: Record<string, { agents: Array<Record<string, unknown>>; next: string | null }> = {
      start: {
        agents: [agentRow('agent-0', 0, 'alive')],
        next: 'after-0',
      },
      'after-0': {
        agents: [agentRow('agent-1', 1, 'alive')],
        next: 'after-1',
      },
      'after-1': {
        agents: [agentRow('agent-2', 2, 'alive')],
        next: 'after-2',
      },
      'after-2': {
        agents: [agentRow('agent-3', 3, 'dead')],
        next: null,
      },
    }
    const ticks: number[] = []
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input)
        const parsed = new URL(url, 'http://localhost')
        if (url.includes('/observer/run')) {
          return json({
            run_id: 'run-1',
            world_id: 'world-1',
            tick: 500,
            latest_tick: 500,
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
            requested_tick: 500,
            resolved_tick: 500,
            revision: 6,
            evidence_class: 'objective',
            availability: 'available',
            reason_code: null,
            markers: [],
            next_after_generation_index: null,
            limit: 200,
          })
        }
        if (url.includes('/observer/demographics')) {
          const section = parsed.searchParams.get('section')
          const tick = Number(parsed.searchParams.get('tick'))
          if (section === 'agents') {
            ticks.push(tick)
            const after = parsed.searchParams.get('after_agent_id') ?? 'start'
            const page = pages[after] ?? { agents: [], next: null }
            return json(
              envelope(tick, {
                section: 'agents',
                agents: page.agents,
                next_after_agent_id: page.next,
              }),
            )
          }
          return json(envelope(tick, { section }))
        }
        return json({}, 404)
      }),
    )
    const mounted = render(PopulationPanel as never, {
      runId: 'run-1',
      selection: emptyResearchSelection({
        runId: 'run-1',
        view: 'population',
        tick: 500,
      }),
      onSelectionChange: vi.fn(),
    })
    await settle()
    const first = [...mounted.target.querySelectorAll('button')].find((button) =>
      button.textContent?.includes('Load agent page'),
    )
    first?.click()
    await settle()
    expect(mounted.target.textContent).toContain('agent-0')
    for (let index = 0; index < 3; index += 1) {
      const more = [...mounted.target.querySelectorAll('button')].find((button) =>
        button.textContent?.includes('Load more agents'),
      )
      expect(more).toBeDefined()
      more?.click()
      await settle()
    }
    expect(mounted.target.textContent).toContain('agent-3')
    expect(mounted.target.textContent).toContain('agent-0')
    expect(mounted.target.textContent).toContain('dead')
    expect(ticks.every((tick) => tick === 500)).toBe(true)
    mounted.cleanup()
  })

  it('retains a long-dead cohort row across explicit cohort continuations', async () => {
    const pages: Record<string, { cohorts: Array<Record<string, unknown>>; next: string | null }> = {
      start: { cohorts: [cohortRow(0, 3)], next: 'c0' },
      c0: { cohorts: [cohortRow(1, 3)], next: 'c1' },
      c1: { cohorts: [cohortRow(2, 0)], next: null },
    }
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input)
        const parsed = new URL(url, 'http://localhost')
        if (url.includes('/observer/run')) {
          return json({
            run_id: 'run-1',
            world_id: 'world-1',
            tick: 700,
            latest_tick: 700,
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
            requested_tick: 700,
            resolved_tick: 700,
            revision: 8,
            evidence_class: 'objective',
            availability: 'available',
            reason_code: null,
            markers: [],
            next_after_generation_index: null,
            limit: 200,
          })
        }
        if (url.includes('/observer/demographics')) {
          const section = parsed.searchParams.get('section')
          const tick = Number(parsed.searchParams.get('tick'))
          if (section === 'cohorts') {
            const after = parsed.searchParams.get('after_group_key') ?? 'start'
            const page = pages[after] ?? { cohorts: [], next: null }
            return json(
              envelope(tick, {
                section: 'cohorts',
                cohorts: page.cohorts,
                next_after_group_key: page.next,
              }),
            )
          }
          return json(envelope(tick, { section }))
        }
        return json({}, 404)
      }),
    )
    const mounted = render(PopulationPanel as never, {
      runId: 'run-1',
      selection: emptyResearchSelection({
        runId: 'run-1',
        view: 'population',
        tick: 700,
      }),
      onSelectionChange: vi.fn(),
    })
    await settle()
    const first = [...mounted.target.querySelectorAll('button')].find((button) =>
      button.textContent?.includes('Load cohort page'),
    )
    first?.click()
    await settle()
    expect(mounted.target.textContent).toContain('cohort-0')
    for (let index = 0; index < 2; index += 1) {
      const more = [...mounted.target.querySelectorAll('button')].find((button) =>
        button.textContent?.includes('Load more cohorts'),
      )
      expect(more).toBeDefined()
      more?.click()
      await settle()
    }
    expect(mounted.target.textContent).toContain('cohort-2')
    expect(mounted.target.textContent).toContain('cohort-0')
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
