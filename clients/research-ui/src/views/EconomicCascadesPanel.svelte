<script lang="ts">
  import { ApiClientError } from '../api/client'
  import {
    getEconomicCascadesChains,
    getEconomicCascadesCoverage,
    getEconomicCascadesDependencies,
    getEconomicCascadesDisruptions,
    getEconomicCascadesPropagation,
    getEconomicCascadesSummary,
    type EconomicCascadeChainRow,
    type EconomicCascadeCoverageRow,
    type EconomicCascadeDependencyRow,
    type EconomicCascadeDisruptionRow,
    type EconomicCascadePropagationRow,
    type EconomicCascadesSummary,
  } from '../api/economicCascades'
  import type { ResearchSelection } from '../research/selection'

  interface Props {
    runId: string
    selection: ResearchSelection
  }

  let { runId }: Props = $props()

  type Status = 'loading' | 'ready' | 'empty' | 'unavailable' | 'error'
  let status = $state<Status>('loading')
  let reason = $state<string | null>(null)
  let summary = $state<EconomicCascadesSummary | null>(null)
  let disruptions = $state<EconomicCascadeDisruptionRow[]>([])
  let dependencies = $state<EconomicCascadeDependencyRow[]>([])
  let chains = $state<EconomicCascadeChainRow[]>([])
  let propagation = $state<EconomicCascadePropagationRow[]>([])
  let coverage = $state<EconomicCascadeCoverageRow | null>(null)
  let windowInput = $state('')

  function label(value: string | null | undefined): string {
    return value ? value.replaceAll('_', ' ') : 'unknown'
  }

  function windowIndex(): number | undefined {
    const raw = String(windowInput ?? '')
    if (raw.trim() === '') return undefined
    const parsed = Number(raw)
    return Number.isInteger(parsed) && parsed >= 0 && parsed <= 511
      ? parsed
      : undefined
  }

  async function load(): Promise<void> {
    status = 'loading'
    reason = null
    const index = windowIndex()
    try {
      summary = await getEconomicCascadesSummary(runId)
      const [
        disruptionPage,
        dependencyPage,
        chainPage,
        propagationPage,
        coveragePage,
      ] = await Promise.all([
        getEconomicCascadesDisruptions(runId, { windowIndex: index }),
        getEconomicCascadesDependencies(runId, { windowIndex: index }),
        getEconomicCascadesChains(runId, { windowIndex: index }),
        getEconomicCascadesPropagation(runId, { windowIndex: index }),
        getEconomicCascadesCoverage(runId, { windowIndex: index }),
      ])
      disruptions = disruptionPage.rows
      dependencies = dependencyPage.rows
      chains = chainPage.rows
      propagation = propagationPage.rows
      coverage = coveragePage.rows[0] ?? null
      status =
        disruptions.length +
          dependencies.length +
          chains.length +
          propagation.length >
        0
          ? 'ready'
          : 'empty'
    } catch (error) {
      if (error instanceof ApiClientError) {
        reason = error.code
        status =
          error.code === 'economic_cascades_disabled' || error.code === 'http_503'
            ? 'unavailable'
            : 'error'
      } else {
        reason = error instanceof Error ? error.message : 'error'
        status = 'error'
      }
    }
  }

  $effect(() => {
    void runId
    void load()
  })
</script>

