<script lang="ts">
  import { onDestroy, onMount, untrack } from 'svelte'
  import {
    ApiClientError,
    getObserverRun,
    type ObserverRunOut,
  } from '../api/client'
  import {
    getDemographics,
    getGenerationMarkers,
  } from '../api/research'
  import AvailabilityNotice from '../components/research/AvailabilityNotice.svelte'
  import EvidenceLegend from '../components/research/EvidenceLegend.svelte'
  import GenerationNavigator from '../components/research/GenerationNavigator.svelte'
  import MetricCard from '../components/research/MetricCard.svelte'
  import ResearchTable from '../components/research/ResearchTable.svelte'
  import SeriesChart from '../components/research/SeriesChart.svelte'
  import type { DemographicsEnvelope } from '../api/researchSchemas'
  import { credentialGeneration } from '../auth/credentials'
  import type { GenerationMarker } from '../research/generationTypes'
  import type { ResearchSelection } from '../research/selection'
  import {
    demographicNotice,
    generationBars,
    populationSeries,
    stageBars,
    type BoundarySample,
  } from '../research/population'
  import { ExplicitPager, type PagerState } from '../research/paging'
  import {
    BoundedRequestPool,
    ResearchScopeController,
  } from '../research/requests'
  import {
    MarkerHighWater,
    pinHighWater,
    sampleBoundaries,
  } from '../research/sampling'

  interface Props {
    runId: string
    selection: ResearchSelection
    onSelectionChange: (
      patch: Partial<ResearchSelection>,
      historyMode?: 'push' | 'replace',
    ) => void
  }

  let { runId, selection, onSelectionChange }: Props = $props()

  type AgentRow = DemographicsEnvelope['agents'][number]
  type CohortRow = DemographicsEnvelope['cohorts'][number]

  const MAX_MARKER_ROWS = 5000
  const MAX_AGENT_ROWS = 2000
  const MAX_COHORT_ROWS = 2000

  let run = $state<ObserverRunOut | null>(null)
  let highWaterState = new MarkerHighWater()
  let highWater = $state<number | null>(null)
  let markers = $state<GenerationMarker[]>([])
  let markerStatus = $state<'loading' | 'available' | 'unavailable' | 'error'>(
    'loading',
  )
  let markerReason = $state<string | null>(null)
  let markerHasMore = $state(false)
  let markerLimited = $state(false)
  let markerRevision = 0
  let markerPager: ExplicitPager<GenerationMarker> | null = null
  let summary = $state<DemographicsEnvelope | null>(null)
  let summaryReason = $state<string | null>(null)
  let samples = $state<BoundarySample[]>([])
  let rangeMode = $state<'selected' | 'full'>('selected')
  let sampled = $state(false)
  let omitted = $state(0)
  let loading = $state(true)
  let error = $state<string | null>(null)
  let agentRows = $state<AgentRow[]>([])
  let cohortRows = $state<CohortRow[]>([])
  let agentHasMore = $state(false)
  let agentLimited = $state(false)
  let cohortHasMore = $state(false)
  let cohortLimited = $state(false)
  let agentPager = $state<ExplicitPager<AgentRow> | null>(null)
  let cohortPager = $state<ExplicitPager<CohortRow> | null>(null)
  let agentLoading = $state(false)
  let cohortLoading = $state(false)
  let boundaryEpoch = 0
  let agentEpoch = 0
  let cohortEpoch = 0
  let markerEpoch = 0
  let boundaryAbort: AbortController | null = null
  let scopeEpoch = 0
  let scopeTick: number | null = null
  let scopeController: ResearchScopeController | null = null
  const pool = new BoundedRequestPool(4, 16)

  const effectiveTick = $derived(selection.tick ?? run?.tick ?? 0)

  const populationNotice = $derived(demographicNotice(summary, summaryReason))

  const stageRows = $derived(stageBars(summary))
  const generationRows = $derived(generationBars(summary))

  const chartSeries = $derived(populationSeries(samples))

  class PagerUnavailable extends Error {
    readonly reason: string

    constructor(reason: string) {
      super(reason)
      this.name = 'PagerUnavailable'
      this.reason = reason
    }
  }

  onMount(() => {
    void loadRun()
  })

  onDestroy(() => {
    scopeController?.dispose()
    scopeController = null
    boundaryAbort?.abort()
    boundaryAbort = null
  })

  $effect(() => {
    if (runId !== '' && run !== null) {
      syncScope(effectiveTick)
    }
  })

  function scopeFor(tick: number) {
    return {
      runId,
      view: 'population',
      tick,
      evidenceClass: 'objective',
      ownerId: null,
      publicationId: null,
    }
  }

  function syncScope(tick: number): void {
    if (scopeController === null) {
      scopeController = new ResearchScopeController(scopeFor(tick))
      scopeController.onReset(handleScopeReset)
      scopeTick = tick
      pool.setScope(scopeEpoch)
      return
    }
    if (scopeTick === tick) {
      return
    }
    scopeTick = tick
    scopeController.setScope(scopeFor(tick))
  }

  function handleScopeReset(): void {
    scopeEpoch += 1
    pool.setScope(scopeEpoch)
    boundaryEpoch += 1
    boundaryAbort?.abort()
    boundaryAbort = null
    summary = null
    summaryReason = null
    samples = []
    sampled = false
    omitted = 0
    resetAgentRows()
    resetCohortRows()
    markerEpoch += 1
    markerPager = null
    markers = []
    markerHasMore = false
    markerLimited = false
    if (run !== null) {
      void loadMarkers(false)
      void loadBoundary(effectiveTick, untrack(() => rangeMode))
    }
  }

  function resetAgentRows(): void {
    agentEpoch += 1
    agentPager = null
    agentRows = []
    agentHasMore = false
    agentLimited = false
  }

  function resetCohortRows(): void {
    cohortEpoch += 1
    cohortPager = null
    cohortRows = []
    cohortHasMore = false
    cohortLimited = false
  }

  async function loadRun(): Promise<void> {
    loading = true
    error = null
    try {
      const loaded = await getObserverRun(runId)
      run = loaded
      highWater = pinHighWater(loaded)
      syncScope(untrack(() => effectiveTick))
      await loadMarkers(false)
      await loadBoundary(effectiveTick, untrack(() => rangeMode))
    } catch (err) {
      error = err instanceof ApiClientError ? err.code : 'fetch_failed'
    } finally {
      loading = false
    }
  }

  async function refreshHighWater(): Promise<void> {
    if (run === null) {
      return
    }
    try {
      const loaded = await getObserverRun(runId)
      run = loaded
      highWater = pinHighWater(loaded)
      await loadMarkers(true)
    } catch (err) {
      markerStatus = 'error'
      markerReason = err instanceof ApiClientError ? err.code : 'marker_fetch_failed'
    }
  }

  function createMarkerPager(target: number): ExplicitPager<GenerationMarker> {
    return new ExplicitPager<GenerationMarker>(
      async (cursor) => {
        const token = scopeController!.currentToken()
        const page = await pool.run(
          () =>
            getGenerationMarkers(
              runId,
              {
                tick: target,
                afterGenerationIndex: cursor === null ? null : Number(cursor),
                limit: 200,
              },
              token.signal,
            ),
          scopeEpoch,
        )
        const accepted = scopeController!.accept(token, page)
        markerRevision = accepted.revision
        if (accepted.availability === 'unavailable') {
          throw new PagerUnavailable(
            accepted.reason_code ?? 'generation_markers_unavailable',
          )
        }
        return {
          items: accepted.markers,
          nextCursor:
            accepted.next_after_generation_index === null
              ? null
              : String(accepted.next_after_generation_index),
          publicationId: String(accepted.revision),
        }
      },
      {
        keyOf: (marker) => String(marker.generation_index),
        maxItems: MAX_MARKER_ROWS,
      },
    )
  }

  function applyMarkerState(
    pager: ExplicitPager<GenerationMarker>,
    state: PagerState<GenerationMarker>,
  ): void {
    markerPager = pager
    markers = [...state.items]
    markerHasMore = state.nextCursor !== null || state.limited
    markerLimited = state.limited
    if (state.stopReason === 'publication_changed') {
      markers = []
      markerStatus = 'error'
      markerReason = 'revision_changed'
      return
    }
    if (state.stopReason === 'fetch_error') {
      markerStatus = 'error'
      markerReason = 'marker_fetch_failed'
      return
    }
    markerStatus = 'available'
  }

  async function loadMarkers(changed: boolean): Promise<void> {
    if (run === null) {
      return
    }
    const epoch = ++markerEpoch
    markerStatus = 'loading'
    markerReason = null
    try {
      let target = changed
        ? pinHighWater(run)
        : (highWater ?? pinHighWater(run))
      let pager = createMarkerPager(target)
      let state = await pager.loadMore()
      if (epoch !== markerEpoch) {
        return
      }
      const observed = changed
        ? highWaterState.refresh(
            runId,
            run,
            markerRevision,
            credentialGeneration(),
          )
        : highWaterState.observe(
            runId,
            run,
            markerRevision,
            credentialGeneration(),
          )
      if (observed.highWater !== target) {
        target = observed.highWater
        pager = createMarkerPager(target)
        state = await pager.loadMore()
        if (epoch !== markerEpoch) {
          return
        }
      }
      highWater = observed.highWater
      applyMarkerState(pager, state)
    } catch (err) {
      if (epoch !== markerEpoch) {
        return
      }
      markerStatus = 'error'
      markerReason =
        err instanceof PagerUnavailable
          ? err.reason
          : err instanceof ApiClientError
            ? err.code
            : 'marker_fetch_failed'
    }
  }

  async function continueMarkers(): Promise<void> {
    if (markerPager === null) {
      return
    }
    const epoch = ++markerEpoch
    markerStatus = 'loading'
    markerReason = null
    try {
      const state = await markerPager.loadMore()
      if (epoch !== markerEpoch) {
        return
      }
      applyMarkerState(markerPager, state)
    } catch (err) {
      if (epoch !== markerEpoch) {
        return
      }
      markerStatus = 'error'
      markerReason = err instanceof ApiClientError ? err.code : 'marker_fetch_failed'
    }
  }

  function createAgentPager(tick: number): ExplicitPager<AgentRow> {
    return new ExplicitPager<AgentRow>(
      async (cursor) => {
        const token = scopeController!.currentToken()
        const page = await pool.run(
          () =>
            getDemographics(
              runId,
              {
                tick,
                section: 'agents',
                afterAgentId: cursor,
                limit: 100,
              },
              token.signal,
            ),
          scopeEpoch,
        )
        const accepted = scopeController!.accept(token, page)
        if (accepted.availability === 'unavailable') {
          throw new PagerUnavailable(
            accepted.reason_code ?? 'demographics_unavailable',
          )
        }
        return {
          items: accepted.agents,
          nextCursor: accepted.next_after_agent_id,
          publicationId: `${accepted.resolved_tick}:${accepted.revision}`,
        }
      },
      {
        keyOf: (row) => row.agent_id,
        fingerprintOf: (row) => `${row.life_status}:${row.age_ticks ?? 'null'}`,
        maxItems: MAX_AGENT_ROWS,
      },
    )
  }

  function createCohortPager(tick: number): ExplicitPager<CohortRow> {
    return new ExplicitPager<CohortRow>(
      async (cursor) => {
        const token = scopeController!.currentToken()
        const page = await pool.run(
          () =>
            getDemographics(
              runId,
              {
                tick,
                section: 'cohorts',
                afterGroupKey: cursor,
                limit: 100,
              },
              token.signal,
            ),
          scopeEpoch,
        )
        const accepted = scopeController!.accept(token, page)
        if (accepted.availability === 'unavailable') {
          throw new PagerUnavailable(
            accepted.reason_code ?? 'demographics_unavailable',
          )
        }
        return {
          items: accepted.cohorts,
          nextCursor: accepted.next_after_group_key,
          publicationId: `${accepted.resolved_tick}:${accepted.revision}`,
        }
      },
      {
        keyOf: (row) =>
          `${row.generation_index}:${row.entry_tick}:${row.cohort_id}`,
        maxItems: MAX_COHORT_ROWS,
      },
    )
  }

  async function loadBoundary(
    tick: number,
    mode: 'selected' | 'full',
  ): Promise<void> {
    if (run === null || scopeController === null) {
      return
    }
    const epoch = ++boundaryEpoch
    boundaryAbort?.abort()
    boundaryAbort = new AbortController()
    const token = scopeController.currentToken()
    const signal = boundaryAbort.signal
    loading = true
    error = null
    try {
      const summaryPage = await getDemographics(
        runId,
        { tick, section: 'generations', limit: 200 },
        signal,
      )
      if (
        epoch !== boundaryEpoch ||
        !scopeController.isCurrent(token)
      ) {
        return
      }
      summary = summaryPage
      summaryReason = summaryPage.reason_code
      resetAgentRows()
      resetCohortRows()

      if (mode === 'selected') {
        samples = [{ tick, envelope: summaryPage }]
        sampled = false
        omitted = 0
      } else {
        const range = { fromTick: 0, toTick: tick }
        const result = sampleBoundaries(
          markers.map((marker) => ({
            generationIndex: marker.generation_index,
            seekTick: marker.seek_tick,
          })),
          range,
          32,
        )
        sampled = result.sampled
        omitted = result.omittedCount
        const loaded = await Promise.all(
          result.ticks.map((sampleTick) =>
            pool.run(async () => {
              try {
                const envelope = await getDemographics(
                  runId,
                  { tick: sampleTick, section: 'generations', limit: 1 },
                  signal,
                )
                if (
                  epoch !== boundaryEpoch ||
                  !scopeController!.isCurrent(token)
                ) {
                  return { tick: sampleTick, envelope: null }
                }
                return { tick: sampleTick, envelope }
              } catch {
                return { tick: sampleTick, envelope: null }
              }
            }, scopeEpoch),
          ),
        )
        if (epoch === boundaryEpoch) {
          samples = loaded
        }
      }
    } catch (err) {
      if (epoch !== boundaryEpoch) {
        return
      }
      error =
        err instanceof DOMException
          ? null
          : err instanceof ApiClientError
            ? err.code
            : 'fetch_failed'
    } finally {
      if (epoch === boundaryEpoch) {
        loading = false
      }
    }
  }

  async function loadAgents(more = false): Promise<void> {
    if (scopeController === null) {
      return
    }
    const epoch = ++agentEpoch
    agentLoading = true
    agentHasMore = false
    try {
      if (!more || agentPager === null) {
        agentRows = []
        agentPager = createAgentPager(effectiveTick)
      }
      const state = await agentPager.loadMore()
      if (epoch !== agentEpoch) {
        return
      }
      agentRows = [...state.items]
      agentHasMore = state.nextCursor !== null || state.limited
      agentLimited = state.limited
      if (state.stopReason === 'publication_changed') {
        error = 'boundary_changed'
      } else if (state.stopReason === 'fetch_error') {
        error = 'fetch_failed'
      }
    } catch (err) {
      if (epoch !== agentEpoch) {
        return
      }
      error =
        err instanceof PagerUnavailable
          ? err.reason
          : err instanceof ApiClientError
            ? err.code
            : 'fetch_failed'
    } finally {
      if (epoch === agentEpoch) {
        agentLoading = false
      }
    }
  }

  async function loadCohorts(more = false): Promise<void> {
    if (scopeController === null) {
      return
    }
    const epoch = ++cohortEpoch
    cohortLoading = true
    cohortHasMore = false
    try {
      if (!more || cohortPager === null) {
        cohortRows = []
        cohortPager = createCohortPager(effectiveTick)
      }
      const state = await cohortPager.loadMore()
      if (epoch !== cohortEpoch) {
        return
      }
      cohortRows = [...state.items]
      cohortHasMore = state.nextCursor !== null || state.limited
      cohortLimited = state.limited
      if (state.stopReason === 'publication_changed') {
        error = 'boundary_changed'
      } else if (state.stopReason === 'fetch_error') {
        error = 'fetch_failed'
      }
    } catch (err) {
      if (epoch !== cohortEpoch) {
        return
      }
      error =
        err instanceof PagerUnavailable
          ? err.reason
          : err instanceof ApiClientError
            ? err.code
            : 'fetch_failed'
    } finally {
      if (epoch === cohortEpoch) {
        cohortLoading = false
      }
    }
  }

  function selectAgent(agentId: string): void {
    onSelectionChange({
      view: 'agent',
      tick: effectiveTick,
      focus: { kind: 'agent', source: 'objective', agentId },
    })
  }

  function selectPoint(tick: number): void {
    onSelectionChange({ tick }, 'replace')
  }

  function toggleRange(): void {
    rangeMode = rangeMode === 'selected' ? 'full' : 'selected'
    void loadBoundary(effectiveTick, rangeMode)
  }
