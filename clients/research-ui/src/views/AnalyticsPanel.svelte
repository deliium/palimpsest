<script lang="ts">
  import {
    ApiClientError,
    getCulturalNarratives,
    getGroupFormation,
    getMetricCatalog,
    getMetricDocument,
    getSocialConventions,
    getSocialNorms,
    type LedgerProjection,
    type MetricCatalogItem,
  } from '../api/client'
  import EpistemicBadge from '../components/EpistemicBadge.svelte'

  interface Props {
    runId: string
    agentId: string | null
  }

  let { runId, agentId }: Props = $props()

  const PRIORITY_FAMILIES = [
    'emergent_group_formation',
    'spatial_control',
    'territorial_concentration',
    'emergent_social_norms',
    'persistent_social_conventions',
    'cultural_narrative_lineage',
    'historical_memory_layers',
    'historical_memory_transitions',
    'historical_memory_queries',
    'durable_record_lineage',
    'durable_record_fidelity',
    'durable_record_survival',
  ] as const

  const HISTORICAL_MEMORY_FAMILIES = new Set([
    'historical_memory_layers',
    'historical_memory_transitions',
    'historical_memory_queries',
  ])

  const DURABLE_RECORD_FAMILIES = new Set([
    'durable_record_lineage',
    'durable_record_fidelity',
    'durable_record_survival',
  ])

  type MetricCard = {
    family: string
    setId: string
    availability: string
    supportBands: string[]
    scalars: Array<{ key: string; value: string }>
    reason?: string
  }

  let catalogItems = $state<MetricCatalogItem[]>([])
  let catalogAvailability = $state<string>('unavailable')
  let cards = $state<MetricCard[]>([])
  let ledgers = $state<Array<{ name: string; doc: LedgerProjection | null; reason?: string }>>(
    [],
  )
  let error = $state<string | null>(null)
  let loading = $state(true)

  function extractSupportBands(payload: unknown): string[] {
    const bands = new Set<string>()
    const visit = (value: unknown): void => {
      if (value === null || value === undefined) {
        return
      }
      if (Array.isArray(value)) {
        for (const item of value) {
          visit(item)
        }
        return
      }
      if (typeof value !== 'object') {
        return
      }
      const record = value as Record<string, unknown>
      const band = record.support_band
      if (typeof band === 'string' && band !== '') {
        bands.add(band)
      }
      for (const nested of Object.values(record)) {
        if (typeof nested === 'object' && nested !== null) {
          visit(nested)
        }
      }
    }
    visit(payload)
    return [...bands]
  }

  function extractScalars(payload: unknown): Array<{ key: string; value: string }> {
    if (payload === null || typeof payload !== 'object') {
      return []
    }
    const record = payload as Record<string, unknown>
    const values = record.values
    if (values === null || typeof values !== 'object' || Array.isArray(values)) {
      return []
    }
    const out: Array<{ key: string; value: string }> = []
    const preferredKeys = [
      'living_count',
      'communicative_count',
      'cultural_count',
      'unattested_count',
      'source_count',
      'transition_count',
      'living_to_communicative_count',
      'communicative_to_cultural_count',
      'true_count_any_direct_witnesses_alive',
      'true_count_anyone_remembers_speaking_to_witness',
      'true_count_event_known_only_from_stories_or_artifacts',
    ]
    const entries = Object.entries(values as Record<string, unknown>)
    for (const key of preferredKeys) {
      const raw = (values as Record<string, unknown>)[key]
      if (typeof raw === 'number' || typeof raw === 'string') {
        out.push({ key, value: String(raw) })
      }
      if (out.length >= 8) {
        return out
      }
    }
    for (const [key, raw] of entries) {
      if (out.some((item) => item.key === key)) {
        continue
      }
      const lowered = key.toLowerCase()
      if (
        lowered.includes('emerged') ||
        lowered === 'detected' ||
        lowered === 'society_formed' ||
        lowered === 'layer' ||
        lowered === 'censoring_policy'
      ) {
        continue
      }
      if (typeof raw === 'number' || typeof raw === 'string') {
        out.push({ key, value: String(raw) })
      }
      if (out.length >= 8) {
        break
      }
    }
    return out
  }

  async function loadMetricCard(item: MetricCatalogItem): Promise<MetricCard> {
    try {
      const doc = await getMetricDocument(
        runId,
        item.metric_set_id,
        item.metric_family,
      )
      let supportBands: string[] = []
      let scalars: Array<{ key: string; value: string }> = []
      try {
        const json = JSON.parse(atob(doc.payload_b64)) as unknown
        supportBands = extractSupportBands(json)
        scalars = extractScalars(json)
      } catch {
        // metadata-only fallback
      }
      if (import.meta.env.DEV) {
        console.debug(
          `research_ui_metric_fetch family=${item.metric_family} status=${doc.availability}`,
        )
      }
      return {
        family: item.metric_family,
        setId: item.metric_set_id,
        availability: doc.availability,
        supportBands,
        scalars,
      }
    } catch (err) {
      const reason = err instanceof ApiClientError ? err.code : 'fetch_failed'
      if (import.meta.env.DEV) {
        console.debug(
          `research_ui_metric_fetch family=${item.metric_family} status=error reason=${reason}`,
        )
      }
      return {
        family: item.metric_family,
        setId: item.metric_set_id,
        availability: 'unavailable',
        supportBands: [],
        scalars: [],
        reason,
      }
    }
  }

  async function load(): Promise<void> {
    loading = true
    error = null
    try {
      const catalog = await getMetricCatalog(runId)
      catalogItems = catalog.items
      catalogAvailability = catalog.availability
      const preferred = PRIORITY_FAMILIES.flatMap((family) =>
        catalog.items.filter((item) => item.metric_family === family),
      )
      const historical = catalog.items.filter((item) =>
        HISTORICAL_MEMORY_FAMILIES.has(item.metric_family),
      )
      const durable = catalog.items.filter((item) =>
        DURABLE_RECORD_FAMILIES.has(item.metric_family),
      )
      const phenomenon = catalog.items.filter((item) =>
        item.metric_family.includes('phenomenon'),
      )
      const selected = [...preferred, ...historical, ...durable, ...phenomenon]
        .filter(
          (item, index, all) =>
            all.findIndex(
              (other) =>
                other.metric_family === item.metric_family &&
                other.metric_set_id === item.metric_set_id,
            ) === index,
        )
        .slice(0, 14)
      cards = await Promise.all(selected.map((item) => loadMetricCard(item)))

      if (agentId) {
        const names = [
          ['group_formation', getGroupFormation],
          ['social_norms', getSocialNorms],
          ['social_conventions', getSocialConventions],
          ['cultural_narratives', getCulturalNarratives],
        ] as const
        const loaded = await Promise.all(
          names.map(async ([name, fetchDoc]) => {
            try {
              return { name, doc: await fetchDoc(runId, agentId) }
            } catch (err) {
              return {
                name,
                doc: null,
                reason: err instanceof ApiClientError ? err.code : 'fetch_failed',
              }
            }
          }),
        )
        ledgers = loaded
      } else {
        ledgers = []
      }
    } catch (err) {
      error = err instanceof ApiClientError ? err.code : 'fetch_failed'
      catalogItems = []
      cards = []
      ledgers = []
    } finally {
      loading = false
    }
  }

  $effect(() => {
    void agentId
    void runId
    void load()
  })
