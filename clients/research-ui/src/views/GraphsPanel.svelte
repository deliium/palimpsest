<script lang="ts">
  import { onMount } from 'svelte'
  import type { ElementDefinition } from 'cytoscape'
  import {
    ApiClientError,
    getBeliefSummary,
    getDebuggerLineage,
    getMemorySummary,
    getObserverEvents,
    getObserverRelationships,
    type GraphSummary,
    type ObserverEventOut,
  } from '../api/client'
  import ResearchGraph from '../graphs/ResearchGraph.svelte'

  interface Props {
    runId: string
    agentId: string | null
    eventId?: string | null
  }

  let { runId, agentId, eventId = null }: Props = $props()

  const COMM_TYPES = new Set(['talk', 'ask', 'tell'])
  const COMM_KINDS = new Set(['Talked', 'Asked', 'Told'])
  const MAX_SOCIAL_EDGES = 80
  const MAX_LINEAGE_EXPAND = 4

  let owner = $state('')
  let relationshipElements = $state<ElementDefinition[]>([])
  let socialElements = $state<ElementDefinition[]>([])
  let memoryElements = $state<ElementDefinition[]>([])
  let beliefElements = $state<ElementDefinition[]>([])
  let socialTruncated = $state(false)
  let error = $state<string | null>(null)
  let loading = $state(false)

  function isCommunication(event: ObserverEventOut): boolean {
    return COMM_TYPES.has(event.type) || COMM_KINDS.has(event.domain_kind)
  }

  function buildSocialGraph(events: ObserverEventOut[]): {
    elements: ElementDefinition[]
    truncated: boolean
  } {
    const nodes = new Map<string, ElementDefinition>()
    const edges: ElementDefinition[] = []
    let truncated = false
    for (const event of events) {
      if (!isCommunication(event)) {
        continue
      }
      const source = event.actor_id
      const target = event.target_id
      if (source === null || target === null || source === '' || target === '') {
        continue
      }
      if (edges.length >= MAX_SOCIAL_EDGES) {
        truncated = true
        break
      }
      nodes.set(source, { data: { id: source, label: source } })
      nodes.set(target, { data: { id: target, label: target } })
      edges.push({
        data: {
          id: event.event_id,
          source,
          target,
          label: event.type,
        },
      })
    }
    return { elements: [...nodes.values(), ...edges], truncated }
  }

  function baseGraphElements(summary: GraphSummary): ElementDefinition[] {
    const nodes = new Map<string, ElementDefinition>()
    const edges: ElementDefinition[] = []
    for (const item of summary.items) {
      nodes.set(item.node_id, {
        data: {
          id: item.node_id,
          label: item.source_kind ?? item.node_id.slice(0, 8),
        },
      })
      for (const ref of item.lineage_ref_ids) {
        if (!nodes.has(ref)) {
          nodes.set(ref, { data: { id: ref, label: ref.slice(0, 8) } })
        }
        edges.push({
          data: {
            id: `${item.node_id}->${ref}`,
            source: item.node_id,
            target: ref,
          },
        })
      }
      if (item.target_id) {
        if (!nodes.has(item.target_id)) {
          nodes.set(item.target_id, {
            data: { id: item.target_id, label: item.target_id },
          })
        }
        edges.push({
          data: {
            id: `${item.node_id}-target-${item.target_id}`,
            source: item.node_id,
            target: item.target_id,
          },
        })
      }
    }
    return [...nodes.values(), ...edges]
  }

  async function expandLineage(
    summary: GraphSummary,
    kind: 'memory_derivation' | 'belief_evidence',
    ownerId: string,
    base: ElementDefinition[],
  ): Promise<ElementDefinition[]> {
    const ordered = [...summary.items]
    if (eventId) {
      ordered.sort((a, b) => {
        const aHit = a.node_id === eventId || a.lineage_ref_ids.includes(eventId) ? 0 : 1
        const bHit = b.node_id === eventId || b.lineage_ref_ids.includes(eventId) ? 0 : 1
        return aHit - bHit
      })
    }
    const focusIds = ordered.slice(0, MAX_LINEAGE_EXPAND).map((item) => item.node_id)
    if (focusIds.length === 0) {
      return base
    }
    const nodes = new Map<string, ElementDefinition>()
    const edges: ElementDefinition[] = []
    for (const el of base) {
      const id = String(el.data.id)
      if ('source' in el.data) {
        edges.push(el)
      } else {
        nodes.set(id, el)
      }
    }
    for (const subjectId of focusIds) {
      try {
        const lineage = await getDebuggerLineage(runId, kind, subjectId, ownerId)
        if (lineage.availability !== 'available') {
          if (import.meta.env.DEV) {
            console.debug(
              `research_ui_graph lineage_unavailable kind=${kind} reason=${lineage.reason_code ?? lineage.availability}`,
            )
          }
          continue
        }
        for (const entry of lineage.entries) {
          for (const related of [...entry.related_ids, ...entry.parent_ids]) {
            if (!nodes.has(related)) {
              nodes.set(related, {
                data: { id: related, label: related.slice(0, 8) },
              })
            }
            edges.push({
              data: {
                id: `${subjectId}-lin-${entry.entry_id}-${related}`,
                source: subjectId,
                target: related,
              },
            })
          }
        }
      } catch (err) {
        const reason = err instanceof ApiClientError ? err.code : 'fetch_failed'
        if (import.meta.env.DEV) {
          console.debug(
            `research_ui_graph lineage_unavailable kind=${kind} reason=${reason}`,
          )
        }
      }
    }
    return [...nodes.values(), ...edges]
  }

  async function load(target: string): Promise<void> {
    loading = true
    error = null
    try {
      const [rels, memories, beliefs, observerEvents] = await Promise.all([
        getObserverRelationships(runId, target),
        getMemorySummary(runId, target),
        getBeliefSummary(runId, target),
        getObserverEvents(runId, { agentId: target, limit: 200 }),
      ])

      const nodes = new Map<string, ElementDefinition>()
      const edges: ElementDefinition[] = []
      nodes.set(target, { data: { id: target, label: target } })
      for (const item of rels.items) {
        nodes.set(item.target_id, {
          data: { id: item.target_id, label: item.target_id },
        })
        edges.push({
          data: {
            id: `${item.owner_id}->${item.target_id}`,
            source: item.owner_id,
            target: item.target_id,
          },
        })
      }
      relationshipElements = [...nodes.values(), ...edges]
      if (import.meta.env.DEV) {
        console.debug(
          `research_ui_graph kind=relationship nodes=${nodes.size} edges=${edges.length}`,
        )
      }

      const social = buildSocialGraph(observerEvents.events)
      socialElements = social.elements
      socialTruncated = social.truncated
      if (import.meta.env.DEV) {
        const edgeCount = social.elements.filter((el) => 'source' in el.data).length
        const nodeCount = social.elements.length - edgeCount
        console.debug(
          `research_ui_graph kind=social nodes=${nodeCount} edges=${edgeCount} truncated=${social.truncated}`,
        )
      }

      const memoryBase = baseGraphElements(memories)
      const beliefBase = baseGraphElements(beliefs)
      memoryElements = await expandLineage(
        memories,
        'memory_derivation',
        target,
        memoryBase,
      )
      beliefElements = await expandLineage(
        beliefs,
        'belief_evidence',
        target,
        beliefBase,
      )
      if (import.meta.env.DEV) {
        console.debug(
          `research_ui_graph kind=memory nodes=${memoryElements.filter((el) => !('source' in el.data)).length} size=${memoryElements.length} unavailable=${memories.availability}`,
        )
        console.debug(
          `research_ui_graph kind=belief nodes=${beliefElements.filter((el) => !('source' in el.data)).length} size=${beliefElements.length} unavailable=${beliefs.availability}`,
        )
      }
    } catch (err) {
      error = err instanceof ApiClientError ? err.code : 'fetch_failed'
      relationshipElements = []
      socialElements = []
      memoryElements = []
      beliefElements = []
      socialTruncated = false
    } finally {
      loading = false
    }
  }

  onMount(() => {
    if (agentId) {
      owner = agentId
      void load(agentId)
    }
  })

  function submit(event: Event): void {
    event.preventDefault()
    const value = owner.trim()
    if (value !== '') {
      void load(value)
    }
  }
