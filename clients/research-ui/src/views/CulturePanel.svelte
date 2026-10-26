<script lang="ts">
  import { ApiClientError } from '../api/client'
  import {
    getCivilizationOverlays,
    getCulturalEvidence,
  } from '../api/research'
  import AvailabilityNotice from '../components/research/AvailabilityNotice.svelte'
  import ResearchTable from '../components/research/ResearchTable.svelte'
  import SeriesChart from '../components/research/SeriesChart.svelte'
  import {
    culturalSeries,
    summarizeCulturalPage,
    type CulturalPageSummary,
  } from '../research/culture'
  import type { ResearchSelection } from '../research/selection'

  interface Props {
    runId: string
    selection: ResearchSelection
  }

  let { runId, selection }: Props = $props()

  let matrixId = $state('')
  let cellId = $state('')
  let summary = $state<CulturalPageSummary | null>(null)
  let status = $state<'loading' | 'available' | 'empty' | 'partial' | 'unavailable' | 'forbidden' | 'error'>('unavailable')
  let reason = $state<string | null>(null)
  let error = $state<string | null>(null)
  let overlayRows = $state<Array<Record<string, unknown>>>([])
  let overlayStatus = $state<string | null>(null)
  let cursor = $state<string | null>(null)
  let partialPage = $state(false)

  async function load(more = false): Promise<void> {
    if (matrixId.trim() === '' || cellId.trim() === '') {
      status = 'unavailable'
      reason = 'matrix_cell_required'
      summary = null
      return
    }
    status = 'loading'
    reason = null
    error = null
    try {
      const page = await getCulturalEvidence(matrixId.trim(), cellId.trim(), {
        section: 'traits',
        limit: 200,
        cursor: more ? cursor : null,
      })
      const pageRun = String(page.run_id ?? '')
      if (pageRun !== runId) {
        status = 'error'
        reason = 'matrix_run_mismatch'
        summary = null
        return
      }
      const next = summarizeCulturalPage(page)
      summary = next
      partialPage = next.partial || (page.truncated === true)
      cursor = typeof page.next_cursor === 'string' ? page.next_cursor : null
      status = next.dimensions.length === 0
        ? 'empty'
        : next.partial
          ? 'partial'
          : 'available'
    } catch (err) {
      if (err instanceof ApiClientError) {
        status = err.status === 403 ? 'forbidden' : err.code === 'invalid_tick_window' ? 'error' : 'error'
        reason = err.code
      } else {
        status = 'error'
        reason = 'fetch_failed'
      }
    }
  }

  async function loadOverlays(): Promise<void> {
    overlayStatus = 'loading'
    try {
      const evidence =
        selection.evidenceClass === 'objective'
          ? 'OBJECTIVE'
          : selection.evidenceClass === 'subjective'
            ? 'SUBJECTIVE'
            : 'ANALYTICAL'
      const overlay = await getCivilizationOverlays(runId, {
        tick: selection.tick ?? 0,
        layer: 'culture',
        evidenceClass: evidence,
        ownerId: evidence === 'OBJECTIVE' ? null : selection.scopeOwnerId,
        limit: 200,
      })
      overlayRows = Array.isArray(overlay.rows)
        ? overlay.rows.filter(
            (row): row is Record<string, unknown> =>
              row !== null && typeof row === 'object',
          )
        : []
      overlayStatus =
        overlay.availability === 'unavailable' ? (overlay.reason ?? 'unavailable') : null
    } catch (err) {
      overlayStatus = err instanceof ApiClientError ? err.code : 'fetch_failed'
      overlayRows = []
    }
  }
</script>

