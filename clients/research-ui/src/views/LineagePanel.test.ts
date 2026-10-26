import { afterEach, describe, expect, it, vi } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { emptyResearchSelection } from '../research/selection'
import { flushSync, render } from '../test/mount'
import LineagePanel from './LineagePanel.svelte'

vi.mock('cytoscape', () => ({
  default: () => ({ on: () => undefined, destroy: () => undefined }),
}))

const fixtureRoot = resolve(
  process.cwd(),
  '../godot-observer/fixtures/protocol/generational',
)
const calls: string[] = []

function fixture(name: string): unknown {
  return JSON.parse(readFileSync(resolve(fixtureRoot, `${name}.json`), 'utf8'))
}

function graphFixture(): Record<string, unknown> {
  const raw = fixture('lineage_graph') as Record<string, unknown>
  const nodes = raw.nodes as Array<Record<string, unknown>>
  return {
    ...raw,
    root: nodes[0]?.ref,
    stop_reasons: [],
    effective_max_depth: 4,
    effective_max_nodes: 200,
    effective_max_edges: 500,
  }
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
  await Promise.resolve()
  flushSync()
}

afterEach(() => {
  vi.unstubAllGlobals()
  calls.length = 0
})

function installFetch(): void {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      calls.push(url)
      if (url.includes('/observer/run')) {
        return json({
          run_id: 'run-generational-23',
          world_id: 'world-1',
          tick: 16,
          latest_tick: 16,
          latest_sequence: 1,
          parent_run_id: null,
          fork_tick: null,
          intervention_summary: null,
          branch_id: null,
          protocol_version: 'observer-protocol-v1',
        })
      }
      if (url.includes('/lineage/families')) {
        return json(fixture('lineage_families'))
      }
      if (url.includes('/snapshots')) {
        return json(fixture('lineage_snapshots'))
      }
      if (url.includes('/nodes')) {
        return json(fixture('lineage_nodes'))
      }
      if (url.includes('/traverse')) {
        return json(graphFixture())
      }
      return json({}, 404)
    }),
  )
}

describe('lineage panel', () => {
  it('discovers roots from the pinned publication and traverses qualified keys', async () => {
    installFetch()
    const mounted = render(LineagePanel as never, {
      runId: 'run-generational-23',
      selection: emptyResearchSelection({
        runId: 'run-generational-23',
        view: 'lineage',
        tick: 16,
      }),
      onSelectionChange: vi.fn(),
    })
    await settle()
    await settle()
    expect(mounted.target.textContent).toContain('Root candidates at the pinned publication')
    expect(mounted.target.textContent).toContain('agent-founder')
    expect(mounted.target.textContent).toContain('context-only')

    const rootRow = [...mounted.target.querySelectorAll('tbody tr')].find((row) =>
      row.textContent?.includes('agent-founder'),
    )
    rootRow?.dispatchEvent(new MouseEvent('click', { bubbles: true }))
    await settle()
    expect(mounted.target.textContent).toContain('snapshot publication-2026-10-24-01')
    expect(
      mounted.target.querySelectorAll('.accessible-nodes button').length,
    ).toBeGreaterThan(0)

    const nodeCalls = calls.filter((url) => url.includes('/nodes'))
    expect(nodeCalls.length).toBeGreaterThan(0)
    for (const url of nodeCalls) {
      expect(url).not.toContain('publication_id')
      expect(url).not.toContain('identity_owner')
    }
    mounted.cleanup()
  })

  it('rejects prefix-only selection without silently seeking', async () => {
    installFetch()
    const mounted = render(LineagePanel as never, {
      runId: 'run-generational-23',
      selection: emptyResearchSelection({
        runId: 'run-generational-23',
        view: 'lineage',
        tick: 5,
        sequence: 2,
      }),
      onSelectionChange: vi.fn(),
    })
    await settle()
    expect(mounted.target.textContent).toContain('prefix_cursor_requires_full_boundary')
    expect(calls).toEqual([])
    mounted.cleanup()
  })
})
