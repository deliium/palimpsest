/** Qualified lineage graph adapters and presentation-only topology helpers. */

import type { ElementDefinition } from 'cytoscape'
import type { EpistemicClass } from '../epistemic'
import type {
  LineageFamilyDescriptor,
  LineageGraph,
  LineageNode,
  LineageNodePage,
  LineageNodeRef,
  LineageSnapshot,
  LineageSnapshotPage,
} from '../api/researchSchemas'

export const LINEAGE_FAMILIES = [
  'genealogy',
  'mentorship',
  'knowledge',
  'technology',
  'record',
  'narrative',
  'institution',
  'office_succession',
] as const

export type LineageFamily = (typeof LINEAGE_FAMILIES)[number]
export type LineageEvidenceClass = 'objective' | 'subjective' | 'analytical'

export const FAMILY_CLASSES: Record<
  LineageFamily,
  readonly LineageEvidenceClass[]
> = {
  genealogy: ['objective'],
  record: ['objective'],
  mentorship: ['subjective', 'analytical'],
  knowledge: ['subjective', 'analytical'],
  technology: ['subjective', 'analytical'],
  narrative: ['subjective', 'analytical'],
  institution: ['analytical'],
  office_succession: ['subjective'],
}

export function defaultEvidenceClass(family: LineageFamily): LineageEvidenceClass {
  return FAMILY_CLASSES[family][0] ?? 'objective'
}

export function familyRequiresOwner(
  family: LineageFamily,
  evidence: LineageEvidenceClass,
): boolean {
  return evidence === 'subjective'
}

export function lineageEpistemic(
  evidence: string,
): EpistemicClass {
  if (evidence === 'objective') {
    return 'objective_world'
  }
  if (evidence === 'subjective') {
    return 'agent_belief'
  }
  return 'research_inference'
}

export function refLabel(ref: LineageNodeRef): string {
  return `${ref.native_kind}:${ref.native_id}`
}

export function nodeEpistemic(node: LineageNode): EpistemicClass {
  return lineageEpistemic(node.ref.evidence_class)
}

export function toGraphElements(graph: LineageGraph): ElementDefinition[] {
  const nodes: ElementDefinition[] = graph.nodes.map((node) => ({
    group: 'nodes' as const,
    data: {
      id: node.ref.key,
      label: refLabel(node.ref),
      epistemic: lineageEpistemic(node.ref.evidence_class),
      status: node.state,
      owner: node.ref.identity_owner,
      className: node.ref.evidence_class,
    },
    classes: [
      lineageEpistemic(node.ref.evidence_class),
      node.state,
      graph.matched_node_keys.includes(node.ref.key)
        ? 'matched'
        : 'context_only',
    ].join(' '),
  }))
  const edges: ElementDefinition[] = graph.edges.map((edge) => ({
    group: 'edges' as const,
    data: {
      id: edge.edge_key,
      source: edge.source_key,
      target: edge.target_key,
      label: edge.relation,
      epistemic: lineageEpistemic(
        graph.nodes.find((node) => node.ref.key === edge.source_key)?.ref
          .evidence_class ?? 'analytical',
      ),
    },
    classes: 'lineage-edge',
  }))
  return [...nodes, ...edges]
}

export function detectCycle(graph: LineageGraph): boolean {
  const adjacency = new Map<string, string[]>()
  for (const edge of graph.edges) {
    const next = adjacency.get(edge.source_key) ?? []
    next.push(edge.target_key)
    adjacency.set(edge.source_key, next)
  }
  const visiting = new Set<string>()
  const visited = new Set<string>()
  const visit = (key: string): boolean => {
    if (visiting.has(key)) {
      return true
    }
    if (visited.has(key)) {
      return false
    }
    visiting.add(key)
    for (const next of adjacency.get(key) ?? []) {
      if (visit(next)) {
        return true
      }
    }
    visiting.delete(key)
    visited.add(key)
    return false
  }
  return [...adjacency.keys()].some(visit)
}

export function sameSnapshot(
  expected: LineageSnapshot,
  actual: LineageSnapshot,
): boolean {
  return (
    expected.publication_id === actual.publication_id &&
    expected.digest === actual.digest &&
    expected.boundary_tick === actual.boundary_tick
  )
}

export function validatePageSnapshot(
  expected: LineageSnapshot,
  page: { snapshot: LineageSnapshot },
): void {
  if (!sameSnapshot(expected, page.snapshot)) {
    throw new Error('research_snapshot_changed')
  }
}

export function mergeGraphPages(
  previous: LineageGraph | null,
  next: LineageGraph,
): LineageGraph {
  if (previous === null) {
    return next
  }
  if (!sameSnapshot(previous.snapshot, next.snapshot)) {
    throw new Error('research_snapshot_changed')
  }
  const nodes = new Map(previous.nodes.map((node) => [node.ref.key, node]))
  for (const node of next.nodes) {
    nodes.set(node.ref.key, node)
  }
  const edges = new Map(previous.edges.map((edge) => [edge.edge_key, edge]))
  for (const edge of next.edges) {
    edges.set(edge.edge_key, edge)
  }
  return {
    ...next,
    nodes: [...nodes.values()],
    edges: [...edges.values()],
  }
}

export function matchQualifiedRef(
  page: LineageNodePage,
  expected: {
    family: string
    evidenceClass: string
    nativeKind: string
    nativeId: string
    identityOwner?: string | null
    nodeKey?: string | null
  },
): LineageNodeRef | null {
  const matches = page.items.filter((item) => {
    const ref = item.ref
    return (
      ref.family === expected.family &&
      ref.evidence_class === expected.evidenceClass &&
      ref.native_kind === expected.nativeKind &&
      ref.native_id === expected.nativeId &&
      (expected.identityOwner === undefined ||
        expected.identityOwner === null ||
        ref.identity_owner === expected.identityOwner) &&
      (expected.nodeKey === undefined ||
        expected.nodeKey === null ||
        ref.key === expected.nodeKey)
    )
  })
  return matches.length === 1 ? (matches[0]?.ref ?? null) : null
}

export function capabilityFor(
  families: readonly LineageFamilyDescriptor[],
  family: string,
  evidence: string,
): LineageFamilyDescriptor | null {
  return (
    families.find(
      (item) =>
        item.family === family && item.available_classes.includes(evidence),
    ) ?? null
  )
}

export function snapshotsForFamily(
  page: LineageSnapshotPage,
): LineageSnapshot[] {
  return [...page.items]
}
