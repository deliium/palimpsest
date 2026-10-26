<script lang="ts">
  import { untrack } from 'svelte'
  import { ApiClientError, getMetricCatalog, getMetricDocument } from '../api/client'
  import {
    getCivilizationCatalogue,
    getCivilizationOverlays,
  } from '../api/research'
  import AvailabilityNotice from '../components/research/AvailabilityNotice.svelte'
  import ResearchTable from '../components/research/ResearchTable.svelte'
  import TopologyMap from '../components/research/TopologyMap.svelte'
  import { itemSummary, tradeNetwork, tradeRows, type TradeRow } from '../research/economy'
  import { decodeMetricPayloadBase64 } from '../api/research'
  import type { ResearchSelection } from '../research/selection'

  interface Props {
    runId: string
    selection: ResearchSelection
  }

  let { runId, selection }: Props = $props()

  const ECONOMY_FAMILIES = [
    'structured_commitment_fulfillment',
    'resource_exchange_profile',
    'exchange_functions',
  ]
  let tick = $state<number | null>(untrack(() => selection.tick))

  $effect(() => {
    tick = selection.tick
  })
  let boundaries = $state<number[]>([])
  let rows = $state<TradeRow[]>([])
  let network = $state(tradeNetwork([]))
  let status = $state<'loading' | 'available' | 'empty' | 'unavailable' | 'forbidden' | 'error'>('loading')
  let reason = $state<string | null>(null)
  let publication = $state<Record<string, unknown> | null>(null)
  let metricCards = $state<Array<{ family: string; availability: string; values: string }>>([])

  async function load(): Promise<void> {
    status = 'loading'
    reason = null
    try {
      const catalogue = await getCivilizationCatalogue(runId, {
        evidenceClass: 'ANALYTICAL',
        layer: 'trade',
        limit: 200,
      })
      publication =
        catalogue.publication !== null && typeof catalogue.publication === 'object'
          ? (catalogue.publication as Record<string, unknown>)
          : null
      boundaries = (Array.isArray(catalogue.boundaries) ? catalogue.boundaries : [])
        .map((row) =>
          row !== null && typeof row === 'object'
            ? Number((row as Record<string, unknown>).boundary_tick)
            : Number.NaN,
        )
        .filter((value) => Number.isSafeInteger(value) && value >= 0)
        .sort((left, right) => left - right)
      const target = tick ?? boundaries.at(-1) ?? 0
      tick = target
      const overlay = await getCivilizationOverlays(runId, {
        tick: target,
        layer: 'trade',
        evidenceClass: 'ANALYTICAL',
        limit: 200,
      })
      if (overlay.availability === 'unavailable') {
        status = 'unavailable'
        reason = overlay.reason ?? null
        rows = []
        network = tradeNetwork([])
        return
      }
      const overlayRows = Array.isArray(overlay.rows)
        ? overlay.rows.filter(
            (row): row is Record<string, unknown> =>
              row !== null && typeof row === 'object',
          )
        : []
      rows = tradeRows(overlayRows)
      network = tradeNetwork(rows)
      status = rows.length === 0 ? 'empty' : 'available'
      await loadMetrics()
    } catch (err) {
      if (err instanceof ApiClientError) {
        status = err.status === 403 ? 'forbidden' : 'error'
        reason = err.code
      } else {
        status = 'error'
        reason = 'fetch_failed'
      }
    }
  }

  async function loadMetrics(): Promise<void> {
    try {
      const catalog = await getMetricCatalog(runId)
      const cards: typeof metricCards = []
      for (const item of catalog.items.filter((entry) =>
        ECONOMY_FAMILIES.some((prefix) => entry.metric_family.startsWith(prefix)),
      )) {
        try {
          const document = await getMetricDocument(
            runId,
            item.metric_set_id,
            item.metric_family,
          )
          const payload = decodeMetricPayloadBase64(document.payload_b64) as
            | Record<string, unknown>
            | null
          const values =
            payload !== null && typeof payload === 'object'
              ? Object.entries(payload.values ?? {})
                  .filter(([, value]) => typeof value === 'number')
                  .map(([key, value]) => `${key}=${String(value)}`)
                  .join(', ')
              : ''
          cards.push({
            family: item.metric_family,
            availability: document.availability,
            values: values || 'no scalar values',
          })
        } catch {
          cards.push({
            family: item.metric_family,
            availability: 'unavailable',
            values: 'metric unavailable',
          })
        }
      }
      metricCards = cards
    } catch {
      metricCards = []
    }
  }

  function focusNode(id: string): void {
    if (id.startsWith('exchange:')) return
    if (import.meta.env.DEV) {
      console.debug('research_ui_economy_focus kind=agent')
    }
  }
