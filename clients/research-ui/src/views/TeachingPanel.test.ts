import { afterEach, describe, expect, it, vi } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { emptyResearchSelection } from '../research/selection'
import { flushSync, render } from '../test/mount'
import TeachingPanel from './TeachingPanel.svelte'

vi.mock('cytoscape', () => ({
  default: () => ({ on: () => undefined, destroy: () => undefined }),
}))

const root = resolve(
  process.cwd(),
  '../godot-observer/fixtures/protocol/generational',
)

function fixture(name: string): unknown {
  return JSON.parse(readFileSync(resolve(root, `${name}.json`), 'utf8'))
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
})

describe('teaching panel', () => {
  it('separates attempted teaching from learning evidence and loads the graph', async () => {
    const graph = fixture('lineage_graph') as Record<string, unknown>
    const nodes = graph.nodes as Array<Record<string, unknown>>
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input)
        if (url.includes('/participants')) {
          return json(fixture('lineage_participants'))
        }
        if (url.includes('/traverse')) {
          return json({
            ...graph,
            root: nodes[0]?.ref,
            stop_reasons: [],
            effective_max_depth: 4,
            effective_max_nodes: 200,
            effective_max_edges: 500,
          })
        }
        return json({}, 404)
      }),
    )
    const mounted = render(TeachingPanel as never, {
      runId: 'run-generational-23',
      selection: emptyResearchSelection({
        runId: 'run-generational-23',
        view: 'teaching',
        tick: 16,
        scopeOwnerId: 'agent-founder',
      }),
      onSelectionChange: vi.fn(),
    })
    await settle()
    const input = mounted.target.querySelectorAll('input')[1]
    if (input !== undefined) {
      input.value = 'agent-child'
      input.dispatchEvent(new Event('input', { bubbles: true }))
    }
    const load = [...mounted.target.querySelectorAll('button')].find((button) =>
      button.textContent?.includes('Load evidence'),
    )
    load?.click()
    await settle()
    expect(mounted.target.textContent).toContain('agent-founder')
    expect(mounted.target.textContent).toContain('agent-child')
    expect(mounted.target.textContent).toContain('2')
    expect(mounted.target.textContent).toContain('learning_evidence')
    expect(mounted.target.textContent).toContain('content content-1')

    const network = [...mounted.target.querySelectorAll('button')].find((button) =>
      button.textContent?.includes('Load mentorship graph'),
    )
    network?.click()
    await settle()
    expect(
      mounted.target.querySelectorAll('.accessible-nodes button').length,
    ).toBeGreaterThan(0)
    mounted.cleanup()
  })
})