</script>

<section class="panel">
  <header class="head">
    <h2>Analytics</h2>
    <EpistemicBadge epistemic="research_inference" />
  </header>
  <p class="lede">
    Metric documents and phenomenon panels are analytical results — never world facts.
    Historical memory and durable-record lineage / fidelity / survival families are
    researcher constructs (<code>research_inference</code>), not agent knowledge.
  </p>

  {#if loading}
    <p>Loading…</p>
  {:else if error !== null}
    <p class="error" role="alert">{error}</p>
  {:else}
    <section class="stats">
      <h3>Per-run statistics</h3>
      <dl>
        <div><dt>Catalog availability</dt><dd>{catalogAvailability}</dd></div>
        <div><dt>Document count</dt><dd>{catalogItems.length}</dd></div>
        <div>
          <dt>Priority families present</dt>
          <dd>
            {
              PRIORITY_FAMILIES.filter((family) =>
                catalogItems.some((item) => item.metric_family === family),
              ).length
            }/{PRIORITY_FAMILIES.length}
          </dd>
        </div>
      </dl>
    </section>

    <section class="metrics">
      <h3>Metric families</h3>
      {#if cards.length === 0}
        <p class="empty">No priority metric documents on this run.</p>
      {:else}
        <ul>
          {#each cards as card (card.setId + card.family)}
            <li>
              <div class="card-head">
                <strong>{card.family}</strong>
                <EpistemicBadge epistemic="research_inference" />
              </div>
              <p class="meta">
                set={card.setId} · {card.availability}
                {#if card.reason}
                  · {card.reason}
                {/if}
              </p>
              {#if card.supportBands.length > 0}
                <p class="bands">
                  support_band: {card.supportBands.join(', ')}
                </p>
              {:else}
                <p class="bands">support_band: (none in payload)</p>
              {/if}
              {#if card.scalars.length > 0}
                <ul class="scalars">
                  {#each card.scalars as scalar (scalar.key)}
                    <li>{scalar.key}: {scalar.value}</li>
                  {/each}
                </ul>
              {/if}
            </li>
          {/each}
        </ul>
      {/if}
    </section>

    <section class="ledgers">
      <header class="card-head">
        <h3>Owner ledger summaries</h3>
        <EpistemicBadge epistemic="agent_belief" />
      </header>
      {#if !agentId}
        <p class="empty">Select an agent_id deep link to load subjective ledgers.</p>
      {:else if ledgers.length === 0}
        <p class="empty">No ledger projections loaded.</p>
      {:else}
        <ul>
          {#each ledgers as entry (entry.name)}
            <li>
              <strong>{entry.name}</strong>
              {#if entry.doc}
                — {entry.doc.availability}, heads={entry.doc.head_count}
              {:else}
                — unavailable{#if entry.reason} ({entry.reason}){/if}
              {/if}
            </li>
          {/each}
        </ul>
      {/if}
    </section>
  {/if}
</section>

<style>
  .panel {
    display: grid;
    gap: 1rem;
  }

  .head,
  .card-head {
    display: flex;
    gap: 0.75rem;
    align-items: center;
    flex-wrap: wrap;
  }

  h2,
  h3 {
    margin: 0;
    font-family: "Iowan Old Style", "Palatino Linotype", Palatino, Georgia, serif;
  }

  .lede,
  .empty,
  .meta,
  .bands {
    margin: 0;
    color: #5a6a72;
    font-size: 0.9rem;
  }

  .error {
    color: #8a3030;
  }

  .stats dl {
    display: grid;
    gap: 0.35rem;
    margin: 0.5rem 0 0;
  }

  .stats div {
    display: flex;
    gap: 0.75rem;
  }

  dt {
    min-width: 11rem;
    color: #5a6a72;
  }

  dd {
    margin: 0;
  }

  .metrics ul,
  .ledgers ul,
  .scalars {
    list-style: none;
    margin: 0.5rem 0 0;
    padding: 0;
    display: grid;
    gap: 0.75rem;
  }

  .metrics li,
  .ledgers li {
    padding: 0.65rem 0;
    border-top: 1px solid rgba(28, 36, 40, 0.12);
  }

  .scalars {
    gap: 0.2rem;
    font-size: 0.85rem;
  }
</style>
