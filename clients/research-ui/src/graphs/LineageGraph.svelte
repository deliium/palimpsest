<script lang="ts">
  import { onDestroy, onMount } from 'svelte'
  import ResearchGraph from './ResearchGraph.svelte'
  import type { LineageGraph } from '../api/researchSchemas'
  import {
    detectCycle,
    lineageEpistemic,
    nodeEpistemic,
    toGraphElements,
  } from '../research/lineage'

  interface Props {
    graph: LineageGraph
    family: string
    onNodeSelect?: (key: string) => void
    onEdgeSelect?: (key: string) => void
  }

  let { graph, family, onNodeSelect, onEdgeSelect }: Props = $props()

  let selectedNodeKey = $state<string | null>(null)
  let selectedEdgeKey = $state<string | null>(null)

  const cycle = $derived(detectCycle(graph))
  const layout = $derived(
    cycle ? 'cose' : family === 'genealogy' || family === 'knowledge' ? 'breadthfirst' : 'cose',
  )
  const elements = $derived(toGraphElements(graph))
  const node = $derived(
    graph.nodes.find((item) => item.ref.key === selectedNodeKey) ?? null,
  )
  const edge = $derived(
    graph.edges.find((item) => item.edge_key === selectedEdgeKey) ?? null,
  )

  function selectNode(key: string): void {
    selectedNodeKey = key
    selectedEdgeKey = null
    onNodeSelect?.(key)
  }

  function selectEdge(key: string): void {
    selectedEdgeKey = key
    selectedNodeKey = null
    onEdgeSelect?.(key)
  }

  onMount(() => {
    // Graph instance is owned by ResearchGraph and destroyed there.
  })

  onDestroy(() => {
    selectedNodeKey = null
    selectedEdgeKey = null
  })
</script>

<section class="lineage-graph">
  <ResearchGraph
    title={`${family} graph · ${graph.snapshot.boundary_tick}`}
    epistemic={lineageEpistemic(graph.root.evidence_class)}
    {elements}
    {layout}
    onNodeSelect={selectNode}
    onEdgeSelect={selectEdge}
    emptyMessage="No lineage nodes at the pinned publication."
  />

  <p class="meta">
    snapshot {graph.snapshot.publication_id} · digest {graph.snapshot.digest.slice(0, 12)}… ·
    matched {graph.matched_node_keys.length} · context-only
    {graph.context_only_node_keys.length} · stops {graph.stop_reasons.join(', ') || 'none'}
  </p>
  {#if cycle}
    <p class="warning" role="status">
      Cycle detected in returned edges. Rendering with the fallback layout; no
      edge was removed.
    </p>
  {/if}

  {#if node !== null}
    <aside aria-label="Qualified lineage node inspector">
      <h3>{node.ref.native_kind}:{node.ref.native_id}</h3>
      <dl>
        <div><dt>Family</dt><dd>{node.ref.family}</dd></div>
        <div><dt>Evidence</dt><dd>{node.ref.evidence_class}</dd></div>
        <div><dt>Identity owner</dt><dd>{node.ref.identity_owner ?? '—'}</dd></div>
        <div><dt>Key</dt><dd>{node.ref.key.slice(0, 16)}…</dd></div>
        <div><dt>State</dt><dd>{node.state}</dd></div>
        <div><dt>Observed tick</dt><dd>{node.observed_tick ?? '—'}</dd></div>
        <div><dt>Living</dt><dd>{node.living === null ? 'unknown' : node.living ? 'yes' : 'no'}</dd></div>
      </dl>
      <p class="muted">
        Matched: {graph.matched_node_keys.includes(node.ref.key) ? 'yes' : 'context-only'}
      </p>
      {#if node.evidence_refs.length > 0}
        <ul class="evidence">
          {#each node.evidence_refs as ref, index (index)}
            <li>{JSON.stringify(ref)}</li>
          {/each}
        </ul>
      {/if}
    </aside>
  {:else if edge !== null}
    <aside aria-label="Qualified lineage edge inspector">
      <h3>{edge.relation}</h3>
      <dl>
        <div><dt>Native kind</dt><dd>{edge.native_kind}</dd></div>
        <div><dt>Native ID</dt><dd>{edge.native_id}</dd></div>
        <div><dt>Claim owner</dt><dd>{edge.claim_owner_id ?? '—'}</dd></div>
        <div><dt>Source presence</dt><dd>{edge.source_presence}</dd></div>
        <div><dt>Observed tick</dt><dd>{edge.observed_tick ?? '—'}</dd></div>
      </dl>
    </aside>
  {/if}

  {#if graph.edges.length > 0}
    <ul class="edges" aria-label="Qualified lineage edges">
      {#each graph.edges.slice(0, 20) as item (item.edge_key)}
        <li>
          <span class="relation">{item.relation}</span>
          {item.native_id} · {item.source_presence}
        </li>
      {/each}
    </ul>
  {/if}

  <p class="muted">
    Coverage: {JSON.stringify(graph.coverage)}
  </p>
</section>

<style>
  .lineage-graph {
    display: grid;
    gap: 0.5rem;
  }

  .meta,
  .muted {
    margin: 0;
    color: #5a6a72;
    font-size: 0.8rem;
  }

  .warning {
    margin: 0;
    color: #6a5420;
    font-size: 0.85rem;
  }

  aside {
    border: 1px solid rgba(28, 36, 40, 0.15);
    padding: 0.5rem 0.7rem;
    background: rgba(255, 255, 255, 0.45);
  }

  h3 {
    margin: 0 0 0.3rem;
    font-size: 0.95rem;
  }

  dl {
    display: grid;
    gap: 0.2rem;
    margin: 0;
  }

  dl div {
    display: grid;
    grid-template-columns: 8rem 1fr;
    gap: 0.4rem;
  }

  dt {
    color: #5a6a72;
  }

  dd {
    margin: 0;
    word-break: break-all;
  }

  .evidence {
    margin: 0.3rem 0 0;
    padding-left: 1rem;
    font-size: 0.75rem;
  }

  .edges {
    margin: 0;
    padding-left: 1rem;
    font-size: 0.75rem;
    display: grid;
    gap: 0.15rem;
  }

  .edges .relation {
    font-weight: 600;
  }
</style>
