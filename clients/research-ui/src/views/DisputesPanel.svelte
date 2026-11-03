<script lang="ts">
  import { ApiClientError } from '../api/client'
  import {
    getDisputeCandidate,
    getDisputeCandidates,
    getDisputeClaims,
    getDisputeLineage,
    getDisputeResolutions,
    getDisputeSummary,
    type DisputeCandidate,
    type DisputeCandidateDetail,
    type DisputeClaim,
    type DisputeLineageEdge,
    type DisputeResolution,
    type DisputeSummary,
  } from '../api/disputes'
  import type { ResearchSelection } from '../research/selection'

  interface Props {
    runId: string
    selection: ResearchSelection
  }

  let { runId }: Props = $props()

  type Status = 'loading' | 'available' | 'empty' | 'unavailable' | 'error'

  let status = $state<Status>('loading')
  let reason = $state<string | null>(null)
  let summary = $state<DisputeSummary | null>(null)
  let candidates = $state<DisputeCandidate[]>([])
  let lineage = $state<DisputeLineageEdge[]>([])
  let selectedId = $state<string | null>(null)
  let detail = $state<DisputeCandidateDetail | null>(null)
  let claims = $state<DisputeClaim[]>([])
  let resolutions = $state<DisputeResolution[]>([])

  function label(value: string): string {
    return value.replaceAll('_', ' ')
  }

  async function load(): Promise<void> {
    status = 'loading'
    reason = null
    summary = null
    candidates = []
    lineage = []
    selectedId = null
    detail = null
    claims = []
    resolutions = []
    try {
      summary = await getDisputeSummary(runId)
      const page = await getDisputeCandidates(runId)
      candidates = page.items
      const edges = await getDisputeLineage(runId)
      lineage = edges.items
      status = candidates.length === 0 ? 'empty' : 'available'
    } catch (error) {
      if (error instanceof ApiClientError) {
        reason = error.code
        status = error.code === 'dispute_disabled' ? 'unavailable' : 'error'
        return
      }
      reason = 'dispute_read_failed'
      status = 'error'
    }
  }

  async function selectCandidate(candidateId: string): Promise<void> {
    selectedId = candidateId
    try {
      detail = await getDisputeCandidate(runId, candidateId)
      const [claimPage, resolutionPage] = await Promise.all([
        getDisputeClaims(runId, candidateId),
        getDisputeResolutions(runId, candidateId),
      ])
      claims = claimPage.items
      resolutions = resolutionPage.items
    } catch (error) {
      reason = error instanceof ApiClientError ? error.code : 'dispute_read_failed'
      status = 'error'
    }
  }

  $effect(() => {
    void runId
    void load()
  })
</script>