<section class="economic-cascades" data-testid="economic-cascades-panel">
  <header>
    <h2>Economic cascades</h2>
    {#if summary}
      <p class="meta">
        {summary.window_count} windows · {summary.disruption_count} disruption records ·
        {summary.chain_count} chains · {label(summary.coverage)}
      </p>
    {/if}
    <label>
      Window
      <input
        bind:value={windowInput}
        inputmode="numeric"
        placeholder="all"
        aria-label="Window index"
      />
    </label>
  </header>

  {#if status === 'loading'}
    <p>loading</p>
  {:else if status === 'unavailable'}
    <p>unavailable — {reason ?? 'economic_cascades_disabled'}</p>
  {:else if status === 'error'}
    <p>error — {reason ?? 'unknown'}</p>
  {:else if status === 'empty'}
    <p>No economic-cascade evidence was published for this run.</p>
  {:else}
    {#if summary}
      <h3>Summary</h3>
      <p>
        {summary.disruption_kind_count} disruption kinds · {summary.stage_count} stages ·
        {summary.dependency_edge_count} edges · {summary.linked_chain_count} linked chains ·
        depth {summary.max_depth} · {label(summary.availability)}
      </p>

      <h3>Disruptions</h3>
      <table>
        <thead>
          <tr>
            <th>Kind</th>
            <th>Window</th>
            <th>Count</th>
            <th>Magnitude</th>
            <th>Subjects</th>
            <th>Coverage</th>
          </tr>
        </thead>
        <tbody>
          {#each disruptions as row}
            <tr>
              <td>{label(row.kind)}</td>
              <td>{row.window_index}</td>
              <td>{row.disruption_count}</td>
              <td>{row.magnitude_total}</td>
              <td>{row.subject_count}</td>
              <td>{label(row.coverage)}</td>
            </tr>
          {/each}
        </tbody>
      </table>

      <h3>Dependencies</h3>
      <table>
        <thead>
          <tr>
            <th>Kind</th>
            <th>Upstream</th>
            <th>Downstream</th>
            <th>Depth</th>
            <th>Evidence</th>
          </tr>
        </thead>
        <tbody>
          {#each dependencies as row}
            <tr>
              <td>{label(row.kind)}</td>
              <td>{row.upstream_token}</td>
              <td>{row.downstream_recipe_token}</td>
              <td>{row.depth}</td>
              <td>{row.evidence_count}</td>
            </tr>
          {/each}
        </tbody>
      </table>

      <h3>Chains</h3>
      <table>
        <thead>
          <tr>
            <th>Kind</th>
            <th>Downstream</th>
            <th>Depth</th>
            <th>Lag</th>
            <th>Shortfall (milli)</th>
            <th>State</th>
          </tr>
        </thead>
        <tbody>
          {#each chains as row}
            <tr>
              <td>{label(row.disruption_kind)}</td>
              <td>{row.chain_token}</td>
              <td>{row.depth}</td>
              <td>{row.lag_windows}</td>
              <td>{row.shortfall_share_milli}</td>
              <td>{row.state}</td>
            </tr>
          {/each}
        </tbody>
      </table>

      <h3>Propagation</h3>
      <table>
        <thead>
          <tr>
            <th>Kind</th>
            <th>Chains</th>
            <th>Linked</th>
            <th>Unlinked</th>
            <th>Unresolved</th>
            <th>Mean depth (milli)</th>
            <th>Mean lag (milli)</th>
            <th>Availability</th>
          </tr>
        </thead>
        <tbody>
          {#each propagation as row}
            <tr>
              <td>{label(row.disruption_kind)}</td>
              <td>{row.chain_count}</td>
              <td>{row.linked_chain_count}</td>
              <td>{row.unlinked_chain_count}</td>
              <td>{row.unresolved_chain_count}</td>
              <td>{row.mean_depth_milli}</td>
              <td>{row.mean_lag_milli}</td>
              <td>{label(row.availability)}</td>
            </tr>
          {/each}
        </tbody>
      </table>

      {#if coverage}
        <h3>Coverage</h3>
        <p>
          {coverage.window_count} windows · {coverage.event_count} events ·
          {coverage.disruption_count} disruptions · {coverage.stage_count} stages ·
          {coverage.dependency_edge_count} edges · {coverage.chain_count} chains ·
          {label(coverage.coverage)}
          {#if coverage.truncated}· truncated{/if}
        </p>
      {/if}
    {/if}
  {/if}
</section>

<style>
  .economic-cascades table {
    border-collapse: collapse;
    margin-bottom: 1rem;
  }
  .economic-cascades th,
  .economic-cascades td {
    border-bottom: 1px solid #ddd;
    padding: 0.25rem 0.5rem;
    text-align: left;
  }
</style>
