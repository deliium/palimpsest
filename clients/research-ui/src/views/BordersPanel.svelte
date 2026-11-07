<script lang="ts">
  import { ApiClientError } from '../api/client'
  import {
    fetchBorderAgreements,
    fetchBorderClaims,
    fetchBorderControl,
    fetchBordersSummary,
    type BorderAgreement,
    type BorderClaim,
    type BorderControlRow,
    type BordersSummary,
  } from '../api/borders'
  import EpistemicBadge from '../components/EpistemicBadge.svelte'
  import type { ResearchSelection } from '../research/selection'

  interface Props {
    runId: string
    selection: ResearchSelection
  }

  let { runId }: Props = $props()

  type Status = 'loading' | 'ready' | 'empty' | 'unavailable' | 'error'
  let status = $state<Status>('loading')
  let reason = $state<string | null>(null)
  let summary = $state<BordersSummary | null>(null)
  let claims = $state<BorderClaim[]>([])
  let agreements = $state<BorderAgreement[]>([])
  let control = $state<BorderControlRow[]>([])

  function label(value: string | null | undefined): string {
    return value ? value.replaceAll('_', ' ') : 'unknown'
  }

  async function load(): Promise<void> {
    status = 'loading'
    reason = null
    try {
      summary = await fetchBordersSummary(runId)
      const [claimPage, agreementPage, controlPage] = await Promise.all([
        fetchBorderClaims(runId),
        fetchBorderAgreements(runId),
        fetchBorderControl(runId, 'all'),
      ])
      claims = claimPage.items
      agreements = agreementPage.items
      control = controlPage.items
      status =
        claims.length === 0 && agreements.length === 0 && control.length === 0
          ? 'empty'
          : 'ready'
    } catch (error) {
      if (error instanceof ApiClientError) {
        reason = error.code
        status =
          error.code === 'borders_disabled' || error.code === 'http_503'
            ? 'unavailable'
            : 'error'
      } else {
        status = 'error'
      }
    }
  }

  $effect(() => {
    void runId
    void load()
  })
</script>

<section class="borders">
  <h2>Borders and claims</h2>
  {#if status === 'loading'}
    <p>Loading border evidence…</p>
  {:else if status === 'unavailable'}
    <p>Border publication is not configured for this run.</p>
  {:else if status === 'error'}
    <p>Border evidence is unavailable. Reason: {reason ?? 'unknown'}.</p>
  {:else if status === 'empty'}
    <p>No border evidence was published for this run.</p>
  {:else if summary}
    <dl>
      <dt>Candidates</dt><dd>{summary.candidate_count}</dd>
      <dt>Claims</dt><dd>{summary.claim_count}</dd>
      <dt>Agreements</dt><dd>{summary.agreement_count}</dd>
      <dt>Disputes</dt><dd>{summary.dispute_count}</dd>
      <dt>Physical rows</dt><dd>{summary.physical_row_count}</dd>
      <dt>Patterns</dt><dd>{summary.pattern_count}</dd>
      <dt>Coverage</dt><dd>{label(summary.coverage)}</dd>
    </dl>

    <h3>Physical control <EpistemicBadge epistemic="objective_world" /></h3>
    <ul>
      {#each control.filter((row) => row.layer === 'physical') as row (row.location_token + ':' + row.window_start)}
        <li>
          <span>{row.location_token}</span>
          <span>{label(row.classification)}</span>
          <span>actions {row.action_count}</span>
          <span>actors {row.actor_count}</span>
          <span>hostile {row.hostile_count}</span>
        </li>
      {/each}
    </ul>

    <h3>Claims <EpistemicBadge epistemic="agent_belief" /></h3>
    <ul>
      {#each claims as claim (claim.claim_token)}
        <li>
          <span>{claim.domain_token}</span>
          <span>{label(claim.status)}</span>
          <span>locations {claim.location_tokens.length}</span>
          <span>edges {claim.boundary_edge_tokens.length}</span>
        </li>
      {/each}
    </ul>

    <h3>Agreements <EpistemicBadge epistemic="agent_belief" /></h3>
    <ul>
      {#each agreements as agreement (agreement.agreement_token)}
        <li>
          <span>{agreement.domain_token}</span>
          <span>{label(agreement.status)}</span>
          <span>{label(agreement.recognition)}</span>
          <span>provisions {agreement.provision_tokens.length}</span>
        </li>
      {/each}
    </ul>

    <h3>Control patterns <EpistemicBadge epistemic="research_inference" /></h3>
    <ul>
      {#each control.filter((row) => row.layer === 'analytical') as row (row.pattern_token)}
        <li>
          <span>{row.domain_token}</span>
          <span>{label(row.pattern)}</span>
          <span>physical actions {row.physical_actions}</span>
          <span>disputes {row.dispute_count}</span>
        </li>
      {/each}
    </ul>
  {/if}
</section>
