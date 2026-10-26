<script lang="ts">
  import { onMount, untrack } from 'svelte'
  import { ApiClientError } from '../api/client'
  import {
    getCivilizationCatalogue,
    getCivilizationMap,
    getCivilizationOverlays,
  } from '../api/research'
  import AvailabilityNotice from '../components/research/AvailabilityNotice.svelte'
  import ResearchTable from '../components/research/ResearchTable.svelte'
  import LineagePanel from './LineagePanel.svelte'
  import type { ResearchSelection } from '../research/selection'

  interface Props {
    runId: string
    selection: ResearchSelection
    onSelectionChange: (
      patch: Partial<ResearchSelection>,
      historyMode?: 'push' | 'replace',
    ) => void
  }

  let { runId, selection, onSelectionChange }: Props = $props()

  let mode = $state<'lineage' | 'diffusion'>('lineage')
  let evidence = $state<'ANALYTICAL' | 'SUBJECTIVE' | 'OBJECTIVE'>('ANALYTICAL')
  let ownerId = $state<string | null>(null)
  let boundaries = $state<number[]>([])
  let tick = $state<number | null>(untrack(() => selection.tick))

  $effect(() => {
    tick = selection.tick
  })
  let publication = $state<Record<string, unknown> | null>(null)
  let rows = $state<Array<Record<string, unknown>>>([])
  let locationLabels = $state<Record<string, string>>({})
  let status = $state<'loading' | 'available' | 'empty' | 'unavailable' | 'forbidden' | 'error'>('loading')
  let reason = $state<string | null>(null)
  let error = $state<string | null>(null)

  const scopeOwner = $derived(
    evidence === 'OBJECTIVE' ? null : (ownerId ?? selection.scopeOwnerId),
  )

  onMount(() => {
    if (mode === 'diffusion') {
      void loadDiffusion()
    }
  })

  $effect(() => {
    if (runId !== '' && mode === 'diffusion') {
      void loadDiffusion()
    }
  })

  async function loadDiffusion(): Promise<void> {
    status = 'loading'
    reason = null
    error = null
    try {
      const catalogue = await getCivilizationCatalogue(runId, {
        evidenceClass: evidence,
        ownerId: scopeOwner,
        layer: 'technology',
        limit: 200,
      })
      publication =
        catalogue.publication !== null && typeof catalogue.publication === 'object'
          ? (catalogue.publication as Record<string, unknown>)
          : null
      const boundaryRows = Array.isArray(catalogue.boundaries)
        ? catalogue.boundaries
        : []
      boundaries = boundaryRows
        .map((row) =>
          row !== null && typeof row === 'object'
            ? Number((row as Record<string, unknown>).boundary_tick)
            : Number.NaN,
        )
        .filter((value) => Number.isSafeInteger(value) && value >= 0)
        .sort((left, right) => left - right)
      const target = tick ?? boundaries.at(-1) ?? selection.tick ?? 0
      tick = target
      const publicationId =
        publication !== null && typeof publication.publication_id === 'string'
          ? publication.publication_id
          : null
      const overlay = await getCivilizationOverlays(runId, {
        tick: target,
        layer: 'technology',
        evidenceClass: evidence,
        ownerId: scopeOwner,
        publicationId,
        limit: 200,
      })
      if (overlay.availability === 'unavailable') {
        status = 'unavailable'
        reason = overlay.reason ?? null
        return
      }
      const overlayRows = Array.isArray(overlay.rows)
        ? overlay.rows.filter(
            (row): row is Record<string, unknown> =>
              row !== null && typeof row === 'object',
          )
        : []
      rows = overlayRows
      // Objective backdrop at the exact overlay boundary; no prefix/latest substitution.
      try {
        const map = await getCivilizationMap(runId, {
          section: 'locations',
          tick: target,
          limit: 200,
        })
        const mapRows = Array.isArray(map.rows) ? map.rows : []
        const labels: Record<string, string> = {}
        for (const row of mapRows) {
          if (row === null || typeof row !== 'object') {
            continue
          }
          const record = row as Record<string, unknown>
          const locationId =
            typeof record.location_id === 'string'
              ? record.location_id
              : typeof record.entity_id === 'string'
                ? record.entity_id
                : null
          if (locationId !== null) {
            labels[locationId] =
              typeof record.label === 'string' ? record.label : locationId
          }
        }
        locationLabels = labels
      } catch {
        locationLabels = {}
      }
      status = rows.length === 0 ? 'empty' : 'available'
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

  function anchors(item: Record<string, unknown>): Array<Record<string, unknown>> {
    const context =
      item.context !== null && typeof item.context === 'object'
        ? (item.context as Record<string, unknown>)
        : null
    const raw = context?.anchors
    return Array.isArray(raw)
      ? raw.filter(
          (anchor): anchor is Record<string, unknown> =>
            anchor !== null && typeof anchor === 'object',
        )
      : []
  }

  function grounding(item: Record<string, unknown>): string {
    const found = anchors(item)
    if (found.length === 0) {
      return 'Unlocated: no published anchor at this boundary'
    }
    return found
      .map((anchor) => {
        const location =
          typeof anchor.location_id === 'string'
            ? (locationLabels[anchor.location_id] ?? anchor.location_id)
            : typeof anchor.entity_id === 'string'
              ? anchor.entity_id
              : 'none'
        const evidenceTick =
          typeof anchor.evidence_tick === 'number'
            ? `evidence tick ${anchor.evidence_tick}`
            : 'evidence tick unknown'
        return `${String(anchor.kind)} · ${location} · ${evidenceTick}`
      })
      .join('; ')
  }

  function topology(): Array<{ location: string; count: number }> {
    const counts = new Map<string, number>()
    for (const row of rows) {
      for (const anchor of anchors(row)) {
        const id =
          typeof anchor.location_id === 'string'
            ? anchor.location_id
            : typeof anchor.entity_id === 'string'
              ? anchor.entity_id
              : null
        if (id !== null) {
          counts.set(id, (counts.get(id) ?? 0) + 1)
        }
      }
    }
    return [...counts.entries()]
      .map(([id, count]) => ({ location: locationLabels[id] ?? id, count }))
      .sort((left, right) => right.count - left.count)
  }

  const topologyRows = $derived(topology())
  const maxCount = $derived(
    Math.max(1, ...topologyRows.map((item) => item.count)),
  )
</script>

<section class="page">
  <header>
    <p class="eyebrow">Technology</p>
    <h1>Technology lineage and diffusion</h1>
    <p class="lede">
      Subjective practical knowledge, analytical transmission and objective place
      remain distinct. A content key is not an owner-local knowledge entry ID.
    </p>
  </header>

  <div class="controls" role="tablist" aria-label="Technology modes">
    <button
      type="button"
      role="tab"
      aria-selected={mode === 'lineage'}
      class:active={mode === 'lineage'}
      onclick={() => (mode = 'lineage')}
    >
      Lineage
    </button>
    <button
      type="button"
      role="tab"
      aria-selected={mode === 'diffusion'}
      class:active={mode === 'diffusion'}
      onclick={() => {
        mode = 'diffusion'
        void loadDiffusion()
      }}
    >
      Diffusion
    </button>
  </div>

  {#if mode === 'lineage'}
    <LineagePanel
      {runId}
      {selection}
      {onSelectionChange}
      initialFamily="technology"
    />
  {:else}
    <div class="controls">
      <label>
        Evidence
        <select
          value={evidence}
          onchange={(event) => {
            evidence = event.currentTarget.value as typeof evidence
            void loadDiffusion()
          }}
        >
          <option value="ANALYTICAL">analytical</option>
          <option value="SUBJECTIVE">subjective (owner scoped)</option>
          <option value="OBJECTIVE">objective</option>
        </select>
      </label>
      {#if evidence !== 'OBJECTIVE'}
        <label>
          Scope owner
          <input
            value={ownerId ?? ''}
            onchange={(event) => {
              ownerId = event.currentTarget.value.trim() || null
              void loadDiffusion()
            }}
          />
        </label>
      {/if}
      <label>
        Captured boundary
        <select
          value={tick ?? ''}
          onchange={(event) => {
            tick = Number.parseInt(event.currentTarget.value, 10)
            void loadDiffusion()
          }}
        >
          {#each boundaries as boundary (boundary)}
            <option value={boundary}>tick {boundary}</option>
          {/each}
        </select>
      </label>
      <button type="button" onclick={() => void loadDiffusion()}>
        Reload diffusion
      </button>
    </div>

    <AvailabilityNotice
      status={status}
      reason={reason}
      requestedTick={tick}
      resolvedTick={tick}
    />
    {#if error !== null}
      <p class="error" role="alert">{error}</p>
    {/if}
    {#if publication !== null}
      <p class="muted">
        Pinned publication {String(publication.publication_id ?? '—')} · policy
        {String(publication.policy_version ?? '—')}
      </p>
    {/if}

    {#if topologyRows.length > 0}
      <figure>
        <figcaption>
          Anchor topology at the exact boundary. Positions are deterministic
          presentation slots, not claimed geography.
        </figcaption>
        <svg viewBox="0 0 640 {Math.max(80, topologyRows.length * 26)}" role="img" aria-label="Technology anchor topology">
          {#each topologyRows as item, index (item.location)}
            <rect
              x="120"
              y={10 + index * 26}
              width={(item.count / maxCount) * 420}
              height="16"
              class="bar"
            />
            <text x="112" y={23 + index * 26} text-anchor="end">{item.location}</text>
            <text x={130 + (item.count / maxCount) * 420} y={23 + index * 26}>
              {item.count}
            </text>
          {/each}
        </svg>
      </figure>
    {/if}

    <ResearchTable
      caption="Technology diffusion rows"
      columns={[
        { key: 'knowledge', label: 'Content key' },
        { key: 'holder', label: 'Holder' },
        { key: 'status', label: 'Status' },
        { key: 'attribution', label: 'Attribution' },
        { key: 'modality', label: 'Modality' },
        { key: 'source', label: 'Source owner / entry' },
        { key: 'denominator', label: 'Living / eligible' },
        { key: 'grounding', label: 'Grounding' },
      ]}
      rows={rows.map((row) => ({
        knowledge: String(row.knowledge_id ?? '—'),
        holder: String(row.holder_id ?? '—'),
        status: String(row.status ?? '—'),
        attribution: String(row.attribution ?? '—'),
        modality: String(row.modality ?? '—'),
        source: `${String(row.source_owner_id ?? '—')} / ${String(row.source_knowledge_id ?? '—')}`,
        denominator: `${String(row.living_holder_count ?? '—')} / ${String(row.eligible_owner_count ?? '—')}`,
        grounding: grounding(row),
      }))}
      rowKey={(row) => `${row.knowledge}:${row.holder}:${row.grounding}`}
    />
  {/if}
</section>

<style>
  .page {
    display: grid;
    gap: 0.9rem;
  }

  .eyebrow {
    margin: 0 0 0.2rem;
    font-size: 0.75rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #5a6a72;
  }

  h1 {
    margin: 0 0 0.3rem;
    font-size: 1.35rem;
  }

  .lede {
    margin: 0;
    color: #3a474e;
  }

  .controls {
    display: flex;
    flex-wrap: wrap;
    gap: 0.6rem;
    align-items: end;
  }

  label {
    display: grid;
    gap: 0.2rem;
    font-size: 0.8rem;
    color: #5a6a72;
  }

  select,
  input,
  button {
    font: inherit;
    padding: 0.25rem 0.45rem;
  }

  button.active {
    border-color: #2e5c6e;
    color: #2e5c6e;
    font-weight: 600;
  }

  figure {
    margin: 0;
    display: grid;
    gap: 0.3rem;
  }

  figcaption {
    font-size: 0.8rem;
    color: #5a6a72;
  }

  svg {
    width: 100%;
    height: auto;
    background: rgba(255, 255, 255, 0.35);
  }

  .bar {
    fill: #2e5c6e;
  }

  text {
    font-size: 0.7rem;
    fill: #1c2428;
  }

  .muted {
    color: #5a6a72;
    font-size: 0.85rem;
  }

  .error {
    color: #8a3030;
  }
</style>
