<script lang="ts">
  import { ApiClientError } from '../api/client'
  import {
    getDistributions,
    getExpectations,
    getMarkets,
    getRelations,
    getSummary,
    getUnits,
    type EmergentPricesSummary,
    type PriceDistribution,
    type PriceExpectation,
    type PriceMarket,
    type PriceRelation,
    type PriceUnit,
  } from '../api/emergentPrices'
  import type { ResearchSelection } from '../research/selection'

  interface Props {
    runId: string
    selection: ResearchSelection
  }

  let { runId }: Props = $props()

  type Status = 'loading' | 'ready' | 'empty' | 'unavailable' | 'error'
  let status = $state<Status>('loading')
  let reason = $state<string | null>(null)
  let summary = $state<EmergentPricesSummary | null>(null)
  let units = $state<PriceUnit[]>([])
  let expectations = $state<PriceExpectation[]>([])
  let distributions = $state<PriceDistribution[]>([])
  let markets = $state<PriceMarket[]>([])
  let relations = $state<PriceRelation[]>([])
  let windowInput = $state('')

  function label(value: string | null | undefined): string {
    return value ? value.replaceAll('_', ' ') : 'unknown'
  }

  function windowIndex(): number | undefined {
    const raw = String(windowInput ?? '')
    if (raw.trim() === '') return undefined
    const parsed = Number(raw)
    return Number.isInteger(parsed) && parsed >= 0 ? parsed : undefined
  }

  async function load(): Promise<void> {
    status = 'loading'
    reason = null
    const index = windowIndex()
    try {
      summary = await getSummary(runId)
      const [unitPage, expectationPage, distributionPage, marketPage, relationPage] =
        await Promise.all([
          getUnits(runId, { windowIndex: index }),
          getExpectations(runId, { windowIndex: index }),
          getDistributions(runId, { windowIndex: index }),
          getMarkets(runId, { windowIndex: index }),
          getRelations(runId, { windowIndex: index }),
        ])
      units = unitPage.rows
      expectations = expectationPage.rows
      distributions = distributionPage.rows
      markets = marketPage.rows
      relations = relationPage.rows
      const hasRows =
        units.length +
          expectations.length +
          distributions.length +
          markets.length +
          relations.length >
        0
      status = hasRows ? 'ready' : 'empty'
    } catch (error) {
      if (error instanceof ApiClientError) {
        reason = error.code
        status =
          error.code === 'emergent_prices_disabled' || error.code === 'http_503'
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

<section class="emergent-prices" data-testid="emergent-prices-panel">
  <header>
    <h2>Emergent prices</h2>
    <p>
      Owner-scoped expectations and analytical distributions. No canonical
      price, money, credit, allocation, or ranking is shown.
    </p>
    <label>
      Window
      <input aria-label="Window filter" bind:value={windowInput} />
    </label>
  </header>

  {#if status === 'loading'}
    <p>Loading emergent-price distributions…</p>
  {:else if status === 'unavailable'}
    <p>Emergent prices are disabled for this deployment.</p>
  {:else if status === 'error'}
    <p>Emergent prices unavailable: {reason ?? 'error'}</p>
  {:else if status === 'empty'}
    <p>No price expectations or distributions were published for this run.</p>
  {:else if summary}
    <dl>
      <dt>Coverage</dt>
      <dd>{label(summary.coverage)}</dd>
      <dt>Windows</dt>
      <dd>{summary.window_count}</dd>
      <dt>Units</dt>
      <dd>{summary.unit_count}</dd>
      <dt>Expectations</dt>
      <dd>{summary.expectation_count}</dd>
      <dt>Distributions</dt>
      <dd>{summary.distribution_count}</dd>
      <dt>Markets</dt>
      <dd>{summary.market_count}</dd>
      <dt>Relations</dt>
      <dd>{summary.relation_count}</dd>
    </dl>

    <h3>Reference units</h3>
    {#if units.length === 0}
      <p>No unit rows.</p>
    {:else}
      <table>
        <thead>
          <tr><th>Unit</th><th>Source</th><th>Owners</th><th>Alignment</th><th>Coverage</th></tr>
        </thead>
        <tbody>
          {#each units as unit (unit.unit_token + unit.unit_source)}
            <tr>
              <td>{unit.unit_token}</td>
              <td>{label(unit.unit_source)}</td>
              <td>{unit.owner_count}</td>
              <td>{label(unit.unit_alignment)}</td>
              <td>{label(unit.coverage)}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    {/if}

    <h3>Distributions</h3>
    {#if distributions.length === 0}
      <p>No distribution rows.</p>
    {:else}
      <table>
        <thead>
          <tr>
            <th>Samples</th><th>Source</th><th>p25</th><th>Median ratio</th>
            <th>p75</th><th>IQR</th><th>Dispersion</th><th>Bins</th><th>Status</th>
          </tr>
        </thead>
        <tbody>
          {#each distributions as row (row.distribution_id)}
            <tr>
              <td>{row.sample_count}</td>
              <td>{label(row.sample_source)}</td>
              <td>{row.p25_ratio_milli}</td>
              <td>{row.median_ratio_milli}</td>
              <td>{row.p75_ratio_milli}</td>
              <td>{row.iqr_milli}</td>
              <td>{row.dispersion_milli}</td>
              <td>{row.bin_shares_milli.join(' / ')}</td>
              <td>{label(row.status)}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    {/if}

    <h3>Markets</h3>
    {#if markets.length === 0}
      <p>No market membership was published.</p>
    {:else}
      <table>
        <thead>
          <tr><th>Market</th><th>Venues</th><th>Distributions</th><th>Samples</th><th>Coverage</th></tr>
        </thead>
        <tbody>
          {#each markets as market (market.market_token + String(market.window_index))}
            <tr>
              <td>{market.market_token}</td>
              <td>{market.venue_count}</td>
              <td>{market.distribution_count}</td>
              <td>{market.sample_count}</td>
              <td>{label(market.coverage)}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    {/if}

    <h3>Convergence and divergence</h3>
    {#if relations.length === 0}
      <p>No pairwise relations.</p>
    {:else}
      <table>
        <thead>
          <tr><th>Relation</th><th>Overlap</th><th>Median gap</th><th>Samples</th><th>Coverage</th></tr>
        </thead>
        <tbody>
          {#each relations as relation (relation.relation_id)}
            <tr>
              <td>{label(relation.relation)}</td>
              <td>{relation.overlap_milli}</td>
              <td>{relation.median_gap_milli}</td>
              <td>{relation.sample_a} / {relation.sample_b}</td>
              <td>{label(relation.coverage)}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    {/if}
  {/if}
</section>

<style>
  .emergent-prices {
    display: grid;
    gap: 1rem;
  }
  table {
    border-collapse: collapse;
    width: 100%;
  }
  th,
  td {
    border-bottom: 1px solid #ddd;
    padding: 0.25rem 0.5rem;
    text-align: left;
  }
</style>
