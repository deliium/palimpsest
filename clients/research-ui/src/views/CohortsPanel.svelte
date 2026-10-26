<script lang="ts">
  import { onMount } from 'svelte'
  import { ApiClientError } from '../api/client'
  import { getDemographics } from '../api/research'
  import AvailabilityNotice from '../components/research/AvailabilityNotice.svelte'
  import EvidenceLegend from '../components/research/EvidenceLegend.svelte'
  import ResearchTable from '../components/research/ResearchTable.svelte'
  import type { DemographicsEnvelope } from '../api/researchSchemas'
  import {
    cohortPatch,
    cohortRows,
    compareCohorts,
    resolveCohortSelection,
    survivalShare,
    type NamedCohortRow,
  } from '../research/cohorts'
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

  let envelope = $state<DemographicsEnvelope | null>(null)
  let rows = $state<NamedCohortRow[]>([])
  let loading = $state(false)
  let error = $state<string | null>(null)
  let secondaryKey = $state<string | null>(null)
  let cursor = $state<string | null>(null)
  let more = $state(false)
  let epoch = 0

  const tick = $derived(selection.tick)

  const primary = $derived(
    resolveCohortSelection(rows, {
      cohortGenerationIndex: selection.cohort?.generationIndex ?? null,
      cohortEntryTick: selection.cohort?.entryTick ?? null,
      cohortId: selection.cohort?.cohortId ?? null,
    }),
  )

  const comparison = $derived(
    compareCohorts(
      [
        primary.kind === 'resolved' ? primary.row : null,
        rows.find((row) => row.key === secondaryKey) ?? null,
      ].filter((row): row is NamedCohortRow => row !== null),
    ),
  )

  const generationOptions = $derived(
    [...new Set(rows.map((row) => row.generationIndex))].sort(
      (left, right) => left - right,
    ),
  )

  onMount(() => {
    void load()
  })

  $effect(() => {
    if (runId !== '' && tick !== null) {
      void load()
    }
  })

  async function load(loadMore = false): Promise<void> {
    if (tick === null) {
      return
    }
    const current = ++epoch
    if (!loadMore) {
      loading = true
      error = null
      rows = []
      cursor = null
    } else {
      more = true
    }
    try {
      const page = await getDemographics(runId, {
        tick,
        section: 'cohorts',
        afterGroupKey: loadMore ? cursor : null,
        limit: 200,
      })
      if (current !== epoch) {
        return
      }
      envelope = page
      const pageRows = cohortRows(runId, [page])
      if (loadMore) {
        // Merge only exact composite identities.
        const merged = new Map<string, NamedCohortRow>()
        for (const row of rows) {
          merged.set(row.key, row)
        }
        for (const row of pageRows) {
          merged.set(row.key, row)
        }
        rows = [...merged.values()]
      } else {
        rows = pageRows
      }
      cursor = page.next_after_group_key
    } catch (err) {
      if (current !== epoch) {
        return
      }
      error = err instanceof ApiClientError ? err.code : 'fetch_failed'
    } finally {
      if (current === epoch) {
        loading = false
        more = false
      }
    }
  }

  function choosePrimary(row: NamedCohortRow): void {
    onSelectionChange(cohortPatch(row))
  }

  function selectGeneration(value: string): void {
    if (value === '') {
      onSelectionChange({ generationIndex: null })
      return
    }
    onSelectionChange({ generationIndex: Number.parseInt(value, 10) })
  }

  function shareLabel(row: NamedCohortRow): string {
    const share = survivalShare(row)
    return share === null ? '—' : `${(share * 100).toFixed(1)}%`
  }
</script>

