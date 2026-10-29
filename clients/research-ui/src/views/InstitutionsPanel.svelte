<script lang="ts">
  import { untrack } from 'svelte'
  import {
    ApiClientError,
    getMetricCatalog,
    getMetricDocument,
    type MetricCatalogItem,
  } from '../api/client'
  import {
    getCivilizationCatalogue,
    getCivilizationOverlays,
  } from '../api/research'
  import EpistemicBadge from '../components/EpistemicBadge.svelte'
  import ResearchTable from '../components/research/ResearchTable.svelte'
  import {
    institutionRows,
    laneRows,
    officeClaims,
    timelineGaps,
    type InstitutionTimelineRow,
  } from '../research/institutions'
  import type { ResearchSelection } from '../research/selection'
  import LineagePanel from './LineagePanel.svelte'

  interface Props {
    runId: string
    selection?: ResearchSelection
    onSelectionChange?: (
      patch: Partial<ResearchSelection>,
      historyMode?: 'push' | 'replace',
    ) => void
  }

  let {
    runId,
    selection = undefined,
    onSelectionChange = undefined,
  }: Props = $props()

  let mode = $state<'timeline' | 'succession' | 'lineage'>('timeline')
  let evidence = $state<'ANALYTICAL' | 'SUBJECTIVE' | 'OBJECTIVE'>('ANALYTICAL')
  let ownerId = $state(untrack(() => selection?.scopeOwnerId ?? ''))
  let timelineRows = $state<InstitutionTimelineRow[]>([])
  let timelineStatus = $state<string>('unavailable')
  let timelineReason = $state<string | null>(null)
  let timelineTick = $state<number | null>(untrack(() => selection?.tick ?? null))

  $effect(() => {
    ownerId = selection?.scopeOwnerId ?? ''
  })

  $effect(() => {
    timelineTick = selection?.tick ?? null
  })

  const INSTITUTION_FAMILIES = [
    'institution_emergence',
    'institutional_persistence',
  ] as const

  type InstitutionCard = {
    family: string
    availability: string
    values: Array<{ key: string; value: string }>
    reason?: string
  }

  let cards = $state<InstitutionCard[]>([])
  let availability = $state('unavailable')
  let loading = $state(true)
  let error = $state<string | null>(null)

  function extractValues(payload: unknown): Array<{ key: string; value: string }> {
    if (payload === null || typeof payload !== 'object') {
      return []
    }
    const record = payload as Record<string, unknown>
    const values = record.values
    if (values === null || typeof values !== 'object') {
      return []
    }
    return Object.entries(values as Record<string, unknown>)
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([key, value]) => ({
        key,
        value: value === null ? 'unknown' : String(value),
      }))
  }

  async function loadCard(item: MetricCatalogItem): Promise<InstitutionCard> {
    try {
      const doc = await getMetricDocument(
        runId,
        item.metric_set_id,
        item.metric_family,
      )
      let values: Array<{ key: string; value: string }> = []
      try {
        values = extractValues(JSON.parse(atob(doc.payload_b64)) as unknown)
      } catch {
        values = []
      }
      return {
        family: item.metric_family,
        availability: doc.availability,
        values,
      }
    } catch (err) {
      return {
        family: item.metric_family,
        availability: 'unavailable',
        values: [],
        reason: err instanceof ApiClientError ? err.code : 'fetch_failed',
      }
    }
  }

  async function load(): Promise<void> {
    loading = true
    error = null
    try {
      const catalog = await getMetricCatalog(runId)
      availability = catalog.availability
      const items = INSTITUTION_FAMILIES.flatMap((family) =>
        catalog.items.filter((item) => item.metric_family === family),
      )
      cards = await Promise.all(items.map(loadCard))
    } catch (err) {
      error = err instanceof ApiClientError ? err.code : 'fetch_failed'
      cards = []
    } finally {
      loading = false
    }
  }

  $effect(() => {
    void runId
    void load()
  })

  async function loadTimeline(): Promise<void> {
    timelineStatus = 'loading'
    timelineReason = null
    try {
      const catalogue = await getCivilizationCatalogue(runId, {
        evidenceClass: evidence,
        ownerId: evidence === 'OBJECTIVE' ? null : ownerId.trim() || null,
        layer: 'institutions',
        limit: 200,
      })
      const boundaries = Array.isArray(catalogue.boundaries)
        ? catalogue.boundaries
        : []
      const target =
        typeof timelineTick === 'number' &&
        boundaries.some(
          (row) =>
            row !== null &&
            typeof row === 'object' &&
            (row as Record<string, unknown>).boundary_tick === timelineTick,
        )
          ? timelineTick
          : Number(
              (boundaries.at(-1) as Record<string, unknown> | undefined)
                ?.boundary_tick ?? timelineTick ?? 0,
            )
      timelineTick = target
      const publication =
        catalogue.publication !== null && typeof catalogue.publication === 'object'
          ? (catalogue.publication as Record<string, unknown>)
          : null
      const overlay = await getCivilizationOverlays(runId, {
        tick: target,
        layer: 'institutions',
        evidenceClass: evidence,
        ownerId: evidence === 'OBJECTIVE' ? null : ownerId.trim() || null,
        publicationId:
          typeof publication?.publication_id === 'string'
            ? publication.publication_id
            : null,
        limit: 200,
      })
      if (overlay.availability === 'unavailable') {
        timelineStatus = 'unavailable'
        timelineReason = overlay.reason ?? null
        timelineRows = []
        return
      }
      const rows = Array.isArray(overlay.rows)
        ? overlay.rows.filter(
            (row): row is Record<string, unknown> =>
              row !== null && typeof row === 'object',
          )
        : []
      timelineRows = institutionRows(rows)
      timelineStatus = timelineRows.length === 0 ? 'empty' : 'available'
    } catch (err) {
      timelineStatus = err instanceof ApiClientError && err.status === 403 ? 'forbidden' : 'error'
      timelineReason = err instanceof ApiClientError ? err.code : 'fetch_failed'
      timelineRows = []
    }
  }