</script>

<section class="page">
  <header>
    <p class="eyebrow">Economy</p>
    <h1>Economic exchange networks</h1>
    <p class="lede">
      Completed analytical exchanges only. No price, currency, account balance,
      debt obligation or wealth measure is synthesized.
    </p>
  </header>

  <div class="controls">
    <label>
      Captured window
      <select
        value={tick ?? ''}
        onchange={(event) => {
          tick = Number.parseInt(event.currentTarget.value, 10)
          void load()
        }}
      >
        {#each boundaries as boundary (boundary)}
          <option value={boundary}>tick {boundary}</option>
        {/each}
      </select>
    </label>
    <button type="button" onclick={() => void load()}>Load exchange window</button>
  </div>

  <AvailabilityNotice status={status} reason={reason} requestedTick={selection.tick} resolvedTick={tick} />
  {#if publication !== null}
    <p class="muted">Pinned publication {String(publication.publication_id ?? '—')}</p>
  {/if}

  <TopologyMap
    title="Completed exchange hub network"
    nodes={network.nodes.map((node) => ({
      id: node.id,
      label: node.label,
      kind: node.kind === 'hub' ? 'hub' : 'agent',
      meta: node.meta ?? {},
    }))}
    edges={network.edges}
    onNodeSelect={focusNode}
    emptyMessage="No completed exchanges in this window; not proof of absent economic activity."
  />

  <ResearchTable
    caption="Completed exchange rows"
    columns={[
      { key: 'row', label: 'Row identity' },
      { key: 'participants', label: 'Participants' },
      { key: 'count', label: 'Completed', numeric: true },
      { key: 'forward', label: 'Forward items' },
      { key: 'reverse', label: 'Reverse items' },
      { key: 'location', label: 'Location' },
      { key: 'window', label: 'Window' },
    ]}
    rows={rows.map((row) => ({
      row: row.rowId,
      participants: row.participants.join(', '),
      count: row.completedExchanges,
      forward: itemSummary(row.forwardItems),
      reverse: itemSummary(row.reverseItems),
      location: row.locationId ?? 'unknown',
      window: `${row.window.start ?? '—'}…${row.window.end ?? '—'}`,
    }))}
    rowKey={(row) => String(row.row)}
  />

  {#if metricCards.length > 0}
    <section>
      <h2>Stored exchange and commitment summaries</h2>
      <ul>
        {#each metricCards as card (card.family)}
          <li>
            <strong>{card.family}</strong> · {card.availability} · {card.values}
          </li>
        {/each}
      </ul>
      <p class="muted">
        Private reservations and valuations are subjective claims and are not
        inferred from item counts.
      </p>
    </section>
  {/if}
</section>

<style>
  .page { display: grid; gap: 0.9rem; }
  .eyebrow { margin: 0 0 0.2rem; font-size: 0.75rem; letter-spacing: 0.08em; text-transform: uppercase; color: #5a6a72; }
  h1 { margin: 0 0 0.3rem; font-size: 1.35rem; }
  h2 { margin: 0 0 0.3rem; font-size: 1rem; }
  .lede { margin: 0; color: #3a474e; }
  .controls { display: flex; flex-wrap: wrap; gap: 0.6rem; align-items: end; }
  label { display: grid; gap: 0.2rem; font-size: 0.8rem; color: #5a6a72; }
  select, button { font: inherit; padding: 0.25rem 0.45rem; }
  .muted { color: #5a6a72; font-size: 0.85rem; }
</style>
