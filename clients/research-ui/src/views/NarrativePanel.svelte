<script lang="ts">
  import { untrack } from 'svelte'
  import { ApiClientError } from '../api/client'
  import { getNarrativeHops } from '../api/research'
  import AvailabilityNotice from '../components/research/AvailabilityNotice.svelte'
  import ResearchTable from '../components/research/ResearchTable.svelte'
  import { narrativeSummary, type NarrativeSummary } from '../research/narratives'
  import type { ResearchSelection } from '../research/selection'
  import LineagePanel from './LineagePanel.svelte'

  interface Props {
    runId: string
    selection: ResearchSelection
    onSelectionChange: (
      patch: Partial<ResearchSelection>,
      historyMode?: 'push' | 'replace',
    ) => void
  }

  let { runId, selection, onSelectionChange }: Props = $props()

  let ownerId = $state(untrack(() => selection.scopeOwnerId ?? ''))

  $effect(() => {
    ownerId = selection.scopeOwnerId ?? ''
  })
  let summary = $state<NarrativeSummary | null>(null)
  let status = $state<'loading' | 'available' | 'empty' | 'unavailable' | 'forbidden' | 'error'>('unavailable')
  let reason = $state<string | null>(null)

  async function load(): Promise<void> {
    if (ownerId.trim() === '') {
      status = 'unavailable'
      reason = 'owner_required'
      return
    }
    status = 'loading'
    try {
      const overlay = await getNarrativeHops(runId, ownerId.trim())
      summary = narrativeSummary(overlay)
      status = summary.count === 0 ? 'empty' : 'available'
      reason = null
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
</script>

<section class="page">
  <header>
    <p class="eyebrow">Narratives</p>
    <h1>Historical narrative lineage</h1>
    <p class="lede">
      Metadata-only variants, roots and transmission. No story content, truth
      label or objective record replacement is inferred.
    </p>
  </header>

  <div class="controls">
    <label>
      Owner
      <input bind:value={ownerId} placeholder="owner id" />
    </label>
    <button type="button" onclick={() => void load()}>Load current narrative metadata</button>
  </div>

  <AvailabilityNotice status={status} reason={reason} requestedTick={selection.tick} />

  {#if summary !== null}
    <div class="cards">
      <p><strong>Variants</strong> {summary.count}</p>
      <p><strong>Roots</strong> {summary.roots}</p>
      <p><strong>Branches</strong> {summary.branches}</p>
      <p><strong>Merges</strong> {summary.merges}</p>
      <p><strong>Source-linked</strong> {summary.sourceLinked}</p>
      <p><strong>Carriers</strong> {summary.carriers}</p>
    </div>
    <p class="warning" role="status">
      Current narrative projection is as-of the live checkpoint; it is not
      restored history. Objective record existence is a separate evidence class.
    </p>
    <ResearchTable
      caption="Narrative variant metadata"
      columns={[
        { key: 'variant', label: 'Variant' },
        { key: 'status', label: 'Status' },
        { key: 'origin', label: 'Origin' },
        { key: 'parents', label: 'Parents' },
        { key: 'merged', label: 'Merged into' },
        { key: 'root', label: 'Transmission root' },
        { key: 'source', label: 'Source event' },
        { key: 'carriers', label: 'Carriers', numeric: true },
      ]}
      rows={summary.variants.map((variant) => ({
        variant: String(variant.variant_id ?? '—'),
        status: String(variant.status ?? '—'),
        origin: String(variant.origin ?? '—'),
        parents: (Array.isArray(variant.parent_variant_ids)
          ? variant.parent_variant_ids
          : []
        ).join(', ') || '—',
        merged: String(variant.merged_into_id ?? '—'),
        root: String(variant.transmission_root_id ?? '—'),
        source: String(variant.source_event_id ?? '—'),
        carriers: Array.isArray(variant.carrier_agent_ids)
          ? variant.carrier_agent_ids.length
          : 0,
      }))}
      rowKey={(row) => String(row.variant)}
    />
  {/if}

  <LineagePanel
    {runId}
    {selection}
    {onSelectionChange}
    initialFamily="narrative"
  />
</section>

<style>
  .page { display: grid; gap: 0.9rem; }
  .eyebrow { margin: 0 0 0.2rem; font-size: 0.75rem; letter-spacing: 0.08em; text-transform: uppercase; color: #5a6a72; }
  h1 { margin: 0 0 0.3rem; font-size: 1.35rem; }
  .lede { margin: 0; color: #3a474e; }
  .controls { display: flex; flex-wrap: wrap; gap: 0.6rem; align-items: end; }
  label { display: grid; gap: 0.2rem; font-size: 0.8rem; color: #5a6a72; }
  input, button { font: inherit; padding: 0.25rem 0.45rem; }
  .cards { display: flex; flex-wrap: wrap; gap: 0.5rem 1.25rem; font-size: 0.85rem; }
  .cards p { margin: 0; }
  .warning { margin: 0; color: #6a5420; font-size: 0.85rem; }
</style>
