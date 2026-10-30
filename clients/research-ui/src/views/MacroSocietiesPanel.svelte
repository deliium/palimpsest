<script lang="ts">
  import { ApiClientError } from '../api/client'
  import {
    getMacroSocietyCandidates,
    getMacroSocietyLineage,
    getMacroSocietySummary,
    type MacroSocietyCandidate,
    type MacroSocietyLineageEdge,
    type MacroSocietySummary,
  } from '../api/macroSocieties'
  import type { ResearchSelection } from '../research/selection'

  interface Props {
    runId: string
    selection: ResearchSelection
  }

  let { runId }: Props = $props()

  type Status = 'loading' | 'available' | 'empty' | 'unavailable' | 'error'

  let status = $state<Status>('loading')
  let reason = $state<string | null>(null)
  let summary = $state<MacroSocietySummary | null>(null)
  let candidates = $state<MacroSocietyCandidate[]>([])
  let lineage = $state<MacroSocietyLineageEdge[]>([])
  let statusFilter = $state<string>('')

  async function load(): Promise<void> {
    status = 'loading'
    reason = null
    try {
      summary = await getMacroSocietySummary(runId)
      const page = await getMacroSocietyCandidates(runId, { limit: 200 })
      candidates = page.items
      const edges = await getMacroSocietyLineage(runId, { limit: 200 })
      lineage = edges.items
      status = candidates.length === 0 ? 'empty' : 'available'
    } catch (error) {
      if (error instanceof ApiClientError) {
        reason = error.code
        status = error.code === 'macro_society_disabled' ? 'unavailable' : 'error'
        return
      }
      reason = 'macro_society_read_failed'
      status = 'error'
    }
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

<section class="macro-societies">
  <header>
    <h2>Macro-society candidates</h2>
    <p class="note">
      Analytical labels derived from detached evidence. Not nations, states,
      polities, or civilizations; membership may overlap.
    </p>
  </header>

  {#if status === 'loading'}
    <p>Loading macro-society snapshot…</p>
  {:else if status === 'unavailable'}
    <p class="unavailable">Macro-society publication is disabled ({reason}).</p>
  {:else if status === 'empty'}
    <p class="empty">No published macro-society snapshot for this run.</p>
  {:else if status === 'error'}
    <p class="error">Macro-society read failed ({reason}).</p>
  {:else if summary !== null}
    <dl class="summary">
      <div><dt>Policy</dt><dd>{summary.policy_version}</dd></div>
      <div><dt>Windows</dt><dd>{summary.window_count}</dd></div>
      <div><dt>Candidates</dt><dd>{summary.candidate_count}</dd></div>
      <div><dt>Coverage</dt><dd>{summary.coverage.observed}/{summary.coverage.expected}</dd></div>
      <div><dt>Lineage edges</dt><dd>{summary.edge_count}</dd></div>
      {#if summary.provenance_code !== 'ok'}
        <div><dt>Provenance</dt><dd>{summary.provenance_code}</dd></div>
      {/if}
    </dl>

    <label class="filter">
      Status
      <select bind:value={statusFilter}>
        <option value="">all</option>
        <option value="supported">supported</option>
        <option value="fragmented">fragmented</option>
        <option value="contested">contested</option>
      </select>
    </label>

    <table>
      <thead>
        <tr>
          <th>Society</th>
          <th>Status</th>
          <th>Members</th>
          <th>Lanes</th>
          <th>Overlap</th>
        </tr>
      </thead>
      <tbody>
        {#each filtered as candidate (candidate.macro_society_id)}
          <tr>
            <td><code>{candidate.macro_society_id}</code></td>
            <td>{candidate.status}</td>
            <td>{candidate.member_count}</td>
            <td>{candidate.lane_signature.join(', ')}</td>
            <td>{candidate.overlap_person_count}</td>
          </tr>
        {/each}
      </tbody>
    </table>

    <h3>Lineage</h3>
    <ul class="lineage">
      {#each lineage as edge (`${edge.from_id}-${edge.to_id}-${edge.kind}-${edge.from_tick}`)}
        <li>
          {edge.kind}:
          {edge.from_id ?? '—'} → {edge.to_id ?? '—'}
          ({edge.from_tick}→{edge.to_tick})
        </li>
      {/each}
    </ul>
  {/if}
</section>

<style>
  .macro-societies {
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
