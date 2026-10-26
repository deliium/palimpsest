<script lang="ts">
  import { onMount } from 'svelte'
  import { ApiClientError } from '../api/client'
  import {
    getLineageMentorshipParticipants,
    getLineageTraverse,
  } from '../api/research'
  import AvailabilityNotice from '../components/research/AvailabilityNotice.svelte'
  import ResearchTable from '../components/research/ResearchTable.svelte'
  import LineageGraphView from '../graphs/LineageGraph.svelte'
  import type { LineageGraph, LineageSnapshot } from '../api/researchSchemas'
  import { mergeGraphPages, sameSnapshot } from '../research/lineage'
  import type { ResearchSelection } from '../research/selection'

  interface Props {
    runId: string
    selection: ResearchSelection
    onSelectionChange: (
      patch: Partial<ResearchSelection>,
      historyMode?: 'push' | 'replace',
    ) => void
  }

  let { runId, selection, onSelectionChange }: Props = $props()

  let evidence = $state<'subjective' | 'analytical'>('subjective')
  let ownerId = $state<string | null>(null)
  let agentId = $state('')
  let role = $state<'teacher' | 'learner' | 'both'>('both')
  let payload = $state<Record<string, unknown> | null>(null)
  let snapshot = $state<LineageSnapshot | null>(null)
  let items = $state<Array<Record<string, unknown>>>([])
  let nextCursor = $state<string | null>(null)
  let graph = $state<LineageGraph | null>(null)
  let status = $state<'loading' | 'available' | 'empty' | 'unavailable' | 'forbidden' | 'error'>('loading')
  let reason = $state<string | null>(null)
  let error = $state<string | null>(null)

  const scope = $derived({
    family: 'mentorship',
    evidenceClass: evidence,
    ownerId: evidence === 'analytical' ? null : ownerId,
  })

  onMount(() => {
    void load()
  })

  $effect(() => {
    if (runId !== '') {
      status = 'loading'
    }
  })

  async function load(more = false): Promise<void> {
    if (agentId.trim() === '') {
      status = 'unavailable'
      reason = 'agent_required'
      return
    }
    status = 'loading'
    reason = null
    error = null
    try {
      const page = await getLineageMentorshipParticipants(
        runId,
        scope,
        {
          agentId: agentId.trim(),
          role,
          after: more ? nextCursor : null,
          boundaryTick: selection.tick,
          limit: 100,
        },
      )
      payload = page
      const snap = page.snapshot
      if (snap === null || typeof snap !== 'object') {
        status = 'error'
        reason = 'invalid_research_response'
        return
      }
      snapshot = snap as LineageSnapshot
      const rawItems = Array.isArray(page.items) ? page.items : []
      const pageItems = rawItems.filter(
        (item): item is Record<string, unknown> =>
          item !== null && typeof item === 'object' && !Array.isArray(item),
      )
      items = more ? [...items, ...pageItems] : pageItems
      nextCursor =
        typeof page.next_cursor === 'string' ? page.next_cursor : null
      status = items.length === 0 ? 'empty' : 'available'
      if (page.scan_limited === true) {
        reason = 'scan_limited'
      }
    } catch (err) {
      if (err instanceof ApiClientError) {
        status = err.status === 403 ? 'forbidden' : 'error'
        reason = err.code
      } else {
        status = 'error'
        reason = 'fetch_failed'
      }
    }
  }

  async function loadNetwork(): Promise<void> {
    if (snapshot === null || items.length === 0) {
      return
    }
    const anchor = items[0]?.ref
    if (anchor === null || typeof anchor !== 'object') {
      return
    }
    const key = (anchor as Record<string, unknown>).key
    if (typeof key !== 'string') {
      return
    }
    try {
      const next = await getLineageTraverse(
        runId,
        scope,
        {
          rootKey: key,
          boundaryTick: snapshot.boundary_tick,
          direction: 'both',
          maxDepth: 2,
          maxNodes: 500,
          maxEdges: 1500,
          limit: 200,
        },
      )
      if (!sameSnapshot(snapshot, next.snapshot)) {
        throw new Error('research_snapshot_changed')
      }
      graph = next
    } catch (err) {
      reason = err instanceof Error ? err.message : 'fetch_failed'
      status = 'error'
    }
  }

  async function loadMoreNetwork(): Promise<void> {
    if (graph === null || graph.next_cursor === null) {
      return
    }
    try {
      const next = await getLineageTraverse(
        runId,
        scope,
        {
          rootKey: graph.root.key,
          boundaryTick: graph.snapshot.boundary_tick,
          after: graph.next_cursor,
          limit: 200,
        },
      )
      graph = mergeGraphPages(graph, next)
    } catch (err) {
      reason = err instanceof Error ? err.message : 'fetch_failed'
      status = 'error'
    }
  }

  function focusAgent(id: unknown): void {
    if (typeof id !== 'string' || id === '') {
      return
    }
    onSelectionChange({
      view: 'agent',
      tick: selection.tick,
      focus: { kind: 'agent', source: 'objective', agentId: id },
    })
  }

  function contentNote(item: Record<string, unknown>): string {
    if (item.content_kind === 'knowledge') {
      return `content ${String(item.content_key)} · open the exact knowledge-family ref from the graph; content key is not a native entry ID`
    }
    return `content ${String(item.content_key ?? '—')}`
  }