<section class="page">
  <header>
    <p class="eyebrow">Cohorts</p>
    <h1>Within-run cohort comparison</h1>
    <p class="lede">
      Descriptive census shares at one explicit boundary. Not Kaplan–Meier
      survival and not a causal effect.
    </p>
  </header>

  {#if tick === null}
    <p class="status" role="status">
      Select a tick in Population first; cohort rows are read at an explicit
      boundary.
    </p>
  {:else}
    <div class="controls">
      <label>
        Navigation generation
        <select
          value={selection.generationIndex ?? ''}
          onchange={(event) => selectGeneration(event.currentTarget.value)}
        >
          <option value="">Not selected</option>
          {#each generationOptions as generation (generation)}
            <option value={generation}>Generation {generation}</option>
          {/each}
        </select>
      </label>
      <label>
        Second cohort
        <select
          value={secondaryKey ?? ''}
          onchange={(event) => (secondaryKey = event.currentTarget.value || null)}
        >
          <option value="">Not selected</option>
          {#each rows as row (row.key)}
            <option value={row.key}>{row.generationIndex} · {row.entryTick} · {row.cohortId}</option>
          {/each}
        </select>
      </label>
      <button type="button" onclick={() => void load()} disabled={loading}>
        Reload boundary
      </button>
    </div>

    <AvailabilityNotice
      status={loading ? 'loading' : envelope?.availability === 'unavailable' ? 'unavailable' : 'available'}
      reason={envelope?.reason_code ?? null}
      requestedTick={tick}
      resolvedTick={envelope?.resolved_tick ?? null}
    />

    {#if error !== null}
      <p class="status error" role="alert">{error}</p>
    {/if}

    {#if primary.kind === 'ambiguous'}
      <p class="status warning" role="alert">
        ambiguous_cohort_selection: the quoted cohort ID matches more than one
        generation/entry tuple. Choose the exact composite cohort.
      </p>
    {:else if primary.kind === 'incomplete'}
      <p class="status warning" role="alert">
        The cohort selection is incomplete. Choose a full
        generation · entry tick · cohort ID tuple.
      </p>
    {:else if selection.cohort !== null && primary.kind === 'none' && !loading}
      <p class="status warning" role="status">
        The selected composite cohort is not present at tick {tick}.
      </p>
    {/if}

    {#if comparison.length > 0}
      <section>
        <h2>Aligned comparison</h2>
        <table>
          <caption>Cohort comparison at tick {tick}</caption>
          <thead>
            <tr>
              <th scope="col">Cohort</th>
              <th scope="col">Admitted</th>
              <th scope="col">Living</th>
              <th scope="col">Dead</th>
              <th scope="col">Living / admitted</th>
              <th scope="col">Exposure</th>
            </tr>
          </thead>
          <tbody>
            {#each comparison as facet (facet.key)}
              <tr>
                <th scope="row">{facet.label}</th>
                <td>{facet.admitted}</td>
                <td>{facet.living}</td>
                <td>{facet.dead}</td>
                <td>{facet.share === null ? '—' : `${(facet.share * 100).toFixed(1)}%`}</td>
                <td>{facet.exposureTicks === null ? '—' : `${facet.exposureTicks} ticks`}</td>
              </tr>
            {/each}
          </tbody>
        </table>
        <p class="muted">{comparison[0]?.provenance}</p>
        <EvidenceLegend
          entries={comparison.map((facet) => ({
            label: facet.label,
            evidenceClass: 'objective_world' as const,
            source: 'observer-demographics-v1',
            window: `tick ${tick}`,
          }))}
        />
      </section>
    {/if}

    <ResearchTable
      caption="Cohorts at tick {tick}"
      columns={[
        { key: 'generationIndex', label: 'Generation', numeric: true },
        { key: 'entryTick', label: 'Entry tick', numeric: true },
        { key: 'cohortId', label: 'Cohort' },
        { key: 'admitted', label: 'Admitted', numeric: true },
        { key: 'living', label: 'Living', numeric: true },
        { key: 'dead', label: 'Dead', numeric: true },
        { key: 'share', label: 'Living / admitted' },
        { key: 'selected', label: 'Primary' },
      ]}
      rows={rows.map((row) => ({
        generationIndex: row.generationIndex,
        entryTick: row.entryTick,
        cohortId: row.cohortId,
        admitted: row.admitted,
        living: row.living,
        dead: row.dead,
        share: shareLabel(row),
        selected:
          primary.kind === 'resolved' && primary.row.key === row.key ? 'yes' : '',
      }))}
      rowKey={(row) => `${row.generationIndex}:${row.entryTick}:${row.cohortId}`}
      onRowSelect={(row) => {
        const found = rows.find(
          (item) =>
            item.generationIndex === row.generationIndex &&
            item.entryTick === row.entryTick &&
            item.cohortId === row.cohortId,
        )
        if (found !== undefined) {
          choosePrimary(found)
        }
      }}
    />

    {#if cursor !== null}
      <button type="button" onclick={() => void load(true)} disabled={more}>
        Load more cohorts
      </button>
    {/if}
  {/if}
</section>

<style>
  .page {
    display: grid;
    gap: 1rem;
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
    font-size: 1.4rem;
  }

  h2 {
    margin: 0 0 0.35rem;
    font-size: 1rem;
  }

  .lede {
    margin: 0;
    color: #3a474e;
  }

  .controls {
    display: flex;
    flex-wrap: wrap;
    gap: 0.75rem;
    align-items: end;
  }

  label {
    display: grid;
    gap: 0.2rem;
    font-size: 0.8rem;
    color: #5a6a72;
  }

  select,
  button {
    font: inherit;
    padding: 0.25rem 0.45rem;
  }

  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.9rem;
  }

  caption {
    text-align: left;
    font-weight: 600;
    padding-bottom: 0.3rem;
  }

  th,
  td {
    border-bottom: 1px solid rgba(28, 36, 40, 0.12);
    padding: 0.3rem 0.45rem;
    text-align: left;
  }

  .warning {
    color: #6a5420;
  }

  .error {
    color: #8a3030;
  }

  .muted {
    color: #5a6a72;
    font-size: 0.85rem;
  }
</style>
