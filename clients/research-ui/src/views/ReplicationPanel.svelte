<script lang="ts">
  import { ApiClientError } from '../api/client'
  import {
    getReplicationPage,
    getReplicationSummary,
    type ReplicationQuery,
    type ReplicationPage,
    type ReplicationResultRow,
    type ReplicationRow,
    type ReplicationSection,
    type ReplicationSummary,
  } from '../api/replication'
  import type { ResearchSelection } from '../research/selection'

  interface Props {
    runId: string
    selection: ResearchSelection
  }

  let { runId }: Props = $props()

  type Status = 'loading' | 'ready' | 'empty' | 'unavailable' | 'error'
  let status = $state<Status>('loading')
  let reason = $state<string | null>(null)
  let summary = $state<ReplicationSummary | null>(null)
  let publicationId = $state<string | null>(null)
  let windowIndex = $state<number | null>(null)
  let designToken = $state('')
  let collaborationToken = $state('')
  let generation = 0

  const sections: { id: ReplicationSection; label: string }[] = [
    { id: 'designs', label: 'Designs and lineage' },
    { id: 'attempts', label: 'Attempts and conditions' },
    { id: 'results', label: 'Measurements and reports' },
    { id: 'comparisons', label: 'Replication comparisons' },
    { id: 'interpretations', label: 'Owner interpretations' },
    { id: 'collaborations', label: 'Collaboration declarations' },
    { id: 'coverage', label: 'Coverage' },
  ]

  type SectionState = {
    rows: ReplicationRow[]
    cursor: string | null
    loading: boolean
    error: string | null
  }

  function blankSections(): Record<string, SectionState> {
    const value: Record<string, SectionState> = {}
    for (const section of sections) {
      value[section.id] = { rows: [], cursor: null, loading: false, error: null }
    }
    return value
  }

  let pages = $state<Record<string, SectionState>>(blankSections())

  function pageFor(section: ReplicationSection): SectionState {
    return pages[section]!
  }

  function filters(section: ReplicationSection): ReplicationQuery {
    const query: ReplicationQuery = {}
    if (publicationId) query.publicationId = publicationId
    if (windowIndex !== null) query.windowIndex = windowIndex
    const narrows = !['results', 'coverage', 'designs'].includes(section)
    if (narrows && designToken) query.designToken = designToken
    if (narrows && collaborationToken) query.collaborationToken = collaborationToken
    return query
  }

  async function load(selected?: string): Promise<void> {
    const current = ++generation
    status = 'loading'
    reason = null
    try {
      summary = await getReplicationSummary(runId, publicationId ?? undefined)
      if (current !== generation) return
      publicationId = summary.publication_id
      pages = blankSections()
      const wanted = selected ? [selected] : sections.map((s) => s.id)
      await Promise.all(
        wanted.map(async (section) => {
          await loadSection(section as ReplicationSection, current)
        }),
      )
      if (current !== generation) return
      const hasRows = Object.values(pages).some((page) => page.rows.length > 0)
      status = hasRows ? 'ready' : 'empty'
    } catch (error) {
      if (current !== generation) return
      if (error instanceof ApiClientError && error.status === 503) {
        status = 'unavailable'
        reason = error.code
      } else {
        status = 'error'
        reason = error instanceof ApiClientError ? error.code : 'request_failed'
      }
    }
  }

  async function loadSection(
    section: ReplicationSection,
    current = generation,
  ): Promise<void> {
    const page = pages[section]!
    if (page.loading) return
    page.loading = true
    page.error = null
    try {
      const query = filters(section)
      query.limit = 100
      if (page.cursor) query.cursor = page.cursor
      const result = await getReplicationPage(runId, section, query)
      if (current !== generation) return
      const existing = new Set(page.rows.map((row) => String(row.row_token)))
      const appended = result.rows.filter(
        (row) => !existing.has(String(row.row_token)),
      )
      page.rows = [...page.rows, ...appended]
      page.cursor = result.next_cursor
    } catch (error) {
      if (current !== generation) return
      page.error = error instanceof ApiClientError ? error.code : 'request_failed'
      if (page.error === 'scientific_replication_cursor_expired') {
        page.cursor = null
      }
    } finally {
      page.loading = false
    }
  }

  function isReport(row: ReplicationRow): boolean {
    return row.row_kind === 'report'
  }

  function uncertainty(row: ReplicationRow): string {
    if (!isReport(row)) return 'objective outcome'
    const measurement = (
      row as unknown as ReplicationResultRow & {
        fact: { measurement: { uncertainty_kind: string; possible_outcomes: string[] } }
      }
    ).fact.measurement
    if (measurement.uncertainty_kind === 'unreported') return 'uncertainty unreported'
    return `declared alternatives: ${measurement.possible_outcomes.join(', ')}`
  }

  $effect(() => {
    void load()
  })
