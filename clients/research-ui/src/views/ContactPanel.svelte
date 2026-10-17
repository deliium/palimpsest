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

  const CONTACT_FAMILIES = [
    'society_contact',
    'contact_cultural_change',
    'contact_hybrid_practice',
    'contact_knowledge_transfer',
    'contact_lexical_borrowing',
    'contact_reputation_transfer',
  ] as const

  type ContactCard = {
    family: string
    availability: string
    values: Array<{ key: string; value: string }>
    reason?: string
  }

  let cards = $state<ContactCard[]>([])
  let availability = $state('unavailable')
  let loading = $state(true)
  let error = $state<string | null>(null)

  function extractValues(payload: unknown): Array<{ key: string; value: string }> {
    if (payload === null || typeof payload !== 'object') {
      return []
    }
    const values = (payload as Record<string, unknown>).values
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

  async function loadCard(item: MetricCatalogItem): Promise<ContactCard> {
    try {
      const doc = await getMetricDocument(runId, item.metric_set_id, item.metric_family)
      let values: Array<{ key: string; value: string }> = []
      try {
        values = extractValues(JSON.parse(atob(doc.payload_b64)) as unknown)
      } catch {
        values = []
      }
      return { family: item.metric_family, availability: doc.availability, values }
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
      const items = CONTACT_FAMILIES.flatMap((family) =>
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
      <h2>Cultural contact</h2>
      <p class="lede">
        Analytical contact exposure, convergence or continued divergence, hybrid
        practices, and transfer. These results never enter agent cognition, memory,
        or observations.
      </p>
    </div>
    <EpistemicBadge epistemic="research_inference" />
  </header>

  {#if loading}
    <p class="muted">Loading contact metrics…</p>
  {:else if error !== null}
    <p class="muted">Contact metrics unavailable: {error}</p>
  {:else if cards.length === 0}
    <p class="muted">No contact families in this run (catalog: {availability}).</p>
  {:else}
    <div class="cards">
      {#each cards as card (card.family)}
        <article class="card">
          <div class="card-head">
            <h3>{card.family}</h3>
            <span class="availability">{card.availability}</span>
          </div>
          {#if card.reason !== undefined}
            <p class="muted">Reason: {card.reason}</p>
          {:else if card.values.length === 0}
            <p class="muted">No values.</p>
          {:else}
            <dl>
              {#each card.values as row (row.key)}
                <div>
                  <dt>{row.key}</dt>
                  <dd>{row.value}</dd>
                </div>
              {/each}
            </dl>
          {/if}
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
  header {
    display: flex;
    justify-content: space-between;
    gap: 1rem;
    align-items: start;
  }
  .cards {
    display: grid;
    gap: 1rem;
    grid-template-columns: repeat(auto-fit, minmax(16rem, 1fr));
  }
  .card {
    border: 1px solid var(--border, #334155);
    border-radius: 0.5rem;
    padding: 1rem;
  }
  .card-head {
    display: flex;
    justify-content: space-between;
    gap: 0.5rem;
  }
  dl div {
    display: flex;
    justify-content: space-between;
    gap: 1rem;
  }
  .muted {
    opacity: 0.7;
  }
</style>
