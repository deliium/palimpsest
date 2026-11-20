<script lang="ts">
  import { onMount } from 'svelte'
  import { ApiClientError } from '../api/client'
  import {
    getCompetingTheoriesPage,
    getCompetingTheoriesSummary,
    type CompetingTheoriesRow,
    type CompetingTheoriesSection,
    type CompetingTheoriesSummary,
  } from '../api/competingTheories'
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
  let summary = $state<CompetingTheoriesSummary | null>(null)
  let publicationId = $state<string | null>(null)
  let section = $state<CompetingTheoriesSection>('theories')
  let rows = $state<CompetingTheoriesRow[]>([])
  let cursor = $state<string | null>(null)
  let generation = 0

  const sections: { id: CompetingTheoriesSection; label: string }[] = [
    { id: 'theories', label: 'Theories' },
    { id: 'support', label: 'Declared support' },
    { id: 'citations', label: 'Citations' },
    { id: 'predictions', label: 'Predictions' },
    { id: 'failures', label: 'Failures' },
    { id: 'transmission', label: 'Communication & teaching' },
    { id: 'coverage', label: 'Coverage' },
  ]

  async function load(reset: boolean): Promise<void> {
    const current = ++generation
    status = 'loading'
    reason = null
    try {
      const next = await getCompetingTheoriesPage(runId, section, {
        ...(publicationId === null ? {} : { publicationId }),
        ...(reset || !cursor ? {} : { cursor }),
      })
      if (current !== generation) return
      rows = reset ? next.rows : [...rows, ...next.rows]
      cursor = next.next_cursor
      publicationId = next.publication_id
      status = rows.length === 0 ? 'empty' : 'ready'
    } catch (error) {
      if (current !== generation) return
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
        reason = 'Unable to load competing theory evidence.'
      }
    }
  }

  async function loadSummary(): Promise<void> {
    try {
      summary = await getCompetingTheoriesSummary(runId, publicationId ?? undefined)
      publicationId = summary.publication_id
      await load(true)
    } catch (error) {
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
        reason = 'Unable to load competing theory evidence.'
      }
    }
  }

  function selectSection(next: CompetingTheoriesSection): void {
    if (next === section) return
    section = next
    cursor = null
    void load(true)
  }

  onMount(() => {
    void loadSummary()
  })
</script>

<section class="competing-theories" aria-label="Competing theories">
  <header>
    <div>
      <h2>Competing theories</h2>
      <p class="hint">
        Declared support and observed predictive performance are separate axes.
        Teaching and citations are testimony, not verified evidence.
      </p>
    </div>
    {#if summary}
      <p class="meta">
        publication {summary.publication_id} · {summary.summary.claim_count ?? 0} claims ·
        {summary.summary.support_edge_count ?? 0} declared support edges ·
        {summary.summary.failure_count ?? 0} observed failures
      </p>
    {/if}
  </header>

  <nav aria-label="Theory sections">
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

  {#if section === 'support' || section === 'transmission'}
    <p class="axis">
      Social axis: declared support and delivery receipts only. Teaching and
      citations are testimony, not verified evidence.
    </p>
  {:else if section === 'predictions' || section === 'failures'}
    <p class="axis">
      Predictive axis: owner-observed same-case outcomes only. Pending and
      missing cases stay outside the observed denominator and are never failures.
    </p>
  {:else if section === 'theories' || section === 'citations' || section === 'coverage'}
    <p class="axis">
      Structure and coverage: rivalry is same-context, different predicted
      category. No champion, rank or truth verdict is selected.
    </p>
  {/if}

  {#if status === 'loading'}
    <p class="status">Loading competing theory evidence…</p>
  {:else if status === 'empty'}
    <p class="status">No retained rows in this section.</p>
  {:else if status === 'disabled'}
    <p class="status">
      Competing theory reads are disabled for this deployment ({reason ?? 'competing_theories_disabled'}).
    </p>
  {:else if status === 'missing'}
    <p class="status">
      No matching run or publication is available ({reason ?? 'competing_theories_not_found'}).
    </p>
  {:else if status === 'error'}
    <p class="status error">{reason ?? 'Competing theory evidence is unavailable.'}</p>
  {:else}
    <table>
      <thead>
        <tr>
          <th>Window</th>
          <th>Theory</th>
          <th>Key</th>
          <th>Fields</th>
        </tr>
      </thead>
      <tbody>
        {#each rows as row (row.row_key)}
          <tr>
            <td>{row.window_start}–{row.window_end}</td>
            <td>{row.theory_id}</td>
            <td>{row.row_key}</td>
            <td>
              {#each row.fields as field}
                <span class="field">{field[0]}={field[1]}</span>
              {/each}
            </td>
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
  .competing-theories {
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
    font-size: 1rem;
  }
  .hint,
  .meta,
  .status,
  .axis {
    margin: 0.25rem 0 0;
    color: var(--muted, #667);
    font-size: 0.8rem;
  }
  nav {
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem;
  }
  button {
    border: 1px solid var(--border, #ccd);
    background: transparent;
    border-radius: 0.35rem;
    padding: 0.25rem 0.55rem;
    cursor: pointer;
  }
  button.active {
    background: var(--accent, #245);
    color: white;
  }
  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.78rem;
  }
  th,
  td {
    text-align: left;
    border-bottom: 1px solid var(--border, #dde);
    padding: 0.3rem;
    vertical-align: top;
  }
  .field {
    display: inline-block;
    margin-right: 0.45rem;
  }
  .error {
    color: #a22;
  }
</style>
