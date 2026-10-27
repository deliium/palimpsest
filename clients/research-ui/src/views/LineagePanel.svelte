<script lang="ts">
  import { onDestroy, onMount, untrack } from 'svelte'
  import { ApiClientError, getObserverRun } from '../api/client'
  import {
    getLineageFamilies,
    getLineageNodes,
    getLineageTraverse,
    scanLineageSnapshots,
  } from '../api/research'
  import { subscribeCredentialChanges } from '../auth/credentials'
  import AvailabilityNotice from '../components/research/AvailabilityNotice.svelte'
  import ResearchTable from '../components/research/ResearchTable.svelte'
  import LineageGraphView from '../graphs/LineageGraph.svelte'
  import type {
    LineageFamilyDescriptor,
    LineageGraph,
    LineageNode,
    LineageNodePage,
    LineageSnapshot,
  } from '../api/researchSchemas'
  import {
    FAMILY_CLASSES,
    LINEAGE_FAMILIES,
    capabilityFor,
    defaultEvidenceClass,
    detectCycle,
    matchQualifiedRef,
    mergeGraphPages,
    refLabel,
    sameSnapshot,
    type LineageEvidenceClass,
    type LineageFamily,
  } from '../research/lineage'
  import type { ResearchSelection } from '../research/selection'

  interface Props {
    runId: string
    selection: ResearchSelection
    onSelectionChange: (
      patch: Partial<ResearchSelection>,
      historyMode?: 'push' | 'replace',
    ) => void
    initialFamily?: LineageFamily
  }

  let { runId, selection, onSelectionChange, initialFamily = 'genealogy' }: Props =
    $props()

  let families = $state<LineageFamilyDescriptor[]>([])
  let family = $state<LineageFamily>(untrack(() => initialFamily))
  let evidence = $state<LineageEvidenceClass>(
    defaultEvidenceClass(untrack(() => initialFamily)),
  )
  let ownerId = $state<string | null>(null)
  let snapshots = $state<LineageSnapshot[]>([])
  let snapshot = $state<LineageSnapshot | null>(null)
  let requestedTick = $state<number | null>(null)
  let page = $state<LineageNodePage | null>(null)
  let roots = $state<LineageNode[]>([])
  let graph = $state<LineageGraph | null>(null)
  let status = $state<'loading' | 'available' | 'empty' | 'unavailable' | 'forbidden' | 'error'>('loading')
  let reason = $state<string | null>(null)
  let error = $state<string | null>(null)
  let selectedRoot = $state<string | null>(null)
  let continuation = $state<string | null>(null)
  let scanCursor = $state<string | null>(null)
  let scanLimited = $state(false)
  let scanExhausted = $state(false)
  let scanning = $state(false)
  let loadEpoch = 0
  let abort: AbortController | null = null
  let unsubscribeCredentials: (() => void) | null = null

  const SNAPSHOT_SCAN_PAGE_LIMIT = 200
  const SNAPSHOT_SCAN_PAGES = 5
  const MAX_SNAPSHOT_ROWS = 4000

  const descriptor = $derived(capabilityFor(families, family, evidence))

  onMount(() => {
    unsubscribeCredentials = subscribeCredentialChanges(() => {
      abort?.abort()
      snapshots = []
      snapshot = null
      page = null
      roots = []
      graph = null
      continuation = null
      scanCursor = null
      scanLimited = false
      scanExhausted = false
      void loadAll()
    })
    void loadAll()
  })

  onDestroy(() => {
    unsubscribeCredentials?.()
    unsubscribeCredentials = null
    abort?.abort()
    abort = null
  })

  $effect(() => {
    if (runId !== '') {
      untrack(() => {
        void loadAll()
      })
    }
  })

  function ensureEvidence(): void {
    if (!FAMILY_CLASSES[family].includes(evidence)) {
      evidence = defaultEvidenceClass(family)
    }
    if (evidence !== 'subjective') {
      ownerId = null
    }
    if (evidence !== 'objective') {
      ownerId = ownerId ?? selection.scopeOwnerId
    }
  }

  async function loadAll(): Promise<void> {
    const epoch = ++loadEpoch
    abort?.abort()
    abort = new AbortController()
    const signal = abort.signal
    scanning = false
    if (selection.sequence !== null) {
      status = 'unavailable'
      reason = 'prefix_cursor_requires_full_boundary'
      return
    }
    status = 'loading'
    reason = null
    error = null
    snapshots = []
    snapshot = null
    page = null
    roots = []
    graph = null
    continuation = null
    scanCursor = null
    scanLimited = false
    scanExhausted = false
    try {
      if (families.length === 0) {
        try {
          families = await getLineageFamilies(runId, true, signal)
        } catch (err) {
          if (err instanceof ApiClientError && err.status === 403) {
            families = await getLineageFamilies(runId, false, signal)
          } else {
            throw err
          }
        }
      }
      ensureEvidence()
      if (descriptor === null) {
        status = 'unavailable'
        reason = 'unsupported_family_class'
        return
      }
      const run = await getObserverRun(runId, signal)
      requestedTick = selection.tick ?? run.latest_tick ?? run.tick
      const scan = await scanLineageSnapshots(
        runId,
        { family, evidenceClass: evidence, ownerId },
        {
          boundaryTick: requestedTick,
          limit: SNAPSHOT_SCAN_PAGE_LIMIT,
          maxPages: SNAPSHOT_SCAN_PAGES,
        },
        signal,
      )
      if (epoch !== loadEpoch) {
        return
      }
      mergeSnapshots(scan.items)
      scanCursor = scan.nextCursor
      scanExhausted = scan.exhausted
      scanLimited = scan.nextCursor !== null
      if (scan.snapshot === null) {
        status = 'unavailable'
        reason = scanLimited ? 'scan_limited' : 'snapshot_not_found'
        return
      }
      snapshot = scan.snapshot
      await loadNodesFor(scan.snapshot, epoch, signal)
    } catch (err) {
      if (epoch !== loadEpoch) {
        return
      }
      if (err instanceof DOMException) {
        return
      }
      if (err instanceof ApiClientError) {
        status = err.status === 403 ? 'forbidden' : 'error'
        reason = err.code
      } else {
        status = 'error'
        reason = err instanceof Error ? err.message : 'fetch_failed'
      }
    }
  }

  function mergeSnapshots(items: LineageSnapshot[]): void {
    const known = new Map(snapshots.map((item) => [item.publication_id, item]))
    let limited = false
    for (const item of items) {
      if (known.size >= MAX_SNAPSHOT_ROWS && !known.has(item.publication_id)) {
        limited = true
        break
      }
      known.set(item.publication_id, item)
    }
    snapshots = [...known.values()].sort(
      (left, right) => right.boundary_tick - left.boundary_tick,
    )
    if (limited) {
      scanLimited = true
    }
  }

  async function continueSnapshotScan(): Promise<void> {
    if (scanCursor === null || requestedTick === null || scanning) {
      return
    }
    scanning = true
    const epoch = loadEpoch
    const signal = abort?.signal
    try {
      const scan = await scanLineageSnapshots(
        runId,
        { family, evidenceClass: evidence, ownerId },
        {
          boundaryTick: requestedTick,
          after: scanCursor,
          limit: SNAPSHOT_SCAN_PAGE_LIMIT,
          maxPages: SNAPSHOT_SCAN_PAGES,
        },
        signal,
      )
      if (epoch !== loadEpoch) {
        return
      }
      mergeSnapshots(scan.items)
      scanCursor = scan.nextCursor
      scanExhausted = scan.exhausted
      scanLimited = scan.nextCursor !== null
      if (scan.snapshot !== null) {
        snapshot = scan.snapshot
        await loadNodesFor(scan.snapshot, epoch, signal)
        return
      }
      status = 'unavailable'
      reason = scanLimited ? 'scan_limited' : 'snapshot_not_found'
    } catch (err) {
      if (epoch !== loadEpoch) {
        return
      }
      if (err instanceof DOMException) {
        return
      }
      status = 'error'
      reason = err instanceof Error ? err.message : 'fetch_failed'
    } finally {
      scanning = false
    }
  }

  async function loadNodesFor(
    target: LineageSnapshot,
    epoch: number,
    signal?: AbortSignal,
  ): Promise<void> {
    const nodes = await getLineageNodes(
      runId,
      { family, evidenceClass: evidence, ownerId },
      { boundaryTick: target.boundary_tick, limit: 200 },
      signal,
    )
    if (epoch !== loadEpoch) {
      return
    }
    if (!sameSnapshot(target, nodes.snapshot)) {
      status = 'error'
      reason = 'research_snapshot_changed'
      return
    }
    page = nodes
    roots = nodes.items
    status = roots.length === 0 ? 'empty' : 'available'
    graph = null
    selectedRoot = null
    continuation = null
  }

  async function chooseSnapshot(value: string): Promise<void> {
    const found = snapshots.find((item) => item.publication_id === value)
    if (found === undefined) {
      return
    }
    snapshot = found
    await loadNodes()
  }

  async function loadNodes(): Promise<void> {
    if (snapshot === null) {
      return
    }
    const epoch = ++loadEpoch
    abort?.abort()
    abort = new AbortController()
    status = 'loading'
    try {
      await loadNodesFor(snapshot, epoch, abort.signal)
    } catch (err) {
      if (epoch !== loadEpoch) {
        return
      }
      status = 'error'
      reason =
        err instanceof ApiClientError
          ? err.code
          : err instanceof Error
            ? err.message
            : 'fetch_failed'
    }
  }

  async function expand(rootKey: string): Promise<void> {
    if (snapshot === null) {
      return
    }
    const epoch = ++loadEpoch
    abort?.abort()
    abort = new AbortController()
    const signal = abort.signal
    const target = snapshot
    selectedRoot = rootKey
    status = 'loading'
    try {
      const next = await getLineageTraverse(
        runId,
        { family, evidenceClass: evidence, ownerId },
        {
          rootKey,
          boundaryTick: target.boundary_tick,
          direction: 'both',
          maxDepth: 2,
          maxNodes: 500,
          maxEdges: 1500,
          livingOnly: false,
          limit: 200,
        },
        signal,
      )
      if (epoch !== loadEpoch) {
        return
      }
      if (!sameSnapshot(target, next.snapshot)) {
        throw new Error('research_snapshot_changed')
      }
      graph = next
      continuation = next.next_cursor
      status = 'available'
    } catch (err) {
      if (epoch !== loadEpoch || err instanceof DOMException) {
        return
      }
      status = 'error'
      reason = err instanceof Error ? err.message : 'fetch_failed'
    }
  }

  async function loadMoreGraph(): Promise<void> {
    if (graph === null || snapshot === null || continuation === null) {
      return
    }
    const epoch = loadEpoch
    try {
      const next = await getLineageTraverse(
        runId,
        { family, evidenceClass: evidence, ownerId },
        {
          rootKey: graph.root.key,
          boundaryTick: snapshot.boundary_tick,
          after: continuation,
          limit: 200,
        },
        abort?.signal,
      )
      if (epoch !== loadEpoch) {
        return
      }
      graph = mergeGraphPages(graph, next)
      continuation = next.next_cursor
    } catch (err) {
      if (epoch !== loadEpoch || err instanceof DOMException) {
        return
      }
      reason = err instanceof Error ? err.message : 'fetch_failed'
      status = 'error'
    }
  }

  function focusNode(key: string): void {
    const item = graph?.nodes.find((node) => node.ref.key === key) ??
      roots.find((node) => node.ref.key === key)
    if (item === undefined) {
      return
    }
    const kind = item.ref.native_kind
    if (kind === 'agent') {
      onSelectionChange({
        view: 'agent',
        tick: snapshot?.boundary_tick ?? selection.tick,
        focus: { kind: 'agent', source: 'objective', agentId: item.ref.native_id },
      })
    }
  }

  function selectRoot(rootKey: string): void {
    const node = roots.find((item) => item.ref.key === rootKey)
    if (node !== undefined) {
      const matched = page === null ? null : matchQualifiedRef(page, {
        family,
        evidenceClass: evidence,
        nativeKind: node.ref.native_kind,
        nativeId: node.ref.native_id,
        identityOwner: node.ref.identity_owner,
        nodeKey: node.ref.key,
      })
      if (matched === null) {
        reason = 'ambiguous_lineage_node'
        return
      }
      void expand(matched.key)
    }
  }