</script>

<section class="panel" aria-labelledby="replication-heading">
  <header>
    <h2 id="replication-heading">Scientific replication</h2>
    {#if summary}
      <p class="meta">
        Publication {summary.publication_id} · coverage {summary.summary?.coverage ?? 'unknown'} ·
        availability {summary.summary?.availability ?? 'unknown'}
      </p>
    {/if}
    <div class="filters">
      <label>
        Window
        <select
          aria-label="Analysis window"
          value={windowIndex ?? ''}
          onchange={(event) => {
            const value = (event.currentTarget as HTMLSelectElement).value
            windowIndex = value === '' ? null : Number(value)
            void load()
          }}
        >
          <option value="">All windows</option>
          {#each Array(512) as _, index}
            <option value={index}>{index}</option>
          {/each}
        </select>
      </label>
      <label>
        Design token
        <input bind:value={designToken} aria-label="Design token" />
      </label>
      <label>
        Collaboration token
        <input bind:value={collaborationToken} aria-label="Collaboration token" />
      </label>
      <button type="button" onclick={() => void load()}>Reload</button>
    </div>
  </header>

  {#if status === 'loading'}
    <p role="status">Loading replication evidence…</p>
  {:else if status === 'unavailable'}
    <p role="status">Replication publication is disabled or unavailable.</p>
  {:else if status === 'empty'}
    <p role="status">No published replication evidence for this run.</p>
  {:else if status === 'error'}
    <p role="alert">Could not read replication evidence: {reason}</p>
  {:else}
    {#each sections as section}
      <article>
        <h3>{section.label}</h3>
        {#if section.id === 'results' || section.id === 'coverage'}
          <p class="scope">Selected window; not narrowed by design/collaboration.</p>
        {/if}
        {#if pageFor(section.id).error}
          <p role="alert">{pageFor(section.id).error}</p>
        {/if}
        {#if pageFor(section.id).rows.length === 0}
          <p>No retained rows in this section.</p>
        {:else}
          <ul>
            {#each pageFor(section.id).rows as row (row.row_token)}
              <li>
                <code>{row.row_token}</code>
                {#if section.id === 'results'}
                  <span>{isReport(row) ? 'Owner report' : 'Objective execution'}</span>
                  {#if isReport(row)}
                    <span>{(row.fact as any).measurement.outcome ?? 'no observed outcome'}</span>
                    <span>{uncertainty(row)}</span>
                  {:else}
                    <span>{(row.fact as any).outcome}</span>
                  {/if}
                {:else if section.id === 'comparisons'}
                  <span>{String(row.appraisal ?? '')}</span>
                  <span>{String(row.condition_comparison ?? '')}</span>
                  <span>{String(row.evidence_qualification ?? '')}</span>
                {:else}
                  <span>{String(row.layer ?? '')}</span>
                {/if}
              </li>
            {/each}
          </ul>
        {/if}
        {#if pageFor(section.id).cursor}
          <button
            type="button"
            disabled={pageFor(section.id).loading}
            onclick={() => void loadSection(section.id)}
          >
            Load more
          </button>
        {/if}
      </article>
    {/each}
  {/if}
</section>
