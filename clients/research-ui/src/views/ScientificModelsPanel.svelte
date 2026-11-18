<script lang="ts">
  import { ApiClientError } from '../api/client'
  import {
    getScientificModelsPage,
    getScientificModelsSummary,
    type ScientificModelsQuery,
    type ScientificModelsRow,
    type ScientificModelsSection,
    type ScientificModelsSummary,
  } from '../api/scientificModels'
  import type { ResearchSelection } from '../research/selection'

  interface Props {
    runId: string
    selection: ResearchSelection
  }

  let { runId }: Props = $props()

  type Status = 'loading' | 'ready' | 'empty' | 'unavailable' | 'error'
  let status = $state<Status>('loading')
  let reason = $state<string | null>(null)
  let summary = $state<ScientificModelsSummary | null>(null)
  let publicationId = $state<string | null>(null)
  let section = $state<ScientificModelsSection>('predictions')
  let rows = $state<ScientificModelsRow[]>([])
  let cursor = $state<string | null>(null)
  let loadingPage = $state(false)
  let generation = 0

  const sections: { id: ScientificModelsSection; label: string }[] = [
    { id: 'models', label: 'Models' },
    { id: 'predictions', label: 'Prior predictions' },
    { id: 'outcomes', label: 'Observed outcomes' },
    { id: 'calibration', label: 'Calibration' },
    { id: 'revisions', label: 'Revisions' },
    { id: 'comparisons', label: 'Model comparison' },
    { id: 'coverage', label: 'Coverage' },
  ]

  function query(): ScientificModelsQuery {
    const value: ScientificModelsQuery = {}
    if (publicationId) value.publicationId = publicationId
    return value
  }

  async function loadPage(reset: boolean): Promise<void> {
    const current = generation
    loadingPage = true
    try {
      const page = await getScientificModelsPage(runId, section, {
        ...query(),
        ...(reset || !cursor ? {} : { cursor }),
      })
      if (current !== generation) return
      rows = reset ? page.rows : [...rows, ...page.rows]
      cursor = page.next_cursor
      status = rows.length === 0 ? 'empty' : 'ready'
      reason = null
    } catch (error) {
      if (current !== generation) return
      const code = error instanceof ApiClientError ? error.code : 'scientific_models_unavailable'
      status = 'error'
      reason = code
    } finally {
      loadingPage = false
    }
  }

  async function load(): Promise<void> {
    const current = ++generation
    status = 'loading'
    reason = null
    try {
      summary = await getScientificModelsSummary(runId, publicationId ?? undefined)
      if (current !== generation) return
      publicationId = summary.publication_id
      cursor = null
      await loadPage(true)
    } catch (error) {
      if (current !== generation) return
      const code = error instanceof ApiClientError ? error.code : 'scientific_models_unavailable'
      const disabled =
        code.includes('disabled') ||
        (error instanceof ApiClientError && error.status === 503)
      status = disabled ? 'unavailable' : 'error'
      reason = code
    }
  }

  async function selectSection(next: ScientificModelsSection): Promise<void> {
    section = next
    cursor = null
    rows = []
    generation += 1
    await loadPage(true)
  }

  $effect(() => {
    void load()
  })
</script>

<main class="panel" data-testid="scientific-models-panel">
  <header>
    <h2>Scientific models</h2>
    <p class="note">
      Prior forecasts and owner observations. No truth, accuracy guarantee or
      universal model winner is shown.
    </p>
    <ul class="legend">
      <li><strong>Predictive probability</strong> comes from a frozen prior forecast.</li>
      <li><strong>Owner-observed outcome</strong> is an observation, not truth.</li>
      <li><strong>Retained-cohort calibration</strong> applies within one target, context and horizon.</li>
      <li><strong>Lower loss on paired observations</strong> is descriptive, not a winner claim.</li>
      <li><strong>Net resource change</strong> is not isolated regeneration.</li>
    </ul>
    <p class="note">
      Pending forecasts stay right-censored. Unavailable, not attempted, not
      comparable and insufficient samples remain distinct; zero is not unavailable.
    </p>
  </header>

  {#if status === 'loading'}
    <p>Loading scientific models…</p>
  {:else if status === 'unavailable'}
    <p class="disabled">Scientific-model artifacts are not configured.</p>
  {:else if status === 'error'}
    <p class="error">{reason ?? 'scientific_models_unavailable'}</p>
  {:else if summary}
    <section class="counts">
      <p>Publication <code>{summary.publication_id}</code></p>
      <p>Coverage <strong>{summary.coverage_status}</strong></p>
      <ul>
        {#each Object.entries(summary.counts) as [name, count]}
          <li>{name}: {count}</li>
        {/each}
      </ul>
    </section>
    <nav>
      {#each sections as item}
        <button
          type="button"
          aria-pressed={section === item.id}
          onclick={() => void selectSection(item.id)}
        >
          {item.label}
        </button>
      {/each}
    </nav>
    {#if rows.length === 0}
      <p>No published rows in this section.</p>
    {:else}
      <ol>
        {#each rows as row}
          <li><pre>{JSON.stringify(row)}</pre></li>
        {/each}
      </ol>
    {/if}
    {#if cursor}
      <button type="button" onclick={() => void loadPage(false)} disabled={loadingPage}>
        Load more
      </button>
    {/if}
  {:else}
    <p>No published scientific-model snapshot.</p>
  {/if}
</main>

<style>
  .panel { display: flex; flex-direction: column; gap: 0.75rem; }
  .note { color: #555; font-size: 0.9rem; }
  .legend { color: #444; font-size: 0.85rem; margin: 0; padding-left: 1.1rem; }
  nav { display: flex; flex-wrap: wrap; gap: 0.25rem; }
  button[aria-pressed='true'] { font-weight: 600; }
  ol { max-height: 24rem; overflow: auto; }
  pre { white-space: pre-wrap; word-break: break-word; font-size: 0.75rem; }
  .error { color: #a11; }
  .disabled { color: #777; }
</style>
