<script lang="ts">
  import { untrack } from 'svelte'
  import { ApiClientError } from '../api/client'
  import {
    getCivilizationCatalogue,
    getCivilizationMap,
    getCivilizationOverlays,
  } from '../api/research'
  import AvailabilityNotice from '../components/research/AvailabilityNotice.svelte'
  import ResearchTable from '../components/research/ResearchTable.svelte'
  import TopologyMap from '../components/research/TopologyMap.svelte'
  import {
    groundAnchors,
    migrationRows,
    topologyFromMap,
    type MigrationRow,
  } from '../research/spatial'
  import type { ResearchSelection } from '../research/selection'

  interface Props {
    runId: string
    selection: ResearchSelection
  }

  let { runId, selection }: Props = $props()

  let tick = $state<number | null>(untrack(() => selection.tick))

  $effect(() => {
    tick = selection.tick
  })
  let boundaries = $state<number[]>([])
  let rows = $state<MigrationRow[]>([])
  let topology = $state<{ nodes: ReturnType<typeof topologyFromMap>['nodes']; edges: ReturnType<typeof topologyFromMap>['edges'] }>({ nodes: [], edges: [] })
  let located = $state<Array<{ rowId: string; locationId: string | null; historical: boolean; evidenceTick: number | null; reason: string | null }>>([])
  let unlocated = $state<Array<{ rowId: string; locationId: string | null; historical: boolean; evidenceTick: number | null; reason: string | null }>>([])
  let routeFilter = $state('')
  let phaseFilter = $state('')
  let status = $state<'loading' | 'available' | 'empty' | 'unavailable' | 'forbidden' | 'error'>('loading')
  let reason = $state<string | null>(null)
  let publication = $state<Record<string, unknown> | null>(null)

  async function load(): Promise<void> {
    status = 'loading'
    reason = null
    try {
      const catalogue = await getCivilizationCatalogue(runId, {
        evidenceClass: 'ANALYTICAL',
        layer: 'migration',
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
      const [overlay, locations, regions, routes] = await Promise.all([
        getCivilizationOverlays(runId, {
          tick: target,
          layer: 'migration',
          evidenceClass: 'ANALYTICAL',
          limit: 200,
        }),
        getCivilizationMap(runId, { section: 'locations', tick: target, limit: 200 }),
        getCivilizationMap(runId, { section: 'regions', tick: target, limit: 200 }),
        getCivilizationMap(runId, { section: 'routes', tick: target, limit: 200 }),
      ])
      if (overlay.availability === 'unavailable') {
        status = 'unavailable'
        reason = overlay.reason ?? null
        rows = []
        return
      }
      const overlayRows = Array.isArray(overlay.rows)
        ? overlay.rows.filter(
            (row): row is Record<string, unknown> =>
              row !== null && typeof row === 'object',
          )
        : []
      rows = migrationRows(overlayRows)
      topology = topologyFromMap({
        locations: Array.isArray(locations.rows) ? locations.rows : [],
        regions: Array.isArray(regions.rows) ? regions.rows : [],
        routes: Array.isArray(routes.rows) ? routes.rows : [],
      })
      const known = new Set(
        topology.nodes
          .filter((node) => node.kind === 'location')
          .map((node) => node.id),
      )
      const grounded = groundAnchors(overlayRows, known, target)
      located = grounded.located
      unlocated = grounded.unlocated
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

  const filtered = $derived(
    rows.filter(
      (row) =>
        (routeFilter === '' || row.routeId === routeFilter) &&
        (phaseFilter === '' || row.phase === phaseFilter),
    ),
  )

  const routeOptions = $derived(
    [...new Set(rows.map((row) => row.routeId))].sort(),
  )
  const phaseOptions = $derived(
    [...new Set(rows.map((row) => row.phase))].sort(),
  )

  function focus(id: string): void {
    if (id === '') return
    // Location/route selection is presentation-only; no simulation command.
    if (import.meta.env.DEV) {
      console.debug(`research_ui_migration_focus kind=map`)
    }
  }
</script>

<section class="page">
  <header>
    <p class="eyebrow">Migration</p>
    <h1>Migration flows</h1>
    <p class="lede">
      Captured movement and co-presence. Journeys are not citizenship, borders or
      polity membership.
    </p>
  </header>

  <div class="controls">
    <label>
      Captured boundary
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
    <label>
      Route
      <select bind:value={routeFilter}>
        <option value="">all routes</option>
        {#each routeOptions as route (route)}
          <option value={route}>{route}</option>
        {/each}
      </select>
    </label>
    <label>
      Phase
      <select bind:value={phaseFilter}>
        <option value="">all phases</option>
        {#each phaseOptions as phase (phase)}
          <option value={phase}>{phase}</option>
        {/each}
      </select>
    </label>
    <button type="button" onclick={() => void load()}>Load migration window</button>
  </div>

  <AvailabilityNotice status={status} reason={reason} requestedTick={selection.tick} resolvedTick={tick} />
  {#if publication !== null}
    <p class="muted">Pinned publication {String(publication.publication_id ?? '—')}</p>
  {/if}

  <TopologyMap
    title="Routes, regions and locations (deterministic presentation slots)"
    nodes={topology.nodes}
    edges={topology.edges}
    onNodeSelect={focus}
    emptyMessage="No objective regional layout rows at this boundary."
  />

  <ResearchTable
    caption="Migration journeys"
    columns={[
      { key: 'journey', label: 'Journey' },
      { key: 'route', label: 'Route' },
      { key: 'origin', label: 'Origin' },
      { key: 'destination', label: 'Destination' },
      { key: 'phase', label: 'Phase' },
      { key: 'participants', label: 'Participants', numeric: true },
      { key: 'started', label: 'Started', numeric: true },
      { key: 'arrived', label: 'Arrived', numeric: true },
      { key: 'ended', label: 'Ended', numeric: true },
      { key: 'window', label: 'Window' },
    ]}
    rows={filtered.map((row) => ({
      journey: row.journeyId,
      route: row.routeId,
      origin: row.origin,
      destination: row.destination,
      phase: row.phase,
      participants: row.participantCount,
      started: row.startedTick,
      arrived: row.arrivedTick,
      ended: row.endedTick,
      window: `${row.window.start ?? '—'}…${row.window.end ?? '—'}`,
    }))}
    rowKey={(row) => `${row.journey}:${row.window}`}
    emptyLabel="No journey rows in the selected filters."
  />

  {#if located.length > 0 || unlocated.length > 0}
    <section>
      <h2>Grounding</h2>
      <ul class="grounding">
        {#each located as item (item.rowId + String(item.evidenceTick))}
          <li>
            {item.rowId} → {item.locationId}
            {#if item.historical}
              <strong>historical anchor at evidence tick {item.evidenceTick}</strong>
            {:else}
              evidence tick {item.evidenceTick ?? '—'}
            {/if}
          </li>
        {/each}
        {#each unlocated as item (item.rowId + String(item.reason))}
          <li>Unlocated {item.rowId}: {item.reason}</li>
        {/each}
      </ul>
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
  .grounding { margin: 0; padding-left: 1rem; font-size: 0.85rem; }
</style>
