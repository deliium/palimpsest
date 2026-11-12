<script lang="ts">
  import { ApiClientError } from '../api/client'
  import {
    getAlignment,
    getClaims,
    getCounterparties,
    getDistributions,
    getPerformances,
    getRelationships,
    getSummary,
    type CreditAlignment,
    type CreditClaim,
    type CreditCounterparty,
    type CreditDistribution,
    type CreditPerformance,
    type CreditRelationship,
    type CreditRelationshipsSummary,
  } from '../api/creditRelationships'
  import type { ResearchSelection } from '../research/selection'

  interface Props {
    runId: string
    selection: ResearchSelection
  }

  let { runId }: Props = $props()

  type Status = 'loading' | 'ready' | 'empty' | 'unavailable' | 'error'
  let status = $state<Status>('loading')
  let reason = $state<string | null>(null)
  let summary = $state<CreditRelationshipsSummary | null>(null)
  let relationships = $state<CreditRelationship[]>([])
  let claims = $state<CreditClaim[]>([])
  let performances = $state<CreditPerformance[]>([])
  let distributions = $state<CreditDistribution[]>([])
  let counterparties = $state<CreditCounterparty[]>([])
  let alignments = $state<CreditAlignment[]>([])
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
      const [
        relationshipPage,
        claimPage,
        performancePage,
        distributionPage,
        counterpartyPage,
        alignmentPage,
      ] = await Promise.all([
        getRelationships(runId, { windowIndex: index }),
        getClaims(runId, { windowIndex: index }),
        getPerformances(runId, { windowIndex: index }),
        getDistributions(runId, { windowIndex: index }),
        getCounterparties(runId, { windowIndex: index }),
        getAlignment(runId, { windowIndex: index }),
      ])
      relationships = relationshipPage.rows
      claims = claimPage.rows
      performances = performancePage.rows
      distributions = distributionPage.rows
      counterparties = counterpartyPage.rows
      alignments = alignmentPage.rows
      const hasRows =
        relationships.length +
          claims.length +
          performances.length +
          distributions.length +
          counterparties.length +
          alignments.length >
        0
      status = hasRows ? 'ready' : 'empty'
    } catch (error) {
      if (error instanceof ApiClientError) {
        reason = error.code
        status =
          error.code === 'credit_relationships_disabled' || error.code === 'http_503'
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

<section class="credit-relationships" data-testid="credit-relationships-panel">
  <header>
    <h2>Credit relationships</h2>
    <p>
      Owner-scoped credit beliefs. No bank, money, enforceable debt, credit
      score, or canonical credit is shown.
    </p>
    <label>
      Window
      <input aria-label="Window filter" bind:value={windowInput} />
    </label>
  </header>

  {#if status === 'loading'}
    <p>Loading credit relationships…</p>
  {:else if status === 'unavailable'}
    <p>Credit relationships are disabled for this deployment.</p>
  {:else if status === 'error'}
    <p>Credit relationships unavailable: {reason ?? 'error'}</p>
  {:else if status === 'empty'}
    <p>No credit relationships were published for this run.</p>
  {:else if summary}
    <dl>
      <dt>Coverage</dt>
      <dd>{label(summary.coverage)}</dd>
      <dt>Relationships</dt>
      <dd>{summary.relationship_count}</dd>
      <dt>Claims</dt>
      <dd>{summary.claim_count}</dd>
      <dt>Performances</dt>
      <dd>{summary.performance_count}</dd>
      <dt>Distributions</dt>
      <dd>{summary.distribution_count}</dd>
      <dt>Counterparties</dt>
      <dd>{summary.counterparty_count}</dd>
      <dt>Alignments</dt>
      <dd>{summary.alignment_count}</dd>
    </dl>

    <h3>Relationships</h3>
    {#if relationships.length === 0}
      <p>No relationship rows.</p>
    {:else}
      <table>
        <thead>
          <tr><th>Direction</th><th>Status</th><th>Repayment ratio</th><th>Confidence</th><th>Coverage</th></tr>
        </thead>
        <tbody>
          {#each relationships as row (row.relationship_id)}
            <tr>
              <td>{label(row.direction)}</td>
              <td>{label(row.status)}</td>
              <td>{row.repayment_ratio_milli}</td>
              <td>{row.confidence_milli}</td>
              <td>{label(row.coverage)}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    {/if}

    <h3>Claims</h3>
    {#if claims.length === 0}
      <p>No claim rows.</p>
    {:else}
      <table>
        <thead>
          <tr><th>Act</th><th>Direction</th><th>Paid</th><th>Repayment</th><th>Coverage</th></tr>
        </thead>
        <tbody>
          {#each claims as row (row.claim_id)}
            <tr>
              <td>{label(row.act)}</td>
              <td>{label(row.direction)}</td>
              <td>{row.paid_quantity}</td>
              <td>{row.repayment_quantity}</td>
              <td>{label(row.coverage)}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    {/if}

    <h3>Performances</h3>
    {#if performances.length === 0}
      <p>No performance rows.</p>
    {:else}
      <table>
        <thead>
          <tr><th>Outcome</th><th>Claims</th><th>Repayments</th><th>Transfers</th><th>Coverage</th></tr>
        </thead>
        <tbody>
          {#each performances as row (row.performance_id)}
            <tr>
              <td>{label(row.outcome)}</td>
              <td>{row.claim_count}</td>
              <td>{row.repay_claim_count}</td>
              <td>{row.observed_transfer_count}</td>
              <td>{label(row.coverage)}</td>
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
          <tr><th>Samples</th><th>Source</th><th>Median</th><th>IQR</th><th>Dispersion</th><th>Status</th></tr>
        </thead>
        <tbody>
          {#each distributions as row (row.distribution_id)}
            <tr>
              <td>{row.sample_count}</td>
              <td>{label(row.sample_source)}</td>
              <td>{row.median_ratio_milli}</td>
              <td>{row.iqr_milli}</td>
              <td>{row.dispersion_milli}</td>
              <td>{label(row.status)}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    {/if}

    <h3>Counterparties</h3>
    {#if counterparties.length === 0}
      <p>No counterparty rows.</p>
    {:else}
      <table>
        <thead>
          <tr><th>Relationships</th><th>Owners</th><th>Claims</th><th>Transfers</th><th>Coverage</th></tr>
        </thead>
        <tbody>
          {#each counterparties as row (row.counterparty_token + String(row.window_index))}
            <tr>
              <td>{row.relationship_count}</td>
              <td>{row.owner_count}</td>
              <td>{row.claim_count}</td>
              <td>{row.observed_transfer_count}</td>
              <td>{label(row.coverage)}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    {/if}

    <h3>Alignment</h3>
    {#if alignments.length === 0}
      <p>No alignment rows.</p>
    {:else}
      <table>
        <thead>
          <tr><th>Alignment</th><th>Owner status</th><th>Analytical outcome</th><th>Gap</th><th>Coverage</th></tr>
        </thead>
        <tbody>
          {#each alignments as row (row.alignment_id)}
            <tr>
              <td>{label(row.alignment)}</td>
              <td>{label(row.owner_status)}</td>
              <td>{label(row.analytical_outcome)}</td>
              <td>{row.gap_milli}</td>
              <td>{label(row.coverage)}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    {/if}
  {/if}
</section>
