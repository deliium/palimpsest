import { describe, expect, it, vi } from 'vitest'

vi.mock('cytoscape', () => ({
  default: () => ({ on: () => undefined, destroy: () => undefined }),
}))
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { flushSync, render } from '../test/mount'
import type { LineageGraph } from '../api/researchSchemas'
import LineageGraphView from './LineageGraph.svelte'

function fixtureGraph(): LineageGraph {
  const raw = JSON.parse(
    readFileSync(
      resolve(
        process.cwd(),
        '../godot-observer/fixtures/protocol/generational/lineage_graph.json',
      ),
      'utf8',
    ),
  ) as Record<string, unknown>
  const nodes = raw.nodes as LineageGraph['nodes']
  return {
    ...(raw as unknown as LineageGraph),
    root: nodes[0]!.ref,
    stop_reasons: [],
    effective_max_depth: 4,
    effective_max_nodes: 200,
    effective_max_edges: 500,
  }
}

describe('lineage graph', () => {
  it('exposes keyboard-selectable qualified nodes and inspector', () => {
    const onNodeSelect = vi.fn()
    const mounted = render(LineageGraphView as never, {
      graph: fixtureGraph(),
      family: 'genealogy',
      onNodeSelect,
    })
    const buttons = mounted.target.querySelectorAll('.accessible-nodes button')
    expect(buttons.length).toBeGreaterThan(0)
    buttons[0]?.dispatchEvent(new MouseEvent('click', { bubbles: true }))
    flushSync()
    expect(onNodeSelect).toHaveBeenCalled()
    expect(
      mounted.target.querySelector('[aria-label="Qualified lineage node inspector"]'),
    ).not.toBeNull()
    expect(mounted.target.textContent).toContain('Identity owner')
    mounted.cleanup()
  })

  it('surfaces a cycle with a fallback layout without removing edges', () => {
    const graph = fixtureGraph()
    graph.edges = [
      ...graph.edges,
      {
        ...graph.edges[0]!,
        edge_key: 'e'.repeat(64),
        source_key: graph.edges[0]!.target_key,
        target_key: graph.edges[0]!.source_key,
      },
    ]
    const mounted = render(LineageGraphView as never, {
      graph,
      family: 'genealogy',
    })
    expect(mounted.target.textContent).toContain('Cycle detected')
    mounted.cleanup()
  })
})
