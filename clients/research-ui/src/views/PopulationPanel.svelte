<script lang="ts">
  import { onMount } from 'svelte'
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
  import type { GenerationMarker } from '../research/generationTypes'
  import type { ResearchSelection } from '../research/selection'
  import {
    demographicNotice,
    generationBars,
    populationSeries,
    stageBars,
    type BoundarySample,
  } from '../research/population'
  import { BoundedRequestPool } from '../research/requests'
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

  let run = $state<ObserverRunOut | null>(null)
  let highWaterState = new MarkerHighWater()
  let highWater = $state<number | null>(null)
  let markers = $state<GenerationMarker[]>([])
  let markerStatus = $state<'loading' | 'available' | 'unavailable' | 'error'>(
    'loading',
  )
  let markerReason = $state<string | null>(null)
  let summary = $state<DemographicsEnvelope | null>(null)
  let summaryReason = $state<string | null>(null)
  let samples = $state<BoundarySample[]>([])
  let rangeMode = $state<'selected' | 'full'>('selected')
  let sampled = $state(false)
  let omitted = $state(0)
  let loading = $state(true)
  let error = $state<string | null>(null)
  let agentEnvelope = $state<DemographicsEnvelope | null>(null)
  let cohortEnvelope = $state<DemographicsEnvelope | null>(null)
  let agentsCursor = $state<string | null>(null)
  let cohortsCursor = $state<string | null>(null)
  let agentLoading = $state(false)
  let cohortLoading = $state(false)
  let requestEpoch = 0
  let controller: AbortController | null = null
  const pool = new BoundedRequestPool(4)

  const effectiveTick = $derived(selection.tick ?? run?.tick ?? 0)

  const populationNotice = $derived(demographicNotice(summary, summaryReason))

  const stageRows = $derived(stageBars(summary))
  const generationRows = $derived(generationBars(summary))

  const chartSeries = $derived(populationSeries(samples))

  onMount(() => {
    void loadRun()
  })

  $effect(() => {
    if (runId !== '' && run !== null) {
      void loadBoundary(effectiveTick, rangeMode)
    }
  })

  async function loadRun(): Promise<void> {
    loading = true
    error = null
    try {
      const loaded = await getObserverRun(runId)
      run = loaded
      const observed = highWaterState.observe(
        runId,
        loaded,
        0,
        0,
      )
      highWater = observed.highWater
      await loadMarkers(false)
      await loadBoundary(effectiveTick, rangeMode)
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
    const next = highWaterState.refresh(runId, run, 0, 0)
    highWater = next.highWater
    await loadMarkers(true)
  }

  async function loadMarkers(changed: boolean): Promise<void> {
    const target = highWater
    if (target === null) {
      markerStatus = 'unavailable'
      markerReason = 'high_water_unavailable'
      return
    }
    markerStatus = 'loading'
    markerReason = null
    const collected: GenerationMarker[] = []
    let after: number | null = null
    let revision: number | null = null
    let pages = 0
    try {
      while (pages < 25) {
        pages += 1
        const page = await getGenerationMarkers(runId, {
          tick: target,
          afterGenerationIndex: after,
          limit: 200,
        })
        if (!changed && revision !== null && page.revision !== revision) {
          markers = []
          markerStatus = 'loading'
          markerReason = 'revision_changed'
          return
        }
        revision = page.revision
        if (page.availability === 'unavailable') {
          markerStatus = 'unavailable'
          markerReason = page.reason_code
          markers = []
          return
        }
        collected.push(...page.markers)
        if (page.next_after_generation_index === null) {
          break
        }
        if (!highWaterState.acceptsContinuation(target)) {
          markerStatus = 'error'
          markerReason = 'mixed_high_water'
          return
        }
        after = page.next_after_generation_index
      }
      markers = collected
      markerStatus = 'available'
    } catch (err) {
      markerStatus = 'error'
      markerReason = err instanceof ApiClientError ? err.code : 'marker_fetch_failed'
    }
  }

  async function loadBoundary(
    tick: number,
    mode: 'selected' | 'full',
  ): Promise<void> {
    if (run === null) {
      return
    }
    const epoch = ++requestEpoch
    controller?.abort()
    controller = new AbortController()
    loading = true
    error = null
    try {
      const summaryPage = await getDemographics(
        runId,
        { tick, section: 'generations', limit: 200 },
        controller.signal,
      )
      if (epoch !== requestEpoch) {
        return
      }
      summary = summaryPage
      summaryReason = summaryPage.reason_code
      cohortEnvelope = null
      cohortsCursor = null
      agentEnvelope = null
      agentsCursor = null

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
                  controller?.signal,
                )
                if (epoch !== requestEpoch) {
                  return { tick: sampleTick, envelope: null }
                }
                return { tick: sampleTick, envelope }
              } catch {
                return { tick: sampleTick, envelope: null }
              }
            }),
          ),
        )
        if (epoch === requestEpoch) {
          samples = loaded
        }
      }
    } catch (err) {
      if (epoch !== requestEpoch) {
        return
      }
      error =
        err instanceof DOMException
          ? null
          : err instanceof ApiClientError
            ? err.code
            : 'fetch_failed'
    } finally {
      if (epoch === requestEpoch) {
        loading = false
      }
    }
  }

  async function loadAgents(more = false): Promise<void> {
    agentLoading = true
    try {
      const page = await getDemographics(runId, {
        tick: effectiveTick,
        section: 'agents',
        afterAgentId: more ? agentsCursor : null,
        limit: 100,
      })
      agentEnvelope =
        more && agentEnvelope !== null
          ? {
              ...page,
              agents: [...agentEnvelope.agents, ...page.agents],
            }
          : page
      agentsCursor = page.next_after_agent_id
    } catch (err) {
      error = err instanceof ApiClientError ? err.code : 'fetch_failed'
    } finally {
      agentLoading = false
    }
  }

  async function loadCohorts(more = false): Promise<void> {
    cohortLoading = true
    try {
      const page = await getDemographics(runId, {
        tick: effectiveTick,
        section: 'cohorts',
        afterGroupKey: more ? cohortsCursor : null,
        limit: 100,
      })
      cohortEnvelope =
        more && cohortEnvelope !== null
          ? {
              ...page,
              cohorts: [...cohortEnvelope.cohorts, ...page.cohorts],
            }
          : page
      cohortsCursor = page.next_after_group_key
    } catch (err) {
      error = err instanceof ApiClientError ? err.code : 'fetch_failed'
    } finally {
      cohortLoading = false
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
    {#if agentEnvelope === null}
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
        rows={agentEnvelope.agents.map((agent) => ({
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
      {#if agentEnvelope.agents.some((agent) => agent.life_status === 'dead' && agent.age_ticks === null)}
        <p class="muted">Dead age is unknown when the server does not project it.</p>
      {/if}
      {#if agentsCursor !== null}
        <button type="button" onclick={() => void loadAgents(true)} disabled={agentLoading}>
          Load more agents
        </button>
      {/if}
    {/if}
  </section>

  <section>
    <h2>Cohorts at tick {effectiveTick}</h2>
    {#if cohortEnvelope === null}
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
        rows={cohortEnvelope.cohorts.map((cohort) => ({
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
      {#if cohortsCursor !== null}
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
