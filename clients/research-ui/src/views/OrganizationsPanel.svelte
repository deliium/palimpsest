<script lang="ts">
  import { ApiClientError } from '../api/client'
  import {
    getOrganizationCandidate,
    getOrganizationCandidates,
    getOrganizationCollectiveAgency,
    getOrganizationLineage,
    getOrganizationOperations,
    getOrganizationSummary,
    type OrganizationCandidate,
    type OrganizationCandidateDetail,
    type OrganizationCollectiveDecision,
    type OrganizationLineageEdge,
    type OrganizationOperation,
    type OrganizationSummary,
  } from '../api/organizations'
  import type { ResearchSelection } from '../research/selection'

  interface Props {
    runId: string
    selection: ResearchSelection
  }

  let { runId }: Props = $props()

  type Status = 'loading' | 'available' | 'empty' | 'unavailable' | 'error'

  let status = $state<Status>('loading')
  let reason = $state<string | null>(null)
  let summary = $state<OrganizationSummary | null>(null)
  let candidates = $state<OrganizationCandidate[]>([])
  let lineage = $state<OrganizationLineageEdge[]>([])
  let operations = $state<OrganizationOperation[]>([])
  let collectiveDecisions = $state<OrganizationCollectiveDecision[]>([])
  let collectiveRecognition = $state<string>('')
  let detail = $state<OrganizationCandidateDetail | null>(null)
  let statusFilter = $state<string>('')
  let operationDomain = $state<string>('')

  async function load(): Promise<void> {
    status = 'loading'
    reason = null
    detail = null
    try {
      summary = await getOrganizationSummary(runId)
      const page = await getOrganizationCandidates(runId, { limit: 200 })
      candidates = page.items
      const edges = await getOrganizationLineage(runId, { limit: 200 })
      lineage = edges.items
      const operationPage = await getOrganizationOperations(runId, { limit: 200 })
      operations = operationPage.items
      const agencyPage = await getOrganizationCollectiveAgency(runId, {
        limit: 200,
      })
      collectiveDecisions = agencyPage.items
      status = candidates.length === 0 ? 'empty' : 'available'
    } catch (error) {
      if (error instanceof ApiClientError) {
        reason = error.code
        status = error.code === 'organization_disabled' ? 'unavailable' : 'error'
        return
      }
      reason = 'organization_read_failed'
      status = 'error'
    }
  }

  async function selectCandidate(organizationId: string): Promise<void> {
    detail = await getOrganizationCandidate(runId, organizationId)
  }

  $effect(() => {
    void runId
    void load()
  })

  const filtered = $derived(
    statusFilter === ''
      ? candidates
      : candidates.filter((item) => item.status === statusFilter),
  )

  const filteredOperations = $derived(
    operationDomain === ''
      ? operations
      : operations.filter((item) => item.domain === operationDomain),
  )

  const filteredDecisions = $derived(
    collectiveRecognition === ''
      ? collectiveDecisions
      : collectiveDecisions.filter(
          (item) => item.recognition === collectiveRecognition,
        ),
  )
</script>

