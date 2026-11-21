<script lang="ts">
  import { onMount } from 'svelte'
  import { ApiClientError } from '../api/client'
  import {
    getScienceDiffusionPage,
    getScienceDiffusionSummary,
    type ScienceDiffusionRow,
    type ScienceDiffusionSection,
    type ScienceDiffusionSummary,
  } from '../api/scienceDiffusion'
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
    | 'expired'
    | 'error'
  let status = $state<Status>('loading')
  let reason = $state<string | null>(null)
  let summary = $state<ScienceDiffusionSummary | null>(null)
  let publicationId = $state<string | null>(null)
  let section = $state<ScienceDiffusionSection>('coverage')
  let rows = $state<ScienceDiffusionRow[]>([])
  let cursor = $state<string | null>(null)
  let generation = 0
  let loadedFor = ''

  const sections: { id: ScienceDiffusionSection; label: string }[] = [
    { id: 'coverage', label: 'Coverage' },
    { id: 'versions', label: 'Versions' },
    { id: 'transmissions', label: 'Transmission' },
    { id: 'changes', label: 'Changes' },
    { id: 'genealogy', label: 'Knowledge genealogy' },
  ]

  function fail(error: unknown): void {
    if (error instanceof ApiClientError) {
      if (error.code.endsWith('_cursor_expired') || error.status === 410) {
        status = 'expired'
        reason = error.code
      } else if (error.code.endsWith('_disabled') || error.status === 503) {
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
      reason = 'Unable to load science diffusion evidence.'
    }
  }

  async function load(reset: boolean): Promise<void> {
    const current = ++generation
    status = 'loading'
    reason = null
    try {
      const next = await getScienceDiffusionPage(runId, section, {
        ...(publicationId === null ? {} : { publicationId }),
        ...(reset || !cursor ? {} : { cursor }),
      })
      if (current !== generation) return
      if (publicationId !== null && next.publication_id !== publicationId) {
        throw new ApiClientError(409, 'science_diffusion_publication_changed')
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
      const next = await getScienceDiffusionSummary(runId)
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

  function selectSection(next: ScienceDiffusionSection): void {
    if (next === section) return
    section = next
    cursor = null
    void load(true)
  }

  function cell(row: ScienceDiffusionRow, key: string): string {
    const value = row[key]
    if (value === undefined || value === null || value === '') return '—'
    return String(value)
  }

  function trackKey(row: ScienceDiffusionRow): string {
    return String(row.row_key ?? row.occurrence_key ?? '')
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

<section class="science-diffusion" aria-label="Science diffusion">
  <header>
    <div>
      <h2>Science diffusion</h2>
      <p class="hint">
        Delivery is not uptake. Mutation, misunderstanding, translation, loss
        and rediscovery are analytical descriptions, not truth claims.
      </p>
    </div>
    {#if summary}
      <p class="meta">
        publication {summary.publication_id} · {summary.counts.transmissions ?? 0}
        transmissions · {summary.counts.changes ?? 0} changes
      </p>
    {/if}
  </header>

  <nav aria-label="Science diffusion sections">
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
    Objective carrier events, owner-scoped uptake and analytical joins are
    labeled separately. Unavailable evidence is not an observed zero.
  </p>

  {#if status === 'loading'}
    <p class="status">Loading science diffusion evidence…</p>
  {:else if status === 'empty'}
    <p class="status">
      No retained rows in this section. A complete-empty window is shown in
      Coverage; it is not missing evidence.
    </p>
  {:else if status === 'disabled'}
    <p class="status">Science diffusion reads are disabled (503).</p>
  {:else if status === 'missing'}
    <p class="status">No published science diffusion snapshot was found.</p>
  {:else if status === 'expired'}
    <p class="status">
      This page cursor expired. Reload the same pinned publication to continue.
    </p>
    <button type="button" onclick={() => void load(true)}>Reload publication</button>
  {:else if status === 'error'}
    <p class="status">Unable to load science diffusion evidence ({reason}).</p>
  {:else}
    <table>
      <thead>
        <tr><th>Evidence</th><th>Row</th></tr>
      </thead>
      <tbody>
        {#each rows as row (trackKey(row))}
          <tr>
            <td>
              {#if section === 'coverage'}
                <span class="label objective">coverage: {cell(row, 'state')}</span>
              {:else if section === 'transmissions'}
                <span class="label uptake">stage: {cell(row, 'stage')}</span>
              {:else if section === 'genealogy'}
                <span class="label analytical">V3 link: {cell(row, 'relation')}</span>
              {:else}
                <span class="label analytical">{section}</span>
              {/if}
            </td>
            <td>
              {#each Object.entries(row) as [key, value]}
                <span class="pair">{key}: {String(value)}</span>
              {/each}
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
    {#if cursor}
      <button type="button" onclick={() => void load(false)}>Next page</button>
    {/if}
  {/if}
</section>
