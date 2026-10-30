<script lang="ts">
  import { ApiClientError } from '../api/client'
  import {
    getOrganizationCandidate,
    getOrganizationCandidates,
    getOrganizationLineage,
    getOrganizationSummary,
    type OrganizationCandidate,
    type OrganizationCandidateDetail,
    type OrganizationLineageEdge,
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
  let detail = $state<OrganizationCandidateDetail | null>(null)
  let statusFilter = $state<string>('')

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
      <div><dt>Coverage</dt><dd>{summary.coverage.observed}/{summary.coverage.expected}</dd></div>
      {#if summary.provenance_code !== 'ok'}
        <div><dt>Provenance</dt><dd>{summary.provenance_code}</dd></div>
      {/if}
    </dl>

    <label class="filter">
      Status
      <select bind:value={statusFilter}>
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
      </article>
    {/if}

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
</style>