</script>

<section class="page">
  <header class="head">
    <div>
      <p class="eyebrow">Population</p>
      <h1>Population and demographics</h1>
      <p class="lede">
        Objective census at finalized boundaries. Cohort is not biological
        kinship; sparse samples are not birth or death rates.
      </p>
    </div>
  </header>

  <GenerationNavigator
    {selection}
    {markers}
    {highWater}
    {markerStatus}
    {markerReason}
    {onSelectionChange}
    onRefreshMarkers={() => void refreshHighWater()}
  />

  {#if markerHasMore || markerLimited}
    <div class="actions" role="status">
      <span class="muted">
        Generation discovery is bounded: {markers.length} markers retained
        {markerLimited ? 'at the local cap' : 'with a server continuation'}.
        Discovery is incomplete until the continuation is drained.
      </span>
      <button type="button" onclick={() => void continueMarkers()}>
        Load more generations
      </button>
    </div>
  {/if}

  <div class="actions">
    <button type="button" onclick={toggleRange}>
      {rangeMode === 'selected' ? 'Load full history sample' : 'Show selected boundary only'}
    </button>
    {#if sampled}
      <span class="muted">
        Deterministic sample: {samples.length} boundaries, {omitted} omitted.
      </span>
    {/if}
  </div>

  {#if error !== null}
    <p class="status error" role="alert">{error}</p>
  {/if}

  <AvailabilityNotice
    status={loading ? 'loading' : populationNotice.status}
    reason={populationNotice.reason}
    requestedTick={selection.tick}
    resolvedTick={summary?.resolved_tick ?? null}
  />

  {#if summary !== null}
    <div class="cards">
      <MetricCard
        label="Living"
        value={String(summary.population?.living ?? 0)}
        unit="agents"
        evidenceClass="objective_world"
        note={`resolved tick ${summary.resolved_tick}`}
      />
      <MetricCard
        label="Admitted"
        value={String(summary.population?.admitted ?? 0)}
        unit="agents"
        evidenceClass="objective_world"
      />
      <MetricCard
        label="Dead"
        value={String(summary.population?.dead ?? 0)}
        unit="agents"
        evidenceClass="objective_world"
      />
      <MetricCard
        label="Maximum generation"
        value={String(summary.population?.max_generation_index ?? '—')}
        evidenceClass="objective_world"
      />
    </div>
  {/if}

  <SeriesChart
    title="Population timeline"
    description="Admitted, living and dead totals at sampled finalized boundaries. Gaps are unknown, not zero."
    series={chartSeries}
    onPointSelect={selectPoint}
  />

  <EvidenceLegend
    entries={[
      {
        label: 'Population totals',
        evidenceClass: 'objective_world',
        source: 'observer-demographics-v1',
        window: `tick ${samples[0]?.tick ?? '—'}–${samples.at(-1)?.tick ?? '—'}`,
      },
    ]}
  />

  <div class="split">
    <section>
      <h2>Stage and life status</h2>
      {#if summary?.stage_counts_truncated}
        <p class="status partial" role="status">
          Stage counts are truncated by the server; shown counts are partial.
        </p>
      {/if}
      <ResearchTable
        caption="Stage distribution"
        columns={[
          { key: 'stage', label: 'Stage' },
          { key: 'lifeStatus', label: 'Life status' },
          { key: 'count', label: 'Count', numeric: true },
        ]}
        rows={stageRows.map((row) => ({
          stage: row.stage,
          lifeStatus: row.lifeStatus,
          count: row.count,
        }))}
        rowKey={(row) => `${row.stage}:${row.lifeStatus}`}
      />
    </section>
    <section>
      <h2>Generation distribution</h2>
      <ResearchTable
        caption="Admitted, living and dead by generation"
        columns={[
          { key: 'generationIndex', label: 'Generation', numeric: true },
          { key: 'admitted', label: 'Admitted', numeric: true },
          { key: 'living', label: 'Living', numeric: true },
          { key: 'dead', label: 'Dead', numeric: true },
        ]}
        rows={generationRows.map((row) => ({
          generationIndex: row.generationIndex,
          admitted: row.admitted,
          living: row.living,
          dead: row.dead,
        }))}
        rowKey={(row) => String(row.generationIndex)}
      />
    </section>
  </div>

  <section>
    <h2>Agents at tick {effectiveTick}</h2>
    {#if agentPager === null}
      <button type="button" onclick={() => void loadAgents(false)}>
        Load agent page
      </button>
    {:else}
      <ResearchTable
        caption="Demographic agent rows"
        columns={[
          { key: 'agentId', label: 'Agent' },
          { key: 'generationIndex', label: 'Generation', numeric: true },
          { key: 'entryTick', label: 'Entry tick', numeric: true },
          { key: 'cohortId', label: 'Cohort' },
          { key: 'stage', label: 'Stage' },
          { key: 'lifeStatus', label: 'Life status' },
          { key: 'ageTicks', label: 'Age (ticks)', numeric: true },
        ]}
        rows={agentRows.map((agent) => ({
          agentId: agent.agent_id,
          generationIndex: agent.generation_index,
          entryTick: agent.entry_tick,
          cohortId: agent.cohort_id,
          stage: agent.stage,
          lifeStatus: agent.life_status,
          ageTicks: agent.age_ticks,
        }))}
        rowKey={(row) => String(row.agentId)}
        onRowSelect={(row) => selectAgent(String(row.agentId))}
      />
      {#if agentRows.some((agent) => agent.life_status === 'dead' && agent.age_ticks === null)}
        <p class="muted">Dead age is unknown when the server does not project it.</p>
      {/if}
      {#if agentLimited}
        <p class="status partial" role="status">
          Local row cap reached for this window. Load more to drain the buffered
          suffix before any later server page is requested.
        </p>
      {/if}
      {#if agentHasMore}
        <button type="button" onclick={() => void loadAgents(true)} disabled={agentLoading}>
          Load more agents
        </button>
      {/if}
    {/if}
  </section>

  <section>
    <h2>Cohorts at tick {effectiveTick}</h2>
    {#if cohortPager === null}
      <button type="button" onclick={() => void loadCohorts(false)}>
        Load cohort page
      </button>
    {:else}
      <ResearchTable
        caption="Cohort census rows"
        columns={[
          { key: 'generationIndex', label: 'Generation', numeric: true },
          { key: 'entryTick', label: 'Entry tick', numeric: true },
          { key: 'cohortId', label: 'Cohort' },
          { key: 'admitted', label: 'Admitted', numeric: true },
          { key: 'living', label: 'Living', numeric: true },
          { key: 'dead', label: 'Dead', numeric: true },
        ]}
        rows={cohortRows.map((cohort) => ({
          generationIndex: cohort.generation_index,
          entryTick: cohort.entry_tick,
          cohortId: cohort.cohort_id,
          admitted: cohort.admitted,
          living: cohort.living,
          dead: cohort.dead,
        }))}
        rowKey={(row) =>
          `${row.generationIndex}:${row.entryTick}:${row.cohortId}`}
      />
      {#if cohortLimited}
        <p class="status partial" role="status">
          Local row cap reached for this window. Load more to drain the buffered
          suffix before any later server page is requested.
        </p>
      {/if}
      {#if cohortHasMore}
        <button type="button" onclick={() => void loadCohorts(true)} disabled={cohortLoading}>
          Load more cohorts
        </button>
      {/if}
    {/if}
  </section>
</section>

<style>
  .page {
    display: grid;
    gap: 1rem;
  }

  .head h1 {
    margin: 0 0 0.3rem;
    font-size: 1.4rem;
  }

  .eyebrow {
    margin: 0 0 0.2rem;
    font-size: 0.75rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #5a6a72;
  }

  .lede {
    margin: 0;
    color: #3a474e;
  }

  .actions {
    display: flex;
    gap: 0.75rem;
    align-items: center;
    flex-wrap: wrap;
  }

  .cards {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(9rem, 1fr));
    gap: 0.6rem;
  }

  .split {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(18rem, 1fr));
    gap: 1rem;
  }

  h2 {
    margin: 0 0 0.35rem;
    font-size: 1rem;
  }

  .muted {
    color: #5a6a72;
    font-size: 0.85rem;
  }

  .partial {
    color: #6a5420;
  }

  .error {
    color: #8a3030;
  }

  button {
    font: inherit;
    padding: 0.25rem 0.55rem;
    cursor: pointer;
  }
</style>