<section class="organizations">
  <header>
    <h1>Organization candidates</h1>
    <p class="note">
      Analytical candidates derived from detached owner beliefs. Not governments,
      churches, corporations, or any hard-coded organization type; membership may
      overlap and self-identification is optional.
    </p>
  </header>

  {#if status === 'loading'}
    <p>Loading organization snapshot…</p>
  {:else if status === 'unavailable'}
    <p class="unavailable">Organization publication is disabled ({reason}).</p>
  {:else if status === 'empty'}
    <p class="empty">No published organization snapshot for this run.</p>
  {:else if status === 'error'}
    <p class="error">Organization read failed ({reason}).</p>
  {:else if summary !== null}
    <dl class="summary">
      <div><dt>Windows</dt><dd>{summary.window_count}</dd></div>
      <div><dt>Candidates</dt><dd>{summary.candidate_count}</dd></div>
      <div><dt>Lineage edges</dt><dd>{summary.edge_count}</dd></div>
      <div><dt>Operations</dt><dd>{summary.operation_count}</dd></div>
      <div><dt>Proposals</dt><dd>{summary.collective_proposal_count}</dd></div>
      <div><dt>Amendments</dt><dd>{summary.collective_amendment_count}</dd></div>
      <div><dt>Support</dt><dd>{summary.collective_support_count}</dd></div>
      <div><dt>Opposition</dt><dd>{summary.collective_oppose_count}</dd></div>
      <div><dt>Abstention</dt><dd>{summary.collective_abstain_count}</dd></div>
      <div><dt>Collective decisions</dt><dd>{summary.collective_decision_count}</dd></div>
      <div><dt>Implementations</dt><dd>{summary.collective_implementation_count}</dd></div>
      <div><dt>Unimplemented</dt><dd>{summary.unimplemented_decision_count}</dd></div>
      <div><dt>Coverage</dt><dd>{summary.coverage.observed}/{summary.coverage.expected}</dd></div>
      {#if summary.provenance_code !== 'ok'}
        <div><dt>Provenance</dt><dd>{summary.provenance_code}</dd></div>
      {/if}
    </dl>

    <label class="filter">
      Status
      <select class="status-filter" bind:value={statusFilter}>
        <option value="">all</option>
        <option value="recognized">recognized</option>
        <option value="partial">partial</option>
        <option value="disputed">disputed</option>
        <option value="fragmented">fragmented</option>
        <option value="temporary">temporary</option>
        <option value="dissolved">dissolved</option>
      </select>
    </label>

    <table>
      <thead>
        <tr>
          <th>Candidate</th>
          <th>Status</th>
          <th>Scope</th>
          <th>Members</th>
          <th>Roles</th>
          <th>Goals</th>
          <th>Records</th>
          <th>Operations</th>
        </tr>
      </thead>
      <tbody>
        {#each filtered as candidate (candidate.organization_id)}
          <tr>
            <td>
              <button type="button" onclick={() => void selectCandidate(candidate.organization_id)}>
                <code>{candidate.organization_id}</code>
              </button>
            </td>
            <td>{candidate.status}</td>
            <td>{candidate.temporal_scope}</td>
            <td>{candidate.member_count}</td>
            <td>{candidate.role_count}</td>
            <td>{candidate.goal_count}</td>
            <td>{candidate.record_count}</td>
            <td>
              {candidate.operation_count}
              {#if candidate.contested_operation_count > 0}
                <span class="contested">contested</span>
              {/if}
            </td>
          </tr>
        {/each}
      </tbody>
    </table>

    {#if detail !== null}
      <article class="detail">
        <h3>{detail.organization_id}</h3>
        <ul class="members">
          {#each detail.members as member (member.member_id)}
            <li>{member.member_id}: {member.status} ({member.temporal_scope})</li>
          {/each}
        </ul>
        <ul class="structure">
          {#each detail.structure as item (`${item.kind}-${item.anchor_id}`)}
            <li>{item.kind}: {item.anchor_id} ({item.status})</li>
          {/each}
        </ul>
        <h4>Operations</h4>
        <ul class="detail-operations">
          {#each detail.operations as operation (operation.operation_id)}
            <li>
              <code>{operation.operation_id}</code>
              {operation.domain} / {operation.act} / {operation.stance} /
              {operation.authority_basis} / {operation.provenance_code}
              {#if operation.stance === 'disputed' || operation.contest_count > 0}
                <span class="contested">contested</span>
              {/if}
            </li>
          {/each}
        </ul>
      </article>
    {/if}

    <h3>Operations</h3>
    <label class="filter">
      Domain
      <select
        class="operation-domain"
        value={operationDomain}
        onchange={(event) => (operationDomain = event.currentTarget.value)}
      >
        <option value="">all</option>
        <option value="resource_control">resource_control</option>
        <option value="storage">storage</option>
        <option value="record_keeping">record_keeping</option>
        <option value="membership_admission">membership_admission</option>
        <option value="membership_departure">membership_departure</option>
        <option value="role_assignment">role_assignment</option>
        <option value="procedure_action">procedure_action</option>
        <option value="internal_commitment">internal_commitment</option>
      </select>
    </label>
    <table class="operations">
      <thead>
        <tr>
          <th>Operation</th>
          <th>Domain</th>
          <th>Act</th>
          <th>Stance</th>
          <th>Authority</th>
          <th>Provenance</th>
          <th>Tick</th>
          <th>Anchor</th>
          <th>Support</th>
          <th>Contest</th>
        </tr>
      </thead>
      <tbody>
        {#each filteredOperations as operation (operation.operation_id)}
          <tr>
            <td><code>{operation.operation_id}</code></td>
            <td>{operation.domain}</td>
            <td>{operation.act}</td>
            <td>
              {operation.stance}
              {#if operation.stance === 'disputed' || operation.contest_count > 0}
                <span class="contested">contested</span>
              {/if}
            </td>
            <td>{operation.authority_basis}</td>
            <td>{operation.provenance_code}</td>
            <td>{operation.tick}</td>
            <td>{operation.anchor_kind}</td>
            <td>{operation.support_count}</td>
            <td>{operation.contest_count}</td>
          </tr>
        {/each}
      </tbody>
    </table>


    <h3>Collective agency</h3>
    <p class="note">
      Collective decisions are owner beliefs about a recognized process. Sabotage
      is an owner attribution, not an objective fact.
    </p>
    <label class="filter">
      Recognition
      <select
        class="recognition-filter"
        value={collectiveRecognition}
        onchange={(event) =>
          (collectiveRecognition = (event.currentTarget as HTMLSelectElement).value)}
      >
        <option value="">all</option>
        <option value="recognized">recognized</option>
        <option value="contested">contested</option>
        <option value="unrecognized">unrecognized</option>
        <option value="expired">expired</option>
        <option value="unknown">unknown</option>
      </select>
    </label>
    <table class="collective-agency">
      <thead>
        <tr>
          <th>Decision</th>
          <th>Recognition</th>
          <th>Support</th>
          <th>Oppose</th>
          <th>Abstain</th>
          <th>Procedure</th>
          <th>Implementation</th>
          <th>Tick</th>
        </tr>
      </thead>
      <tbody>
        {#each filteredDecisions as decision (decision.decision_id)}
          <tr>
            <td>{decision.decision_id}</td>
            <td>{decision.recognition}</td>
            <td>{decision.support_count}</td>
            <td>{decision.oppose_count}</td>
            <td>{decision.abstain_count}</td>
            <td>{decision.procedure_ref ?? '—'}</td>
            <td>{decision.implementation_status}</td>
            <td>{decision.decided_tick}</td>
          </tr>
          <tr>
            <td colspan="8">
              <ul class="implementations">
                {#each decision.implementations as implementation (implementation.implementation_id)}
                  <li>
                    {implementation.actor_ref}: {implementation.status}
                    ({implementation.provenance_code})
                  </li>
                {/each}
              </ul>
            </td>
          </tr>
        {/each}
      </tbody>
    </table>

    <h3>Lineage</h3>
    <ul class="lineage">
      {#each lineage as edge (`${edge.kind}-${edge.from_id}-${edge.to_id}-${edge.tick}`)}
        <li>
          {edge.kind}: {edge.from_id ?? '—'} → {edge.to_id ?? '—'} ({edge.tick})
        </li>
      {/each}
    </ul>
  {/if}
</section>

<style>
  .organizations {
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }
  .note {
    color: #555;
    font-size: 0.9rem;
  }
  .summary {
    display: flex;
    flex-wrap: wrap;
    gap: 1.5rem;
  }
  .summary dt {
    font-size: 0.75rem;
    text-transform: uppercase;
    color: #666;
  }
  .summary dd {
    margin: 0;
    font-variant-numeric: tabular-nums;
  }
  table {
    border-collapse: collapse;
    width: 100%;
  }
  th,
  td {
    border-bottom: 1px solid #ddd;
    padding: 0.35rem 0.5rem;
    text-align: left;
  }
  .unavailable,
  .empty {
    color: #666;
  }
  .error {
    color: #a40000;
  }
  .contested {
    background: #fdecea;
    color: #a40000;
    border-radius: 0.25rem;
    padding: 0 0.25rem;
    font-size: 0.8rem;
  }
</style>
