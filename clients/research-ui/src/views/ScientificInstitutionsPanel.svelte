<script lang="ts">
  import { onMount } from 'svelte'
  import { ApiClientError } from '../api/client'
  import {
    getScientificInstitutionsPage,
    getScientificInstitutionsSummary,
    type ScientificInstitutionsRow,
    type ScientificInstitutionsSection,
    type ScientificInstitutionsSummary,
  } from '../api/scientificInstitutions'
  import type { ResearchSelection } from '../research/selection'

  interface Props {
    runId: string
    selection: ResearchSelection
  }

  let { runId }: Props = $props()

  type Status =
    | 'loading'
    | 'ready'
    | 'empty'
    | 'disabled'
    | 'missing'
    | 'error'
  let status = $state<Status>('loading')
  let reason = $state<string | null>(null)
  let summary = $state<ScientificInstitutionsSummary | null>(null)
  let publicationId = $state<string | null>(null)
  let section = $state<ScientificInstitutionsSection>('windows')
  let rows = $state<ScientificInstitutionsRow[]>([])
  let cursor = $state<string | null>(null)
  let generation = 0
  let loadedFor = ''

  const sections: { id: ScientificInstitutionsSection; label: string }[] = [
    { id: 'windows', label: 'Windows & coverage' },
    { id: 'practice', label: 'Practice' },
    { id: 'signals', label: 'Roles & carriers' },
    { id: 'lineage', label: 'Lineage' },
  ]

  function fail(error: unknown): void {
    if (error instanceof ApiClientError) {
      if (error.code.endsWith('_disabled') || error.status === 503) {
        status = 'disabled'
        reason = error.code
      } else if (error.code.endsWith('_not_found') || error.status === 404) {
        status = 'missing'
        reason = error.code
      } else {
        status = 'error'
        reason = error.message || error.code
      }
    } else {
      status = 'error'
      reason = 'Unable to load scientific practice evidence.'
    }
  }

  async function load(reset: boolean): Promise<void> {
    const current = ++generation
    status = 'loading'
    reason = null
    try {
      const next = await getScientificInstitutionsPage(runId, section, {
        ...(publicationId === null ? {} : { publicationId }),
        ...(reset || !cursor ? {} : { cursor }),
      })
      if (current !== generation) return
      if (publicationId !== null && next.publication_id !== publicationId) {
        throw new ApiClientError(409, 'scientific_institutions_publication_changed')
      }
      rows = reset ? next.rows : [...rows, ...next.rows]
      cursor = next.next_cursor
      publicationId = next.publication_id
      status = rows.length === 0 ? 'empty' : 'ready'
    } catch (error) {
      if (current !== generation) return
      fail(error)
    }
  }

  async function loadSummary(): Promise<void> {
    const current = ++generation
    status = 'loading'
    reason = null
    try {
      const next = await getScientificInstitutionsSummary(runId)
      if (current !== generation) return
      summary = next
      publicationId = next.publication_id
      cursor = null
      await load(true)
    } catch (error) {
      if (current !== generation) return
      fail(error)
    }
  }

  function selectSection(next: ScientificInstitutionsSection): void {
    if (next === section) return
    section = next
    cursor = null
    void load(true)
  }

  function field(row: ScientificInstitutionsRow, name: string): string {
    const found = (row.fields ?? []).find(
      (item: [string, string | number]) => item[0] === name,
    )
    return found ? String(found[1]) : '—'
  }

  function trackKey(row: ScientificInstitutionsRow): string {
    return String(row.row_key ?? '')
  }

  onMount(() => {
    loadedFor = runId
    void loadSummary()
  })

  $effect(() => {
    if (loadedFor !== '' && loadedFor !== runId) {
      loadedFor = runId
      rows = []
      cursor = null
      summary = null
      publicationId = null
      void loadSummary()
    }
  })
</script>

