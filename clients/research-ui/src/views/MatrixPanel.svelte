<script lang="ts">
  import {
    ApiClientError,
    getMatrixAggregate,
    getMatrixCell,
    getMatrixCellMetrics,
    getMatrixManifest,
    getMatrixMetricSummary,
    listMatrices,
    listMatrixCells,
    type MatrixListItem,
  } from '../api/client'
  import {
    readCulturalCellMetrics,
    readCulturalComparison,
  } from '../api/research'
  import EpistemicBadge from '../components/EpistemicBadge.svelte'
  import ResearchTable from '../components/research/ResearchTable.svelte'
  import {
    culturalComparisonFacets,
    facetLabel,
    incompatibleSelectors,
    intervalUsable,
    scalarMetricFacets,
    type MetricFacet,
  } from '../research/matrixMetrics'
  import { pushRunRoute } from '../router'

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
  let metricFacets = $state<MetricFacet[]>([])
  let metricBindings = $state<string[]>([])
  let selectorConflicts = $state<Array<[string, string]>>([])
  let metricError = $state<string | null>(null)
  let cellRuns = $state<Record<string, string>>({})

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
    metricFacets = []
    metricBindings = []
    selectorConflicts = []
    metricError = null
    cellRuns = {}
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
      await loadMetrics(id, cellIds)
    } catch (err) {
      error = err instanceof ApiClientError ? err.code : 'fetch_failed'
    }
  }

  async function loadMetrics(id: string, cells: string[]): Promise<void> {
    const facets: MetricFacet[] = []
    const bindings = new Set<string>()
    const runMap: Record<string, string> = {}
    try {
      const comparison = await readCulturalComparison(id)
      bindings.add(comparison.binding)
      facets.push(...culturalComparisonFacets(null, comparison.data))
    } catch {
      // Cultural comparison is optional for any one matrix.
    }
    for (const cellId of cells.slice(0, 6)) {
      try {
        const state = await getMatrixCell(id, cellId)
        const runId = typeof state.run_id === 'string' ? state.run_id : null
        if (runId !== null) {
          runMap[cellId] = runId
        }
      } catch {
        // Cell state is optional metadata.
      }
      try {
        const metrics = await getMatrixCellMetrics(id, cellId)
        facets.push(...scalarMetricFacets(cellId, metrics))
      } catch {
        // A cell without metric sidecars remains visible in the cell list.
      }
      try {
        const cultural = await readCulturalCellMetrics(id, cellId)
        bindings.add(cultural.binding)
        facets.push(...scalarMetricFacets(cellId, cultural.data))
      } catch {
        // Cultural metrics are optional per cell.
      }
    }
    metricFacets = facets
    metricBindings = [...bindings]
    selectorConflicts = incompatibleSelectors(facets)
    cellRuns = runMap
    if (facets.length === 0) {
      metricError = 'no_metric_rows'
    }
  }

  function metricValue(facet: MetricFacet): string {
    if (facet.meanDifference !== null) {
      return facet.meanDifference.toFixed(6)
    }
    return facet.value === null ? '—' : facet.value.toFixed(6)
  }

  function intervalLabel(facet: MetricFacet): string {
    if (!intervalUsable(facet)) {
      return facet.inferenceStatus ?? 'not_comparable'
    }
    return `${facet.ciLow?.toFixed(6)} … ${facet.ciHigh?.toFixed(6)} (df ${facet.df ?? '—'})`
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
    <p class="empty">No supported matrix manifests found under the configured root.</p>
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
            <li>
              {cellId}
              {#if cellRuns[cellId]}
                <button
                  type="button"
                  onclick={() => pushRunRoute(cellRuns[cellId] ?? '', 'overview')}
                >
                  Open run {cellRuns[cellId]}
                </button>
              {:else}
                <span class="meta">run ID unavailable</span>
              {/if}
            </li>
          {/each}
        </ul>
      {/if}

      <h3>Stored metric rows</h3>
      <p class="meta">
        Artifact binding: {metricBindings.length === 0 ? 'none' : metricBindings.join(', ')}
      </p>
      {#if metricError !== null}
        <p class="empty">
          {metricError === 'no_metric_rows'
            ? 'No PRESENT/PARTIAL metric rows in the stored sidecars.'
            : metricError}
        </p>
      {:else}
        {#if selectorConflicts.length > 0}
          <p class="error" role="status">
            not_comparable: {selectorConflicts.length} measurement selector(s)
            disagree. They remain separate facets.
          </p>
        {/if}
        <ResearchTable
          caption="Stored generational and cultural metric facets"
          columns={[
            { key: 'cell', label: 'Cell' },
            { key: 'facet', label: 'Family · measurement' },
            { key: 'value', label: 'Value / mean difference', numeric: true },
            { key: 'n', label: 'n', numeric: true },
            { key: 'interval', label: 'Interval / status' },
            { key: 'method', label: 'Method' },
            { key: 'binding', label: 'Binding' },
          ]}
          rows={metricFacets.map((facet) => ({
            cell: facet.cellId ?? 'matrix',
            facet: facetLabel(facet),
            value: metricValue(facet),
            n: facet.n,
            interval: intervalLabel(facet),
            method: facet.method,
            binding: metricBindings.join(', ') || 'none',
          }))}
          rowKey={(row) =>
            `${row.cell}:${row.facet}:${row.value}:${row.interval}`}
        />
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