</script>

<section class="page">
  <header>
    <p class="eyebrow">Lineage</p>
    <h1>Qualified lineage explorer</h1>
    <p class="lede">
      Eight evidence families share qualified identities. A local ID is never a
      cross-owner or cross-family join key.
    </p>
  </header>

  <div class="controls">
    <label>
      Family
      <select
        value={family}
        onchange={(event) => {
          family = event.currentTarget.value as LineageFamily
          void loadAll()
        }}
      >
        {#each LINEAGE_FAMILIES as item (item)}
          <option value={item}>{item}</option>
        {/each}
      </select>
    </label>
    <label>
      Evidence class
      <select
        value={evidence}
        onchange={(event) => {
          evidence = event.currentTarget.value as LineageEvidenceClass
          void loadAll()
        }}
      >
        {#each FAMILY_CLASSES[family] as item (item)}
          <option value={item}>{item}</option>
        {/each}
      </select>
    </label>
    {#if evidence !== 'objective'}
      <label>
        Scope owner
        <input
          value={ownerId ?? ''}
          onchange={(event) => {
            ownerId = event.currentTarget.value.trim() || null
            void loadAll()
          }}
          placeholder="owner id"
        />
      </label>
    {/if}
    <label>
      Publication boundary
      <select
        value={snapshot?.publication_id ?? ''}
        onchange={(event) => void chooseSnapshot(event.currentTarget.value)}
      >
        {#each snapshots as item (item.publication_id)}
          <option value={item.publication_id}>
            tick {item.boundary_tick} · {item.publication_id}
          </option>
        {/each}
      </select>
    </label>
    <button type="button" onclick={() => void loadAll()}>Reload lineage</button>
  </div>

  {#if scanLimited}
    <div class="actions" role="status">
      <span class="muted">
        Publication discovery scanned {snapshots.length} publication(s) and is
        scan-limited; the requested boundary is not proven absent.
      </span>
      <button type="button" onclick={() => void continueSnapshotScan()} disabled={scanning}>
        Continue publication scan
      </button>
    </div>
  {/if}

  {#if requestedTick !== null && snapshot !== null && snapshot.boundary_tick !== requestedTick}
    <p class="notice" role="status">
      Showing explicit published boundary {snapshot.boundary_tick} for requested
      tick {requestedTick}; it is not relabelled as current.
    </p>
  {/if}

  <AvailabilityNotice
    status={status}
    reason={reason}
    requestedTick={requestedTick}
    resolvedTick={snapshot?.boundary_tick ?? null}
  />
  {#if error !== null}
    <p class="error" role="alert">{error}</p>
  {/if}

  {#if evidence === 'analytical'}
    <p class="muted">
      Analytical scope omits API <code>owner_id</code>; native identity owner is
      preserved inside each qualified ref.
    </p>
  {/if}

  {#if roots.length > 0}
    <ResearchTable
      caption="Root candidates at the pinned publication"
      columns={[
        { key: 'label', label: 'Qualified node' },
        { key: 'family', label: 'Family' },
        { key: 'evidence', label: 'Evidence' },
        { key: 'owner', label: 'Identity owner' },
        { key: 'state', label: 'State' },
        { key: 'matched', label: 'Matched' },
      ]}
      rows={roots.map((node) => ({
        label: refLabel(node.ref),
        family: node.ref.family,
        evidence: node.ref.evidence_class,
        owner: node.ref.identity_owner,
        state: node.state,
        matched:
          page?.matched_node_keys.includes(node.ref.key) === true ? 'yes' : 'no',
      }))}
      rowKey={(row) => String(row.label)}
      onRowSelect={(row) => {
        const node = roots.find((item) => refLabel(item.ref) === row.label)
        if (node !== undefined) {
          selectRoot(node.ref.key)
        }
      }}
    />
    {#if page !== null && page.context_only_node_keys.length > 0}
      <p class="muted">
        {page.context_only_node_keys.length} context-only connector node(s) are
        shown but not counted as matched roots.
      </p>
    {/if}
  {/if}

  {#if graph !== null}
    <LineageGraphView
      {graph}
      {family}
      onNodeSelect={focusNode}
    />
    {#if detectCycle(graph)}
      <p class="muted">
        A returned cycle is surfaced; no edge is silently removed.
      </p>
    {/if}
    {#if continuation !== null}
      <button type="button" onclick={() => void loadMoreGraph()}>
        Load more graph
      </button>
    {/if}
    <p class="muted">
      Server budgets: depth {graph.effective_max_depth}, nodes
      {graph.effective_max_nodes}, edges {graph.effective_max_edges}, page
      {graph.effective_page_size}.
    </p>
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

  .controls {
    display: flex;
    flex-wrap: wrap;
    gap: 0.7rem;
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

  .notice {
    margin: 0;
    color: #6a5420;
    font-size: 0.85rem;
  }

  .muted {
    color: #5a6a72;
    font-size: 0.85rem;
  }

  .error {
    color: #8a3030;
  }
</style>