</script>

<section class="panel">
  <header>
    <h2>Graphs</h2>
  </header>
  <form onsubmit={submit}>
    <label>
      Owner agent id
      <input bind:value={owner} placeholder="alice" autocomplete="off" />
    </label>
    <button type="submit">Load</button>
  </form>

  {#if loading}
    <p>Loading…</p>
  {:else if error !== null}
    <p class="error" role="alert">{error}</p>
  {:else}
    <ResearchGraph
      title="Relationship graph"
      epistemic="agent_belief"
      elements={relationshipElements}
      emptyMessage="No relationship summaries (needs subjective_debug + owner)."
    />
    <ResearchGraph
      title="Social / communication graph"
      epistemic="objective_world"
      elements={socialElements}
      emptyMessage="No Talked/Asked/Told delivery edges for this agent filter."
    />
    {#if socialTruncated}
      <p class="note">Social graph truncated at {MAX_SOCIAL_EDGES} edges.</p>
    {/if}
    <ResearchGraph
      title="Memory graph"
      epistemic="agent_memory"
      elements={memoryElements}
      emptyMessage="No memory summary nodes (metadata-safe page empty/unavailable)."
    />
    <ResearchGraph
      title="Belief graph"
      epistemic="agent_belief"
      elements={beliefElements}
      emptyMessage="No belief summary nodes (metadata-safe page empty/unavailable)."
    />
    <p class="note">
      Delivery edges are objective_world (Talked/Asked/Told). Relationship
      dimensions remain agent_belief. Focused lineage expands via debugger GETs
      (metadata ids only).
    </p>
  {/if}
</section>

<style>
  .panel {
    display: grid;
    gap: 1rem;
  }

  h2 {
    margin: 0;
    font-family: "Iowan Old Style", "Palatino Linotype", Palatino, Georgia, serif;
  }

  form {
    display: flex;
    gap: 0.5rem;
    align-items: end;
  }

  label {
    display: grid;
    gap: 0.25rem;
    font-size: 0.85rem;
  }

  input,
  button {
    font: inherit;
    padding: 0.35rem 0.55rem;
    border: 1px solid rgba(28, 36, 40, 0.22);
  }

  button {
    cursor: pointer;
    background: rgba(255, 255, 255, 0.6);
  }

  .error {
    color: #8a3030;
  }

  .note {
    margin: 0;
    color: #5a6a72;
    font-size: 0.85rem;
  }
</style>
