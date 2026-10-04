<script lang="ts">
  import { onDestroy, onMount } from 'svelte'
  import cytoscape, { type Core, type ElementDefinition } from 'cytoscape'
  import type { EpistemicClass } from '../epistemic'
  import EpistemicBadge from '../components/EpistemicBadge.svelte'

  interface Props {
    title: string
    epistemic: EpistemicClass
    elements: ElementDefinition[]
    emptyMessage?: string
  }

  let {
    title,
    epistemic,
    elements,
    emptyMessage = 'No graph nodes in the current window.',
  }: Props = $props()

  let host: HTMLDivElement | undefined = $state()
  let cy: Core | null = null

  function paint(next: ElementDefinition[]): void {
    if (host === undefined) {
      return
    }
    cy?.destroy()
    cy = cytoscape({
      container: host,
      elements: next,
      style: [
        {
          selector: 'node',
          style: {
            label: 'data(label)',
            'font-size': 10,
            'background-color': '#2e5c6e',
            color: '#1c2428',
            'text-valign': 'bottom',
            'text-margin-y': 6,
            width: 18,
            height: 18,
          },
        },
        {
          selector: 'edge',
          style: {
            width: 1.5,
            'line-color': '#8a6a3a',
            'target-arrow-color': '#8a6a3a',
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
          },
        },
      ],
      layout: { name: 'cose', animate: false },
    })
    if (import.meta.env.DEV) {
      console.debug(
        `research_ui_graph title=${title} nodes=${next.filter((e) => !('source' in (e.data ?? {}))).length}`,
      )
    }
  }

  onMount(() => {
    paint(elements)
  })

  $effect(() => {
    paint(elements)
  })

  onDestroy(() => {
    cy?.destroy()
    cy = null
  })
</script>

<article>
  <header>
    <h3>{title}</h3>
    <EpistemicBadge {epistemic} />
  </header>
  {#if elements.length === 0}
    <p class="empty">{emptyMessage}</p>
  {:else}
    <div class="canvas" bind:this={host}></div>
  {/if}
</article>

<style>
  article {
    display: grid;
    gap: 0.5rem;
  }

  header {
    display: flex;
    align-items: center;
    gap: 0.6rem;
  }

  h3 {
    margin: 0;
    font-family: "Iowan Old Style", "Palatino Linotype", Palatino, Georgia, serif;
  }

  .canvas {
    height: 16rem;
    border: 1px solid rgba(28, 36, 40, 0.14);
    background: rgba(255, 255, 255, 0.4);
  }

  .empty {
    margin: 0;
    color: #5a6a72;
    font-style: italic;
  }
</style>