<section class="page">
  <header>
    <p class="eyebrow">Culture</p>
    <h1>Cultural trait timelines</h1>
    <p class="lede">
      Captured owner inventories by dimension. Descriptive display summaries only;
      no composite culture score and no inferred history.
    </p>
  </header>

  <div class="controls">
    <label>
      Matrix
      <input bind:value={matrixId} placeholder="matrix id" />
    </label>
    <label>
      Cell
      <input bind:value={cellId} placeholder="cell id" />
    </label>
    <button type="button" onclick={() => void load()}>Load captured inventory</button>
    <button type="button" onclick={() => void loadOverlays()}>
      Load captured culture overlays
    </button>
  </div>

  <AvailabilityNotice
    status={status}
    reason={reason}
    requestedTick={selection.tick}
    continuation={cursor}
    onLoadMore={() => void load(true)}
  />
  {#if error !== null}
    <p class="error" role="alert">{error}</p>
  {/if}

  {#if summary !== null}
    <div class="cards">
      <p><strong>Binding</strong> {summary.binding}</p>
      <p><strong>Window</strong> {summary.requestedWindow.from_tick ?? '—'} … {summary.requestedWindow.to_tick ?? '—'}</p>
      <p><strong>Capture</strong> {JSON.stringify(summary.captureStatus)}</p>
      <p><strong>Gaps</strong> {summary.gaps.length}</p>
    </div>
    {#if summary.binding === 'legacy_unverified'}
      <p class="warning" role="status">
        legacy_unverified: a stored self-digest does not prove runtime completion.
      </p>
    {/if}
    {#if partialPage}
      <p class="warning" role="status">
        Partial page: distinct-form counts cover only loaded rows and are not a
        complete inventory total.
      </p>
    {/if}

    {#each summary.dimensions as dimension (dimension.dimension)}
      <section>
        <h2>{dimension.dimension}</h2>
        <p class="muted">
          Coverage {dimension.coverage === null ? 'unknown' : `${(dimension.coverage * 100).toFixed(0)}%`}
          {#if dimension.partial}· partial inventory{/if}
        </p>
        <SeriesChart
          title={`${dimension.dimension} carrier timeline`}
          description="Distinct owners carrying an entry in the selected dimension. Complete empty coverage is zero; missing coverage is a gap."
          series={culturalSeries(summary, 'carrierOwners').filter((series) => series.id.startsWith(`${dimension.dimension}:`))}
        />
      </section>
    {/each}

    <ResearchTable
      caption="Dimension summaries"
      columns={[
        { key: 'dimension', label: 'Dimension' },
        { key: 'points', label: 'Boundaries', numeric: true },
        { key: 'coverage', label: 'Coverage' },
        { key: 'partial', label: 'Status' },
      ]}
      rows={summary.dimensions.map((dimension) => ({
        dimension: dimension.dimension,
        points: dimension.points.length,
        coverage:
          dimension.coverage === null
            ? 'unknown'
            : `${(dimension.coverage * 100).toFixed(0)}%`,
        partial: dimension.partial ? 'partial' : 'complete',
      }))}
      rowKey={(row) => String(row.dimension)}
    />
  {/if}

  {#if overlayRows.length > 0}
    <ResearchTable
      caption="Captured civilization culture overlays"
      columns={[
        { key: 'row', label: 'Row' },
        { key: 'owner', label: 'Owner' },
        { key: 'status', label: 'Status' },
        { key: 'coverage', label: 'Coverage' },
      ]}
      rows={overlayRows.map((row) => ({
        row: String(
          (row.context as Record<string, unknown> | undefined)?.row_id ??
            row.dimension ??
            '—',
        ),
        owner: String(row.owner_id ?? '—'),
        status: String(row.status ?? '—'),
        coverage: JSON.stringify(row.coverage ?? '—'),
      }))}
      rowKey={(row) => `${row.row}:${row.owner}`}
    />
  {:else if overlayStatus !== null}
    <p class="warning" role="status">Culture overlays unavailable: {overlayStatus}</p>
  {/if}
</section>

<style>
  .page { display: grid; gap: 0.9rem; }
  .eyebrow { margin: 0 0 0.2rem; font-size: 0.75rem; letter-spacing: 0.08em; text-transform: uppercase; color: #5a6a72; }
  h1 { margin: 0 0 0.3rem; font-size: 1.35rem; }
  h2 { margin: 0 0 0.25rem; font-size: 1rem; }
  .lede { margin: 0; color: #3a474e; }
  .controls { display: flex; flex-wrap: wrap; gap: 0.6rem; align-items: end; }
  label { display: grid; gap: 0.2rem; font-size: 0.8rem; color: #5a6a72; }
  input, button { font: inherit; padding: 0.25rem 0.45rem; }
  .cards { display: flex; flex-wrap: wrap; gap: 0.5rem 1.25rem; font-size: 0.85rem; }
  .cards p { margin: 0; }
  .muted { color: #5a6a72; font-size: 0.85rem; }
  .warning { margin: 0; color: #6a5420; font-size: 0.85rem; }
  .error { color: #8a3030; }
</style>
