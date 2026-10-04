<script lang="ts">
  import {
    ApiClientError,
    getMatrixAggregate,
    getMatrixManifest,
    getMatrixMetricSummary,
    listMatrices,
    listMatrixCells,
    type MatrixListItem,
  } from '../api/client'
  import EpistemicBadge from '../components/EpistemicBadge.svelte'

  interface Props {
    matrixId?: string | null
  }

  let { matrixId = null }: Props = $props()

  let items = $state<MatrixListItem[]>([])
  let availability = $state('unavailable')
  let selectedId = $state<string | null>(null)
  let cellIds = $state<string[]>([])
  let aggregateKeys = $state<string[]>([])
  let summaryKeys = $state<string[]>([])
  let manifestMeta = $state<string>('')
  let error = $state<string | null>(null)
  let loading = $state(true)

  async function loadList(): Promise<void> {
    loading = true
    error = null
    try {
      const list = await listMatrices()
      items = list.items
      availability = list.availability
      if (import.meta.env.DEV) {
        console.debug(`research_ui_matrix_list count=${list.count}`)
      }
    } catch (err) {
      error = err instanceof ApiClientError ? err.code : 'fetch_failed'
      items = []
    } finally {
      loading = false
    }
  }

  async function loadDetail(id: string): Promise<void> {
    selectedId = id
    cellIds = []
    aggregateKeys = []
    summaryKeys = []
    manifestMeta = ''
    try {
      const [manifest, cells] = await Promise.all([
        getMatrixManifest(id),
        listMatrixCells(id),
      ])
      const schema =
        typeof manifest.schema_version === 'string'
          ? manifest.schema_version
          : 'unknown'
      manifestMeta = `schema=${schema}`
      cellIds = cells.cell_ids
      try {
        const aggregate = await getMatrixAggregate(id)
        aggregateKeys = Object.keys(aggregate).slice(0, 12)
      } catch {
        aggregateKeys = []
      }
      try {
        const summary = await getMatrixMetricSummary(id)
        summaryKeys = Object.keys(summary).slice(0, 12)
      } catch {
        summaryKeys = []
      }
    } catch (err) {
      error = err instanceof ApiClientError ? err.code : 'fetch_failed'
    }
  }

  $effect(() => {
    void loadList()
  })

  $effect(() => {
    const target = matrixId ?? selectedId
    if (target) {
      void loadDetail(target)
    }
  })
</script>

<section class="panel">
  <header class="head">
    <h1>Experiment matrices</h1>
    <EpistemicBadge epistemic="research_inference" />
  </header>
  <p class="lede">
    Read-only filesystem overview. Analytical results only — never start runs from here.
  </p>

  {#if loading}
    <p>Loading…</p>
  {:else if error !== null}
    <p class="error" role="alert">{error}</p>
  {:else if availability === 'unavailable'}
    <p class="empty">
      Matrix root unavailable. Set <code>PALIMPSEST_RESEARCH_MATRIX_ROOT</code>.
    </p>
  {:else if items.length === 0}
    <p class="empty">No experiment-matrix-v1 manifests found under the configured root.</p>
  {:else}
    <ul class="list">
      {#each items as item (item.matrix_id)}
        <li>
          <button type="button" onclick={() => void loadDetail(item.matrix_id)}>
            {item.matrix_id}
          </button>
          <span class="meta">
            {item.schema_version}
            {#if item.has_aggregate} · aggregate{/if}
            {#if item.has_metric_summary} · metric-summary{/if}
          </span>
        </li>
      {/each}
    </ul>
  {/if}

  {#if selectedId}
    <section class="detail">
      <h2>{selectedId}</h2>
      <p class="meta">{manifestMeta}</p>
      <h3>Cells ({cellIds.length})</h3>
      {#if cellIds.length === 0}
        <p class="empty">No cell JSON files.</p>
      {:else}
        <ul class="cells">
          {#each cellIds as cellId (cellId)}
            <li>{cellId}</li>
          {/each}
        </ul>
      {/if}
      <h3>Aggregate keys</h3>
      <p class="meta">
        {aggregateKeys.length > 0 ? aggregateKeys.join(', ') : 'unavailable'}
      </p>
      <h3>Metric summary keys</h3>
      <p class="meta">
        {summaryKeys.length > 0 ? summaryKeys.join(', ') : 'unavailable'}
      </p>
    </section>
  {/if}
</section>

<style>
  .panel {
    display: grid;
    gap: 0.85rem;
  }

  .head {
    display: flex;
    gap: 0.75rem;
    align-items: center;
    flex-wrap: wrap;
  }

  h1,
  h2,
  h3 {
    margin: 0;
    font-family: "Iowan Old Style", "Palatino Linotype", Palatino, Georgia, serif;
  }

  .lede,
  .meta,
  .empty {
    margin: 0;
    color: #5a6a72;
  }

  .error {
    color: #8a3030;
  }

  .list,
  .cells {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    gap: 0.45rem;
  }

  .list li {
    display: flex;
    gap: 0.75rem;
    align-items: baseline;
    flex-wrap: wrap;
  }

  button {
    font: inherit;
    padding: 0.3rem 0.5rem;
    border: 1px solid rgba(28, 36, 40, 0.22);
    background: rgba(255, 255, 255, 0.6);
    cursor: pointer;
  }

  .detail {
    display: grid;
    gap: 0.45rem;
    padding-top: 0.75rem;
    border-top: 1px solid rgba(28, 36, 40, 0.12);
  }
</style>
