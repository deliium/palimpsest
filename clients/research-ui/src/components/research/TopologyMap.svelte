<script lang="ts">
  import type { TopologyEdge, TopologyNode } from '../../research/spatial'

  interface Props {
    title: string
    nodes: TopologyNode[]
    edges: TopologyEdge[]
    onNodeSelect?: (id: string) => void
    emptyMessage?: string
  }

  let {
    title,
    nodes,
    edges,
    onNodeSelect,
    emptyMessage = 'No topology rows in this window.',
  }: Props = $props()

  const positions = $derived.by(() => {
    const ordered = [...nodes].sort((left, right) => left.id.localeCompare(right.id))
    const columns = Math.max(1, Math.ceil(Math.sqrt(ordered.length)))
    const rows = Math.max(1, Math.ceil(ordered.length / columns))
    const width = 720
    const height = Math.max(120, rows * 70)
    const map = new Map<string, { x: number; y: number }>()
    ordered.forEach((node, index) => {
      const column = index % columns
      const row = Math.floor(index / columns)
      map.set(node.id, {
        x: 50 + (column + 0.5) * ((width - 100) / columns),
        y: 40 + (row + 0.5) * ((height - 80) / rows),
      })
    })
    return { map, width, height }
  })
</script>

<figure class="topology">
  <figcaption>{title}</figcaption>
  {#if nodes.length === 0}
    <p class="empty">{emptyMessage}</p>
  {:else}
    <svg viewBox={`0 0 ${positions.width} ${positions.height}`} role="img" aria-label={title}>
      {#each edges as edge (edge.id)}
        {@const source = positions.map.get(edge.source)}
        {@const target = positions.map.get(edge.target)}
        {#if source !== undefined && target !== undefined}
          <line
            x1={source.x}
            y1={source.y}
            x2={target.x}
            y2={target.y}
            class="edge"
            stroke-dasharray={edge.evidenceClass === 'analytical' ? '5 3' : undefined}
          />
          <text
            x={(source.x + target.x) / 2}
            y={(source.y + target.y) / 2 - 4}
            text-anchor="middle"
            class="edge-label"
          >
            {edge.label}
          </text>
        {/if}
      {/each}
      {#each nodes as node (node.id)}
        {@const position = positions.map.get(node.id)}
        {#if position !== undefined}
          <circle
            cx={position.x}
            cy={position.y}
            r="12"
            class:region={node.kind === 'region'}
            class:hub={node.kind === 'hub'}
          />
          <text x={position.x} y={position.y + 26} text-anchor="middle" class="node-label">
            {node.label}
          </text>
        {/if}
      {/each}
    </svg>
    <ul class="accessible" aria-label={`${title} nodes`}>
      {#each nodes as node (node.id)}
        <li>
          <button type="button" onclick={() => onNodeSelect?.(node.id)}>
            {node.label}
            <span class="muted">({node.kind})</span>
          </button>
        </li>
      {/each}
    </ul>
  {/if}
</figure>

<style>
  .topology {
    margin: 0;
    display: grid;
    gap: 0.4rem;
  }

  figcaption {
    font-weight: 600;
  }

  svg {
    width: 100%;
    height: auto;
    background: rgba(255, 255, 255, 0.35);
  }

  .edge {
    stroke: #8a6a3a;
    stroke-width: 1.5;
  }

  .edge-label,
  .node-label {
    font-size: 0.65rem;
    fill: #3a474e;
  }

  circle {
    fill: #2e5c6e;
  }

  circle.region {
    fill: #6a5420;
  }

  circle.hub {
    fill: #6a3050;
  }

  .accessible {
    display: flex;
    flex-wrap: wrap;
    gap: 0.3rem;
    margin: 0;
    padding: 0;
    list-style: none;
    font-size: 0.8rem;
  }

  .accessible button {
    font: inherit;
    cursor: pointer;
  }

  .muted,
  .empty {
    color: #5a6a72;
    font-size: 0.8rem;
  }
</style>