</script>

<section class="page">
  <header>
    <p class="eyebrow">Teaching</p>
    <h1>Teacher / student networks</h1>
    <p class="lede">
      Attempted teaching is shown separately from learning evidence. Roles are
      observed or claimed relations in evidence, not social ranks.
    </p>
  </header>

  <div class="controls">
    <label>
      Evidence
      <select
        value={evidence}
        onchange={(event) => {
          evidence = event.currentTarget.value as 'subjective' | 'analytical'
          void load()
        }}
      >
        <option value="subjective">subjective (one owner)</option>
        <option value="analytical">analytical (cross-owner)</option>
      </select>
    </label>
    {#if evidence === 'subjective'}
      <label>
        Scope owner
        <input
          value={ownerId ?? ''}
          onchange={(event) => {
            ownerId = event.currentTarget.value.trim() || null
            void load()
          }}
        />
      </label>
    {/if}
    <label>
      Agent
      <input bind:value={agentId} placeholder="agent id" />
    </label>
    <label>
      Role
      <select
        value={role}
        onchange={(event) => {
          role = event.currentTarget.value as 'teacher' | 'learner' | 'both'
          void load()
        }}
      >
        <option value="both">both</option>
        <option value="teacher">teacher</option>
        <option value="learner">learner</option>
      </select>
    </label>
    <button type="button" onclick={() => void load()}>Load evidence</button>
    <button type="button" onclick={() => void loadNetwork()} disabled={items.length === 0}>
      Load mentorship graph
    </button>
  </div>

  <AvailabilityNotice
    status={status}
    reason={reason}
    requestedTick={selection.tick}
    resolvedTick={snapshot?.boundary_tick ?? null}
    continuation={nextCursor}
    onLoadMore={() => void load(true)}
  />
  {#if error !== null && error !== reason}
    <p class="error" role="alert">{error}</p>
  {/if}

  {#if items.length > 0}
    <ResearchTable
      caption="Mentorship participant evidence"
      columns={[
        { key: 'teacher', label: 'Teacher' },
        { key: 'learner', label: 'Learner' },
        { key: 'owner', label: 'Claim owner' },
        { key: 'attempts', label: 'Attempts', numeric: true },
        { key: 'uptake', label: 'Learning evidence', numeric: true },
        { key: 'state', label: 'Learning state' },
        { key: 'hop', label: 'Hop', numeric: true },
        { key: 'acquisition', label: 'Acquisition tick', numeric: true },
        { key: 'update', label: 'Update tick', numeric: true },
        { key: 'mutated', label: 'Mutated' },
        { key: 'content', label: 'Content' },
      ]}
      rows={items.map((item) => ({
        teacher: String(item.teacher_id ?? '—'),
        learner: String(item.learner_id ?? '—'),
        owner: String(item.owner_id ?? '—'),
        attempts: Number(item.attempt_count ?? 0),
        uptake: Number(item.learning_evidence_count ?? 0),
        state: String(item.learning_state ?? item.native_status ?? '—'),
        hop: Number(item.hop ?? 0),
        acquisition: Number(item.acquisition_tick ?? 0),
        update: Number(item.update_tick ?? 0),
        mutated: item.mutated === true ? 'yes' : 'no',
        content: contentNote(item),
      }))}
      rowKey={(row) => `${row.teacher}:${row.learner}:${row.content}`}
      onRowSelect={(row) => {
        focusAgent(row.teacher)
      }}
    />
    <div class="actions">
      <button type="button" onclick={() => focusAgent(items[0]?.teacher_id)}>
        Focus teacher
      </button>
      <button type="button" onclick={() => focusAgent(items[0]?.learner_id)}>
        Focus learner
      </button>
    </div>
  {:else if status === 'empty'}
    <p class="muted">
      Complete empty retained mentorship inventory at this boundary; not proof
      that no teaching ever occurred.
    </p>
  {/if}

  {#if graph !== null}
    <LineageGraphView {graph} family="mentorship" />
    {#if graph.next_cursor !== null}
      <button type="button" onclick={() => void loadMoreNetwork()}>
        Load more network
      </button>
    {/if}
  {/if}
</section>

<style>
  .page {
    display: grid;
    gap: 0.9rem;
  }

  .eyebrow {
    margin: 0 0 0.2rem;
    font-size: 0.75rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #5a6a72;
  }

  h1 {
    margin: 0 0 0.3rem;
    font-size: 1.35rem;
  }

  .lede {
    margin: 0;
    color: #3a474e;
  }

  .controls,
  .actions {
    display: flex;
    flex-wrap: wrap;
    gap: 0.6rem;
    align-items: end;
  }

  label {
    display: grid;
    gap: 0.2rem;
    font-size: 0.8rem;
    color: #5a6a72;
  }

  select,
  input,
  button {
    font: inherit;
    padding: 0.25rem 0.45rem;
  }

  .muted {
    color: #5a6a72;
    font-size: 0.85rem;
  }

  .error {
    color: #8a3030;
  }
</style>
