<script lang="ts">
  import { ApiClientError } from '../api/client'
  import {
    getCohorts,
    getDimensions,
    getSocieties,
    getSummary,
    type EconomicCohort,
    type EconomicDimension,
    type EconomicInequalitySummary,
    type EconomicSociety,
  } from '../api/economicInequality'
  import type { ResearchSelection } from '../research/selection'

  interface Props {
    runId: string
    selection: ResearchSelection
  }

  let { runId }: Props = $props()

  type Status = 'loading' | 'ready' | 'empty' | 'unavailable' | 'error'
  let status = $state<Status>('loading')
  let reason = $state<string | null>(null)
  let summary = $state<EconomicInequalitySummary | null>(null)
  let dimensions = $state<EconomicDimension[]>([])
  let cohorts = $state<EconomicCohort[]>([])
  let societies = $state<EconomicSociety[]>([])
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

  function value(value: number | null): string {
    return value === null ? 'unavailable' : String(value)
  }

  async function load(): Promise<void> {
    status = 'loading'
    reason = null
    const index = windowIndex()
    try {
      summary = await getSummary(runId)
      const [dimensionPage, cohortPage, societyPage] = await Promise.all([
        getDimensions(runId, { windowIndex: index }),
        getCohorts(runId, { windowIndex: index }),
        getSocieties(runId, { windowIndex: index }),
      ])
      dimensions = dimensionPage.rows
      cohorts = cohortPage.rows
      societies = societyPage.rows
      status =
        dimensions.length + cohorts.length + societies.length > 0
          ? 'ready'
          : 'empty'
    } catch (error) {
      if (error instanceof ApiClientError) {
        reason = error.code
        status =
          error.code === 'economic_inequality_disabled' || error.code === 'http_503'
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

<section class="economic-inequality" data-testid="economic-inequality-panel">
  <header>
    <h2>Economic inequality</h2>
    <p data-testid="economic-inequality-disclaimer">
      These are descriptive distributions over observed possession, access, and
      declared claims. They do not measure legitimate ownership, merit, poverty,
      or a composite wealth score, and they never rank people.
    </p>
    <label>
      Window
      <input aria-label="Window filter" bind:value={windowInput} />
    </label>
  </header>

  {#if status === 'loading'}
    <p>Loading economic inequality…</p>
  {:else if status === 'unavailable'}
    <p>Economic inequality is disabled for this deployment.</p>
  {:else if status === 'error'}
    <p>Economic inequality unavailable: {reason ?? 'error'}</p>
  {:else if status === 'empty'}
    <p>No economic inequality rows were published for this run.</p>
  {:else if summary}
    <dl>
      <dt>Dimensions</dt><dd>{summary.dimension_row_count}</dd>
      <dt>Cohorts</dt><dd>{summary.cohort_row_count}</dd>
      <dt>Societies</dt><dd>{summary.society_row_count}</dd>
      <dt>Windows</dt><dd>{summary.window_count}</dd>
      <dt>Owners</dt><dd>{summary.observed_owner_count} / {summary.owner_count}</dd>
      <dt>Overlap members</dt><dd>{summary.overlap_member_count}</dd>
      <dt>Coverage</dt><dd>{label(summary.coverage)}</dd>
      <dt>Evidence coverage</dt><dd>{label(summary.evidence_coverage)}</dd>
      <dt>Dimension coverage</dt><dd>{label(summary.dimension_coverage)}</dd>
      <dt>Comparison coverage</dt><dd>{label(summary.comparison_coverage)}</dd>
      <dt>Truncated</dt><dd>{summary.truncated ? 'yes' : 'no'}</dd>
    </dl>

    <h3>Dimensions</h3>
    {#if dimensions.length === 0}
      <p>No dimension rows.</p>
    {:else}
      <table>
        <thead>
          <tr>
            <th>Dimension</th><th>Measure</th><th>Owners</th><th>Gini</th>
            <th>Median</th><th>IQR</th><th>Top share</th>
            <th>Availability</th><th>Coverage</th>
          </tr>
        </thead>
        <tbody>
          {#each dimensions as row (row.dimension + row.measure + String(row.window_index))}
            <tr>
              <td>{label(row.dimension)}</td>
              <td>{label(row.measure)}</td>
              <td>{row.observed_owner_count} / {row.owner_count}</td>
              <td>{value(row.gini_milli)}</td>
              <td>{value(row.median)}</td>
              <td>{value(row.iqr)}</td>
              <td>{value(row.top_share_milli)}</td>
              <td>{label(row.availability)}</td>
              <td>{label(row.coverage)}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    {/if}

    <h3>Cohorts</h3>
    {#if cohorts.length === 0}
      <p>No cohort rows.</p>
    {:else}
      <table>
        <thead>
          <tr>
            <th>Generation</th><th>Owners</th><th>Gini</th>
            <th>Trend</th><th>Availability</th>
          </tr>
        </thead>
        <tbody>
          {#each cohorts as row (row.cohort_token + String(row.window_index))}
            <tr>
              <td>{row.generation_index}</td>
              <td>{row.owner_count}</td>
              <td>{value(row.gini_milli)}</td>
              <td>{label(row.trend)}</td>
              <td>{label(row.availability)}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    {/if}

    <h3>Societies</h3>
    {#if societies.length === 0}
      <p>No society rows.</p>
    {:else}
      <table>
        <thead>
          <tr>
            <th>Society</th><th>Owners</th><th>Gini</th>
            <th>Trend</th><th>Availability</th>
          </tr>
        </thead>
        <tbody>
          {#each societies as row (row.society_token + String(row.window_index))}
            <tr>
              <td>{row.society_token.slice(0, 12)}</td>
              <td>{row.owner_count}</td>
              <td>{value(row.gini_milli)}</td>
              <td>{label(row.trend)}</td>
              <td>{label(row.availability)}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    {/if}
  {/if}
</section>