</script>

<section class="panel">
  <header>
    <div>
      <h1>Institutions</h1>
      <p class="lede">
        Analytical pattern bundles and persistence classifications. No
        institution type exists; these labels never enter agent cognition,
        memory, or observations.
      </p>
    </div>
    <EpistemicBadge epistemic="research_inference" />
  </header>

  <nav class="lanes" aria-label="Institution lanes">
    <button type="button" class:active={mode === 'timeline'} onclick={() => { mode = 'timeline'; void loadTimeline() }}>Timeline</button>
    <button type="button" class:active={mode === 'succession'} onclick={() => (mode = 'succession')}>Office succession</button>
    <button type="button" class:active={mode === 'lineage'} onclick={() => (mode = 'lineage')}>Institution lineage</button>
  </nav>

  {#if mode === 'timeline'}
    <div class="controls">
      <label>Evidence <select bind:value={evidence} onchange={() => void loadTimeline()}><option value="ANALYTICAL">analytical</option><option value="SUBJECTIVE">subjective</option><option value="OBJECTIVE">objective</option></select></label>
      {#if evidence !== 'OBJECTIVE'}<label>Owner <input bind:value={ownerId} /></label>{/if}
      <button type="button" onclick={() => void loadTimeline()}>Load institution timeline</button>
    </div>
    <p class="muted">
      Concepts and office claims are private beliefs; analytical episodes are
      retrospective. No institution type registry or world office authority exists.
    </p>
    {#if timelineStatus === 'unavailable'}
      <p class="muted" role="status">Institution timeline unavailable{timelineReason ? `: ${timelineReason}` : ''}.</p>
    {:else if timelineStatus === 'empty'}
      <p class="muted">Complete empty institution-like inventory at this boundary.</p>
    {:else if timelineStatus === 'error' || timelineStatus === 'forbidden'}
      <p class="muted">Institution timeline {timelineStatus}{timelineReason ? `: ${timelineReason}` : ''}.</p>
    {:else if timelineRows.length > 0}
      {#each ['concept', 'episode', 'office'] as lane (lane)}
        <section>
          <h3>{lane} lane</h3>
          <ResearchTable
            caption="{lane} rows at tick {timelineTick ?? '—'}"
            columns={[
              { key: 'native', label: 'Native ID' },
              { key: 'owner', label: 'Identity owner' },
              { key: 'status', label: 'Status' },
              { key: 'row', label: 'Row identity' },
              { key: 'tick', label: 'Evidence tick', numeric: true },
            ]}
            rows={laneRows(timelineRows, lane as 'concept' | 'episode' | 'office').map((row) => ({
              native: row.nativeId,
              owner: row.ownerId ?? 'shared',
              status: row.status,
              row: row.rowId,
              tick: row.evidenceTick,
            }))}
            rowKey={(row) => `${row.native}:${row.owner}:${row.row}`}
            emptyLabel="No rows in this lane."
          />
        </section>
      {/each}
      {#if timelineGaps(timelineRows).length > 0}
        <p class="muted">Unknown/censored bands before ticks {timelineGaps(timelineRows).join(', ')}.</p>
      {/if}
      {#if officeClaims(timelineRows).length > 0}
        <p class="muted">Office claims are shown as returned. No global current occupant is chosen by majority, confidence or recency.</p>
      {/if}
    {/if}
  {:else if mode === 'succession'}
    {#if selection !== undefined && onSelectionChange !== undefined}
      <LineagePanel {runId} {selection} {onSelectionChange} initialFamily="office_succession" />
    {/if}
  {:else}
    {#if selection !== undefined && onSelectionChange !== undefined}
      <LineagePanel {runId} {selection} {onSelectionChange} initialFamily="institution" />
    {/if}
  {/if}

  {#if loading}
    <p class="muted">Loading institution metrics…</p>
  {:else if error !== null}
    <p class="muted">Institution metrics unavailable: {error}</p>
  {:else if cards.length === 0}
    <p class="muted">
      No institution families in this run (catalog: {availability}).
    </p>
  {:else}
    <div class="grid">
      {#each cards as card (card.family)}
        <article class="card">
          <div class="card-head">
            <h3>{card.family}</h3>
            <EpistemicBadge epistemic="research_inference" />
          </div>
          <p class="muted">Availability: {card.availability}</p>
          {#if card.reason !== undefined}
            <p class="muted">Reason: {card.reason}</p>
          {/if}
          <dl>
            {#each card.values as item (item.key)}
              <dt>{item.key}</dt>
              <dd>{item.value}</dd>
            {/each}
          </dl>
        </article>
      {/each}
    </div>
  {/if}
</section>

<style>
  .panel {
    display: grid;
    gap: 1rem;
  }
  header,
  .card-head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 1rem;
  }
  .lede,
  .muted {
    color: var(--muted, #6b7280);
  }
  .grid {
    display: grid;
    gap: 1rem;
    grid-template-columns: repeat(auto-fit, minmax(18rem, 1fr));
  }
  .card {
    border: 1px solid var(--border, #d1d5db);
    border-radius: 0.5rem;
    padding: 0.75rem 1rem;
  }
  .lanes,
  .controls {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    align-items: end;
  }

  .lanes button.active {
    border-color: #2e5c6e;
    color: #2e5c6e;
    font-weight: 600;
  }

  label {
    display: grid;
    gap: 0.2rem;
    font-size: 0.8rem;
    color: #5a6a72;
  }

  input,
  select,
  button {
    font: inherit;
    padding: 0.25rem 0.45rem;
  }

  dl {
    display: grid;
    grid-template-columns: 1fr auto;
    gap: 0.25rem 0.75rem;
    font-size: 0.875rem;
  }
  dt {
    overflow-wrap: anywhere;
  }
  dd {
    margin: 0;
    font-variant-numeric: tabular-nums;
  }
</style>