<section class="disputes">
  <header>
    <h1>Disputed claims</h1>
    <p class="note">
      Owner beliefs only: claimed, reported, and declared positions. Resolutions
      are proposals; apparently accepted requires every named party's active
      declaration.
    </p>
  </header>

  {#if status === 'loading'}
    <p>Loading dispute snapshot…</p>
  {:else if status === 'unavailable'}
    <p class="unavailable">Dispute publication is disabled ({reason}).</p>
  {:else if status === 'empty'}
    <p class="empty">No published dispute-resolution snapshot for this run.</p>
  {:else if status === 'error'}
    <p class="error">Dispute read failed ({reason}).</p>
  {:else if summary !== null}
    <dl class="summary">
      <div><dt>Candidates</dt><dd>{summary.candidate_count}</dd></div>
      <div><dt>Cases</dt><dd>{summary.case_count}</dd></div>
      <div><dt>Claims</dt><dd>{summary.claim_count}</dd></div>
      <div><dt>Counterclaims</dt><dd>{summary.counterclaim_count}</dd></div>
      <div><dt>Testimony</dt><dd>{summary.testimony_count}</dd></div>
      <div><dt>Evidence</dt><dd>{summary.evidence_count}</dd></div>
      <div><dt>Resolutions</dt><dd>{summary.resolution_count}</dd></div>
      <div><dt>Declared acceptances</dt><dd>{summary.accepted_count}</dd></div>
      <div><dt>Declared rejections</dt><dd>{summary.rejected_count}</dd></div>
      <div><dt>Lineage edges</dt><dd>{summary.edge_count}</dd></div>
      <div><dt>Windows</dt><dd>{summary.window_count}</dd></div>
      <div>
        <dt>Coverage</dt>
        <dd>
          {summary.coverage.observed}/{summary.coverage.expected}
          {#if summary.coverage.note !== ''}
            <span class="muted">({summary.coverage.note})</span>
          {/if}
        </dd>
      </div>
      <div><dt>Publication</dt><dd>{summary.publication_id}</dd></div>
    </dl>

    <table class="candidates">
      <thead>
        <tr>
          <th>Candidate</th>
          <th>Kind</th>
          <th>Status</th>
          <th>Parties</th>
          <th>Claims</th>
          <th>Counterclaims</th>
          <th>Disagreements</th>
          <th>Coverage</th>
        </tr>
      </thead>
      <tbody>
        {#each candidates as candidate (candidate.candidate_id)}
          <tr>
            <td>
              <button
                type="button"
                class:selected={selectedId === candidate.candidate_id}
                onclick={() => selectCandidate(candidate.candidate_id)}
              >
                {candidate.candidate_id}
              </button>
            </td>
            <td>{label(candidate.kind)}</td>
            <td>{label(candidate.status)}</td>
            <td>{candidate.party_count}</td>
            <td>{candidate.claim_count}</td>
            <td>{candidate.counterclaim_count}</td>
            <td>{candidate.disagreement_count}</td>
            <td>{candidate.coverage.observed}/{candidate.coverage.expected}</td>
          </tr>
        {/each}
      </tbody>
    </table>

    {#if detail !== null}
      <section class="detail">
        <h2>Candidate {detail.candidate.candidate_id}</h2>

        <h3>Claims</h3>
        <table class="claims">
          <thead>
            <tr>
              <th>Claimant</th>
              <th>Role</th>
              <th>Polarity</th>
              <th>Claim kind</th>
              <th>Evidence count</th>
              <th>First tick</th>
              <th>Last tick</th>
            </tr>
          </thead>
          <tbody>
            {#each claims as claim (claim.claim_id)}
              <tr>
                <td>{claim.claimant_id}</td>
                <td>{label(claim.role)}</td>
                <td>{label(claim.polarity)}</td>
                <td>{label(claim.claim_kind)}</td>
                <td>{claim.evidence_count}</td>
                <td>{claim.first_tick}</td>
                <td>{claim.last_tick}</td>
              </tr>
            {/each}
          </tbody>
        </table>

        <h3>Testimony</h3>
        <table class="testimony">
          <thead>
            <tr>
              <th>Speaker</th>
              <th>Channel</th>
              <th>Root</th>
              <th>Independent</th>
            </tr>
          </thead>
          <tbody>
            {#each detail.testimony as testimony (testimony.testimony_id)}
              <tr>
                <td>{testimony.speaker_id}</td>
                <td>{label(testimony.channel)}</td>
                <td>{testimony.root_token}</td>
                <td>{testimony.independently_evidenced ? 'yes' : 'no'}</td>
              </tr>
            {/each}
          </tbody>
        </table>

        <h3>Evidence references</h3>
        <table class="evidence">
          <thead>
            <tr>
              <th>Evidence</th>
              <th>Claim</th>
              <th>Channel</th>
              <th>Reference kind</th>
              <th>Reference token</th>
              <th>Tick</th>
              <th>Independent</th>
            </tr>
          </thead>
          <tbody>
            {#each detail.evidence as evidence (evidence.evidence_id)}
              <tr>
                <td>{evidence.evidence_id}</td>
                <td>{evidence.claim_id}</td>
                <td>{label(evidence.channel)}</td>
                <td>{label(evidence.reference_kind)}</td>
                <td>{evidence.reference_token}</td>
                <td>{evidence.tick}</td>
                <td>{evidence.independently_evidenced ? 'yes' : 'no'}</td>
              </tr>
            {/each}
          </tbody>
        </table>

        <h3>Rule references</h3>
        <table class="rule-references">
          <thead>
            <tr>
              <th>Reference</th>
              <th>Claim</th>
              <th>System</th>
              <th>Rule</th>
              <th>Version</th>
              <th>Applicability</th>
              <th>Interpretation</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {#each detail.rule_references as reference (reference.rule_reference_id)}
              <tr>
                <td>{reference.rule_reference_id}</td>
                <td>{reference.claim_ref}</td>
                <td>{reference.system_token}</td>
                <td>{reference.rule_token}</td>
                <td>{reference.version_number}</td>
                <td>{label(reference.applicability)}</td>
                <td>{label(reference.interpretation)}</td>
                <td>{label(reference.status)}</td>
              </tr>
            {/each}
          </tbody>
        </table>

        <h3>Authority references</h3>
        <table class="authority-references">
          <thead>
            <tr>
              <th>Reference</th>
              <th>Authority kind</th>
              <th>Token</th>
              <th>Strength</th>
              <th>Uncertainty</th>
              <th>Dissenting</th>
            </tr>
          </thead>
          <tbody>
            {#each detail.authority_references as reference (reference.authority_reference_id)}
              <tr>
                <td>{reference.authority_reference_id}</td>
                <td>{label(reference.authority_kind)}</td>
                <td>{reference.reference_token}</td>
                <td>{reference.strength}</td>
                <td>{reference.uncertainty}</td>
                <td>{reference.dissenting ? 'yes' : 'no'}</td>
              </tr>
            {/each}
          </tbody>
        </table>

        <h3>Mediation references</h3>
        <table class="mediation-references">
          <thead>
            <tr>
              <th>Reference</th>
              <th>Case token</th>
              <th>Recommendation</th>
              <th>Response</th>
              <th>Outcome</th>
              <th>Link status</th>
            </tr>
          </thead>
          <tbody>
            {#each detail.mediation_references as reference (reference.mediation_reference_id)}
              <tr>
                <td>{reference.mediation_reference_id}</td>
                <td>{reference.mediation_case_token}</td>
                <td>{reference.recommendation_token ?? 'none'}</td>
                <td>{reference.response_token ?? 'none'}</td>
                <td>{reference.outcome_token ?? 'none'}</td>
                <td>{label(reference.link_status)}</td>
              </tr>
            {/each}
          </tbody>
        </table>

        <h3>Resolutions</h3>
        <table class="resolutions">
          <thead>
            <tr>
              <th>Proposer</th>
              <th>Source</th>
              <th>Terms digest</th>
              <th>Status</th>
              <th>Accepted parties</th>
              <th>Rejected parties</th>
              <th>Expiry</th>
            </tr>
          </thead>
          <tbody>
            {#each resolutions as resolution (resolution.resolution_id)}
              <tr>
                <td>{resolution.proposer_id}</td>
                <td>{label(resolution.source)}</td>
                <td>{resolution.terms_digest}</td>
                <td>{label(resolution.status)}</td>
                <td>{resolution.accepted_party_count}</td>
                <td>{resolution.rejected_party_count}</td>
                <td>{resolution.expires_tick ?? 'none'}</td>
              </tr>
            {/each}
          </tbody>
        </table>

        <h3>Resolution responses</h3>
        <table class="responses">
          <thead>
            <tr>
              <th>Party</th>
              <th>Declaration</th>
              <th>Tick</th>
              <th>Terms digest</th>
            </tr>
          </thead>
          <tbody>
            {#each detail.responses as response (response.response_id)}
              <tr>
                <td>{response.party_id}</td>
                <td>declared {label(response.kind)}</td>
                <td>{response.tick}</td>
                <td>{response.terms_digest}</td>
              </tr>
            {/each}
          </tbody>
        </table>

        {#if detail.truncated}
          <p class="truncated">
            Some related rows were truncated by the published snapshot bounds.
          </p>
        {/if}
      </section>
    {/if}

    <h3>Lineage</h3>
    <table class="lineage">
      <thead>
        <tr>
          <th>Edge</th>
          <th>Kind</th>
          <th>Source</th>
          <th>Target</th>
          <th>Tick</th>
        </tr>
      </thead>
      <tbody>
        {#each lineage as edge (edge.edge_id)}
          <tr>
            <td>{edge.edge_id}</td>
            <td>{label(edge.kind)}</td>
            <td>{edge.source}</td>
            <td>{edge.target}</td>
            <td>{edge.tick}</td>
          </tr>
        {/each}
      </tbody>
    </table>
  {/if}
</section>
