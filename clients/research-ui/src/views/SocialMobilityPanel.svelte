<script lang="ts">
  import { ApiClientError } from '../api/client'
  import {
    getCoverage,
    getDomains,
    getGenerations,
    getSummary,
    type SocialMobilityCoverageRow,
    type SocialMobilityDomainRow,
    type SocialMobilityGenerationRow,
    type SocialMobilityLagRow,
    type SocialMobilitySummary,
  } from '../api/socialMobility'
  import type { ResearchSelection } from '../research/selection'

  interface Props {
    runId: string
    selection: ResearchSelection
  }

  let { runId }: Props = $props()

  type Status = 'loading' | 'ready' | 'empty' | 'unavailable' | 'error'
  let status = $state<Status>('loading')
  let reason = $state<string | null>(null)
  let summary = $state<SocialMobilitySummary | null>(null)
  let domains = $state<SocialMobilityDomainRow[]>([])
  let generations = $state<SocialMobilityGenerationRow[]>([])
  let lags = $state<SocialMobilityLagRow[]>([])
  let coverage = $state<SocialMobilityCoverageRow | null>(null)
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
      summary = await getSummary(runId)
      const [domainPage, generationPage, coveragePage] = await Promise.all([
        getDomains(runId, { windowIndex: index }),
        getGenerations(runId, { windowIndex: index }),
        getCoverage(runId, { windowIndex: index }),
      ])
      domains = domainPage.rows
      generations = generationPage.rows.filter(
        (row): row is SocialMobilityGenerationRow =>
          'generation_index' in row,
      )
      lags = generationPage.rows.filter(
        (row): row is SocialMobilityLagRow => 'generation_lag' in row,
      )
      coverage = coveragePage.rows[0] ?? null
      status =
        domains.length + generations.length + lags.length > 0
          ? 'ready'
          : 'empty'
    } catch (error) {
      if (error instanceof ApiClientError) {
        reason = error.code
        status =
          error.code === 'social_mobility_disabled' || error.code === 'http_503'
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

<section class="social-mobility" data-testid="social-mobility-panel">
  <header>
    <h2>Social mobility</h2>
    {#if summary}
      <p class="meta">
        {summary.window_count} windows · {summary.owner_count} owners ·
        {summary.generation_count} generations · {label(summary.coverage)}
        {#if summary.truncated}· truncated{/if}
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
    <p>unavailable — {reason ?? 'social_mobility_disabled'}</p>
  {:else if status === 'error'}
    <p>error — {reason ?? 'unknown'}</p>
  {:else if status === 'empty'}
    <p>No social-mobility evidence was published for this run.</p>
  {:else}
    {#if summary}
      <h3>Domains</h3>
      <table>
        <thead>
          <tr>
            <th>Domain</th>
            <th>Measure</th>
            <th>Pairs</th>
            <th>Resolved</th>
            <th>Rank correlation (milli)</th>
            <th>Same bin (milli)</th>
            <th>Upward (milli)</th>
            <th>Downward (milli)</th>
            <th>Mean rank change (milli)</th>
            <th>Persistence</th>
            <th>Availability</th>
          </tr>
        </thead>
        <tbody>
          {#each domains as row}
            <tr>
              <td>{label(row.domain)}</td>
              <td>{label(row.measure)}</td>
              <td>{row.pair_count}</td>
              <td>{row.resolved_pair_count}</td>
              <td>{row.rank_correlation_milli}</td>
              <td>{row.same_bin_share_milli}</td>
              <td>{row.upward_share_milli}</td>
              <td>{row.downward_share_milli}</td>
              <td>{row.mean_absolute_rank_change_milli}</td>
              <td>{label(row.persistence_direction)}</td>
              <td>{label(row.availability)}</td>
            </tr>
          {/each}
        </tbody>
      </table>

      <h3>Generations</h3>
      <table>
        <thead>
          <tr>
            <th>Generation</th>
            <th>Owners</th>
            <th>Pairs</th>
            <th>Comparable</th>
            <th>Same bin (milli)</th>
            <th>Upward (milli)</th>
            <th>Downward (milli)</th>
            <th>Availability</th>
          </tr>
        </thead>
        <tbody>
          {#each generations as row}
            <tr>
              <td>{row.generation_index}</td>
              <td>{row.owner_count}</td>
              <td>{row.pair_count}</td>
              <td>{row.comparable}</td>
              <td>{row.same_bin_share_milli}</td>
              <td>{row.upward_share_milli}</td>
              <td>{row.downward_share_milli}</td>
              <td>{label(row.availability)}</td>
            </tr>
          {/each}
        </tbody>
      </table>

      <h3>Generation lags</h3>
      <table>
        <thead>
          <tr>
            <th>Lag</th>
            <th>Pairs</th>
            <th>Comparable</th>
            <th>Same bin (milli)</th>
            <th>Upward (milli)</th>
            <th>Downward (milli)</th>
            <th>Availability</th>
          </tr>
        </thead>
        <tbody>
          {#each lags as row}
            <tr>
              <td>{row.generation_lag}</td>
              <td>{row.pair_count}</td>
              <td>{row.comparable}</td>
              <td>{row.same_bin_share_milli}</td>
              <td>{row.upward_share_milli}</td>
              <td>{row.downward_share_milli}</td>
              <td>{label(row.availability)}</td>
            </tr>
          {/each}
        </tbody>
      </table>

      {#if coverage}
        <h3>Coverage</h3>
        <dl>
          <dt>Generation count</dt>
          <dd>{coverage.generation_count}</dd>
          <dt>Owner count</dt>
          <dd>{coverage.owner_count}</dd>
          <dt>Genealogy edges</dt>
          <dd>{coverage.genealogy_edge_count}</dd>
          <dt>Pairs</dt>
          <dd>{coverage.pair_count}</dd>
          <dt>Resolved</dt>
          <dd>{coverage.resolved_pair_count}</dd>
          <dt>Unresolved</dt>
          <dd>{coverage.unresolved_pair_count}</dd>
          <dt>Domains available</dt>
          <dd>{coverage.domain_available_count}</dd>
          <dt>Truncated</dt>
          <dd>{coverage.truncated}</dd>
          <dt>Coverage</dt>
          <dd>{label(coverage.coverage)}</dd>
        </dl>
      {/if}
    {/if}
  {/if}
</section>
