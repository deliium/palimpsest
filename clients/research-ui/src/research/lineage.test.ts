import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import type { LineageGraph, LineageNodePage } from '../api/researchSchemas'
import {
  detectCycle,
  matchQualifiedRef,
  mergeGraphPages,
  refLabel,
  sameSnapshot,
  toGraphElements,
} from './lineage'

const fixtures = resolve(
  process.cwd(),
  '../godot-observer/fixtures/protocol/generational',
)

function fixture(name: string): unknown {
  return JSON.parse(readFileSync(resolve(fixtures, `${name}.json`), 'utf8'))
}

function graph(): LineageGraph {
  const raw = fixture('lineage_graph') as Record<string, unknown>
  return {
    ...(raw as unknown as LineageGraph),
    root: (raw.nodes as LineageGraph['nodes'])[0]!.ref,
    stop_reasons: [],
    effective_max_depth: 4,
    effective_max_nodes: 200,
    effective_max_edges: 500,
  }
}

describe('qualified lineage adapters', () => {
  it('builds graph ids from returned qualified keys and labels context-only nodes', () => {
    const value = graph()
    const elements = toGraphElements(value)
    const nodes = elements.filter((item) => item.group === 'nodes')
    expect(nodes[0]?.data?.id).toBe(value.nodes[0]?.ref.key)
    expect(nodes.some((item) => item.classes?.includes('context_only'))).toBe(true)
    expect(refLabel(value.nodes[0]!.ref)).toContain('agent:')
  })

  it('merges only the same publication and keeps matched/context keys', () => {
    const first = graph()
    const second = { ...graph(), nodes: [], edges: [] }
    const merged = mergeGraphPages(first, second)
    expect(merged.nodes).toHaveLength(first.nodes.length)
    expect(() =>
      mergeGraphPages(first, {
        ...second,
        snapshot: { ...first.snapshot, digest: 'f'.repeat(64) },
      }),
    ).toThrow('research_snapshot_changed')
    expect(sameSnapshot(first.snapshot, second.snapshot)).toBe(true)
  })

  it('detects returned cycles without removing edges', () => {
    const value = graph()
    value.edges = [
      ...value.edges,
      {
        ...value.edges[0]!,
        edge_key: 'e'.repeat(64),
        source_key: value.edges[0]!.target_key,
        target_key: value.edges[0]!.source_key,
      },
    ]
    expect(detectCycle(value)).toBe(true)
  })

  it('matches the complete qualified identity, never a bare native ID', () => {
    const page = fixture('lineage_nodes') as LineageNodePage
    page.items = [
      ...page.items,
      {
        ...page.items[0]!,
        ref: {
          ...page.items[0]!.ref,
          identity_owner: 'agent-other',
          key: '1'.repeat(64),
        },
      },
    ]
    expect(
      matchQualifiedRef(page, {
        family: 'genealogy',
        evidenceClass: 'objective',
        nativeKind: 'agent',
        nativeId: page.items[0]!.ref.native_id,
      }),
    ).toBeNull()
    expect(
      matchQualifiedRef(page, {
        family: 'genealogy',
        evidenceClass: 'objective',
        nativeKind: 'agent',
        nativeId: page.items[0]!.ref.native_id,
        identityOwner: 'agent-other',
        nodeKey: '1'.repeat(64),
      })?.key,
    ).toBe('1'.repeat(64))
  })

  it('capabilities expose restricted families only when returned', () => {
    const families = fixture('lineage_families') as Array<{
      family: string
      available_classes: string[]
    }>
    expect(
      families.find((item) => item.family === 'genealogy')?.available_classes,
    ).toEqual(['objective'])
    expect(
      families.find((item) => item.family === 'mentorship')?.available_classes,
    ).toContain('analytical')
  })
})