<section class="scientific-institutions" aria-label="Scientific institutions">
  <header>
    <div>
      <h2>Scientific institutions</h2>
      <p class="hint">
        Practice, roles, archives and instruments are research descriptions.
        A stable label means repeat practice, not truth, quality or a
        pre-defined institution type.
      </p>
    </div>
    {#if summary}
      <p class="meta">
        publication {summary.publication_id} · {summary.counts.practice ?? 0} practice rows ·
        {summary.summary.stable_row_count ?? 0} stable windows ·
        {summary.summary.episode_count ?? 0} episodes
      </p>
    {/if}
  </header>

  <nav aria-label="Scientific practice sections">
    {#each sections as item}
      <button
        type="button"
        class:active={item.id === section}
        onclick={() => selectSection(item.id)}
      >
        {item.label}
      </button>
    {/each}
  </nav>

  <p class="axis">
    Action facts, owner claims and analytical links stay separate. Coverage
    unknown is never the same as a complete empty window.
  </p>

  {#if status === 'loading'}
    <p class="status">Loading scientific practice evidence…</p>
  {:else if status === 'empty'}
    <p class="status">
      No retained rows in this section. A completely observed empty window is
      reported above as coverage, not as missing evidence.
    </p>
  {:else if status === 'disabled'}
    <p class="status">
      Scientific institution reads are disabled for this deployment
      ({reason ?? 'scientific_institutions_disabled'}).
    </p>
  {:else if status === 'missing'}
    <p class="status">
      No matching run or publication is available
      ({reason ?? 'scientific_institutions_not_found'}).
    </p>
  {:else if status === 'error'}
    <p class="status error">
      {reason ?? 'Scientific practice evidence is unavailable.'}
    </p>
  {:else}
    <table>
      <thead>
        <tr>
          <th>Window</th>
          <th>Key</th>
          <th>Status</th>
          {#if section === 'windows'}
            <th>Coverage</th>
            <th>Counts</th>
          {:else if section === 'practice'}
            <th>Organization</th>
            <th>Activity</th>
            <th>Actors</th>
            <th>Carriers</th>
          {:else if section === 'signals'}
            <th>Signal</th>
            <th>Actors</th>
            <th>Carriers</th>
          {:else}
            <th>Record</th>
            <th>Transition</th>
            <th>Known at</th>
          {/if}
        </tr>
      </thead>
      <tbody>
        {#each rows as row (trackKey(row))}
          <tr>
            <td>{row.window_index}</td>
            <td>{row.row_key}</td>
            {#if section === 'windows'}
              <td>{field(row, 'state')}</td>
              <td>
                execution {field(row, 'execution_coverage')} · carrier
                {field(row, 'carrier_coverage')} · organization
                {field(row, 'organization_coverage')}
              </td>
              <td>
                rows {field(row, 'row_count')} · unassigned
                {field(row, 'unassigned')} · ambiguous
                {field(row, 'ambiguous')}
              </td>
            {:else if section === 'practice'}
              <td>{field(row, 'status')}</td>
              <td>{field(row, 'organization_token')}</td>
              <td>{field(row, 'operator')} / {field(row, 'process_token')}</td>
              <td>{field(row, 'actor_tokens')}</td>
              <td>{field(row, 'surviving_carrier_tokens')}</td>
            {:else if section === 'signals'}
              <td>{field(row, 'signal')}</td>
              <td>{field(row, 'actor_tokens')}</td>
              <td>{field(row, 'carrier_tokens')}</td>
            {:else}
              <td>{field(row, 'record_kind')}</td>
              <td>{field(row, 'transition_kind')}</td>
              <td>{field(row, 'known_at_window')}</td>
            {/if}
          </tr>
        {/each}
      </tbody>
    </table>
    {#if cursor}
      <button type="button" onclick={() => void load(false)}>Load more</button>
    {/if}
  {/if}
</section>

<style>
  .scientific-institutions {
    display: grid;
    gap: 0.75rem;
  }
  header {
    display: flex;
    justify-content: space-between;
    gap: 1rem;
    align-items: end;
  }
  h2 {
    margin: 0;
  }
  .hint,
  .meta,
  .axis,
  .status {
    margin: 0;
    color: #52606d;
    font-size: 0.85rem;
  }
  nav {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
  }
  nav button.active {
    font-weight: 600;
    border-color: #334e68;
  }
  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.8rem;
  }
  th,
  td {
    text-align: left;
    border-bottom: 1px solid #d9e2ec;
    padding: 0.3rem;
    vertical-align: top;
  }
  .error {
    color: #9b1c1c;
  }
</style>
