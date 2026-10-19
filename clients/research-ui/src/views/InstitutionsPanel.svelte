<script lang="ts">
  import {
    ApiClientError,
    getMetricCatalog,
    getMetricDocument,
    type MetricCatalogItem,
  } from '../api/client'
  import EpistemicBadge from '../components/EpistemicBadge.svelte'

  interface Props {
    runId: string
  }

  let { runId }: Props = $props()

  const INSTITUTION_FAMILIES = [
    'institution_emergence',
    'institutional_persistence',
  ] as const

  type InstitutionCard = {
    family: string
    availability: string
    values: Array<{ key: string; value: string }>
    reason?: string
  }

  let cards = $state<InstitutionCard[]>([])
  let availability = $state('unavailable')
  let loading = $state(true)
  let error = $state<string | null>(null)

  function extractValues(payload: unknown): Array<{ key: string; value: string }> {
    if (payload === null || typeof payload !== 'object') {
      return []
    }
    const record = payload as Record<string, unknown>
    const values = record.values
    if (values === null || typeof values !== 'object') {
      return []
    }
    return Object.entries(values as Record<string, unknown>)
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([key, value]) => ({
        key,
        value: value === null ? 'unknown' : String(value),
      }))
  }

  async function loadCard(item: MetricCatalogItem): Promise<InstitutionCard> {
    try {
      const doc = await getMetricDocument(
        runId,
        item.metric_set_id,
        item.metric_family,
      )
      let values: Array<{ key: string; value: string }> = []
      try {
        values = extractValues(JSON.parse(atob(doc.payload_b64)) as unknown)
      } catch {
        values = []
      }
      return {
        family: item.metric_family,
        availability: doc.availability,
        values,
      }
    } catch (err) {
      return {
        family: item.metric_family,
        availability: 'unavailable',
        values: [],
        reason: err instanceof ApiClientError ? err.code : 'fetch_failed',
      }
    }
  }

  async function load(): Promise<void> {
    loading = true
    error = null
    try {
      const catalog = await getMetricCatalog(runId)
      availability = catalog.availability
      const items = INSTITUTION_FAMILIES.flatMap((family) =>
        catalog.items.filter((item) => item.metric_family === family),
      )
      cards = await Promise.all(items.map(loadCard))
    } catch (err) {
      error = err instanceof ApiClientError ? err.code : 'fetch_failed'
      cards = []
    } finally {
      loading = false
    }
  }

  $effect(() => {
    void runId
    void load()
  })
</script>

<section class="panel">
  <header>
    <div>
      <h2>Analytical institutions</h2>
      <p class="lede">
        Analytical pattern bundles and persistence classifications. No
        institution type exists; these labels never enter agent cognition,
        memory, or observations.
      </p>
    </div>
    <EpistemicBadge epistemic="research_inference" />
  </header>

  {#if loading}
    <p class="muted">Loading institution metrics…</p>
  {:else if error !== null}
    <p class="muted">Institution metrics unavailable: {error}</p>
  {:else if cards.length === 0}
    <p class="muted">
      No institution families in this run (catalog: {availability}).
    </p>
  {:else}
    <div class="grid">
      {#each cards as card (card.family)}
        <article class="card">
          <div class="card-head">
            <h3>{card.family}</h3>
            <EpistemicBadge epistemic="research_inference" />
          </div>
          <p class="muted">Availability: {card.availability}</p>
          {#if card.reason !== undefined}
            <p class="muted">Reason: {card.reason}</p>
          {/if}
          <dl>
            {#each card.values as item (item.key)}
              <dt>{item.key}</dt>
              <dd>{item.value}</dd>
            {/each}
          </dl>
        </article>
      {/each}
    </div>
  {/if}
</section>

<style>
  .panel {
    display: grid;
    gap: 1rem;
  }
  header,
  .card-head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 1rem;
  }
  .lede,
  .muted {
    color: var(--muted, #6b7280);
  }
  .grid {
    display: grid;
    gap: 1rem;
    grid-template-columns: repeat(auto-fit, minmax(18rem, 1fr));
  }
  .card {
    border: 1px solid var(--border, #d1d5db);
    border-radius: 0.5rem;
    padding: 0.75rem 1rem;
  }
  dl {
    display: grid;
    grid-template-columns: 1fr auto;
    gap: 0.25rem 0.75rem;
    font-size: 0.875rem;
  }
  dt {
    overflow-wrap: anywhere;
  }
  dd {
    margin: 0;
    font-variant-numeric: tabular-nums;
  }
</style>
