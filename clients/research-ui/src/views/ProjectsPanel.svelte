<script lang="ts">
  import { untrack } from 'svelte'
  import { ApiClientError } from '../api/client'
  import { getCivilizationMap } from '../api/research'
  import AvailabilityNotice from '../components/research/AvailabilityNotice.svelte'
  import ResearchTable from '../components/research/ResearchTable.svelte'
  import SeriesChart from '../components/research/SeriesChart.svelte'
  import {
    projectRows,
    sampledProgress,
    type ProjectRow,
  } from '../research/projects'
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
  let rows = $state<ProjectRow[]>([])
  let cursor = $state<string | null>(null)
  let nextCursor = $state<string | null>(null)
  let truncated = $state(false)
  let status = $state<'loading' | 'available' | 'empty' | 'unavailable' | 'forbidden' | 'error'>('loading')
  let reason = $state<string | null>(null)
  let selectedProject = $state<string | null>(null)

  async function load(more = false): Promise<void> {
    if (tick === null) {
      status = 'unavailable'
      reason = 'tick_required'
      return
    }
    status = 'loading'
    reason = null
    try {
      const page = await getCivilizationMap(runId, {
        section: 'projects',
        tick,
        limit: 200,
        cursor: more ? cursor : null,
      })
      const pageRows = Array.isArray(page.rows)
        ? page.rows.filter(
            (row): row is Record<string, unknown> =>
              row !== null && typeof row === 'object',
          )
        : []
      const parsed = projectRows(pageRows)
      const merged = new Map<string, ProjectRow>()
      if (more) {
        for (const row of rows) merged.set(row.key, row)
      }
      for (const row of parsed) merged.set(row.key, row)
      rows = [...merged.values()]
      cursor = typeof page.next_cursor === 'string' ? page.next_cursor : null
      nextCursor = cursor
      truncated = page.truncated === true
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

  const visible = $derived(
    selectedProject === null
      ? rows
      : rows.filter((row) => row.projectId === selectedProject),
  )

  const progress = $derived(sampledProgress(visible))

  const series = $derived(
    selectedProject === null
      ? []
      : [
          {
            id: 'labor',
            label: 'Labor progress',
            evidenceClass: 'objective_world' as const,
            ownerId: null,
            unit: 'labor units',
            coverage: null,
            sourceRef: 'observer-civilization-map-v1',
            points: progress.map((point) => ({
              tick: point.tick,
              value: point.laborProgress,
            })),
          },
          {
            id: 'material',
            label: 'Material progress',
            evidenceClass: 'objective_world' as const,
            ownerId: null,
            unit: 'items',
            coverage: null,
            sourceRef: 'observer-civilization-map-v1',
            points: progress.map((point) => ({
              tick: point.tick,
              value: point.materialProgress,
            })),
          },
        ]
  )

  const contributions = $derived(
    visible.flatMap((row) =>
      row.retainedContributions.map((item) => ({
        project: row.projectId,
        actor: item.actorId,
        tick: item.tick,
        labor: item.laborUnits,
        material: item.materialCount,
        item: item.itemId,
        identity: item.identity,
        retained: row.retainedContributions.length,
        accepted: row.acceptedContributionCount,
        truncated: row.detailTruncated,
      })),
    ),
  )
</script>

<section class="page">
  <header>
    <p class="eyebrow">Projects</p>
    <h1>Collective project history</h1>
    <p class="lede">
      Objective sampled state plus retained accepted receipts. Counters are not
      a complete event history, and contribution is not social rank.
    </p>
  </header>

  <div class="controls">
    <label>
      Boundary
      <input
        type="number"
        min="0"
        value={tick ?? 0}
        onchange={(event) => {
          tick = Number.parseInt(event.currentTarget.value, 10)
          void load()
        }}
      />
    </label>
    <label>
      Project
      <select bind:value={selectedProject}>
        <option value={null}>all projects</option>
        {#each [...new Set(rows.map((row) => row.projectId))].sort() as project (project)}
          <option value={project}>{project}</option>
        {/each}
      </select>
    </label>
    <button type="button" onclick={() => void load()}>Load project boundary</button>
  </div>

  <AvailabilityNotice status={status} reason={reason} requestedTick={tick} resolvedTick={tick} />
  {#if truncated}
    <p class="warning" role="status">
      Server reply truncated by a page/detail bound; counters and retained tails
      remain distinct.
    </p>
  {/if}

  {#if selectedProject !== null && series.length > 0}
    <SeriesChart
      title={`Project ${selectedProject} progress`}
      description="Only sampled observed boundaries; differences are display differences, not synthesized contribution events."
      {series}
    />
  {/if}

  <ResearchTable
    caption="Project state at boundary {tick}"
    columns={[
      { key: 'project', label: 'Project' },
      { key: 'kind', label: 'Kind' },
      { key: 'status', label: 'Status' },
      { key: 'location', label: 'Location' },
      { key: 'labor', label: 'Labor progress / required' },
      { key: 'material', label: 'Material progress / required' },
      { key: 'shortages', label: 'Shortages', numeric: true },
      { key: 'accepted', label: 'Accepted count', numeric: true },
      { key: 'retained', label: 'Retained tail', numeric: true },
      { key: 'structure', label: 'Linked structure' },
      { key: 'acts', label: 'Public acts' },
    ]}
    rows={visible.map((row) => ({
      project: row.projectId,
      kind: row.kind,
      status: row.status,
      location: row.locationId,
      labor: `${row.laborProgress} / ${row.laborRequired}`,
      material: `${row.materialProgress} / ${row.materialRequired} (${row.materialKind})`,
      shortages: row.shortageCount,
      accepted: row.acceptedContributionCount,
      retained: row.retainedContributions.length,
      structure: row.linkedStructureId ?? '—',
      acts: Object.entries(row.publicActs)
        .map(([key, value]) => `${key}=${value}`)
        .join(', '),
    }))}
    rowKey={(row) => String(row.project)}
    onRowSelect={(row) => {
      selectedProject = String(row.project)
    }}
  />

  {#if contributions.length > 0}
    <ResearchTable
      caption="Retained accepted contributions"
      columns={[
        { key: 'project', label: 'Project' },
        { key: 'actor', label: 'Actor' },
        { key: 'tick', label: 'Tick', numeric: true },
        { key: 'labor', label: 'Labor', numeric: true },
        { key: 'material', label: 'Material', numeric: true },
        { key: 'item', label: 'Item' },
        { key: 'limits', label: 'Counters vs tail' },
      ]}
      rows={contributions.map((row) => ({
        project: row.project,
        actor: row.actor,
        tick: row.tick,
        labor: row.labor,
        material: row.material,
        item: row.item ?? '—',
        limits: `accepted ${row.accepted} · retained ${row.retained}${row.truncated ? ' · detail truncated' : ''}`,
      }))}
      rowKey={(row) => `${row.project}:${row.actor}:${row.tick}:${row.labor}:${row.material}:${row.item}`}
    />
    <p class="muted">
      Duplicate receipt rows are presentation-deduplicated only within identical
      row evidence; retained tails are not claimed as complete event history.
    </p>
  {/if}

  {#if nextCursor !== null}
    <button type="button" onclick={() => void load(true)}>Load more projects</button>
  {/if}
</section>

<style>
  .page { display: grid; gap: 0.9rem; }
  .eyebrow { margin: 0 0 0.2rem; font-size: 0.75rem; letter-spacing: 0.08em; text-transform: uppercase; color: #5a6a72; }
  h1 { margin: 0 0 0.3rem; font-size: 1.35rem; }
  .lede { margin: 0; color: #3a474e; }
  .controls { display: flex; flex-wrap: wrap; gap: 0.6rem; align-items: end; }
  label { display: grid; gap: 0.2rem; font-size: 0.8rem; color: #5a6a72; }
  input, select, button { font: inherit; padding: 0.25rem 0.45rem; }
  .muted { color: #5a6a72; font-size: 0.85rem; }
  .warning { margin: 0; color: #6a5420; font-size: 0.85rem; }
</style>
