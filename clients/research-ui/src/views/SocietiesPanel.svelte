<script lang="ts">
  import {
    ApiClientError,
    getMetricCatalog,
    getMetricDocument,
    type MetricCatalogItem,
  } from '../api/client'
  import {
    getCivilizationCatalogue,
    getCivilizationOverlays,
  } from '../api/research'
  import EpistemicBadge from '../components/EpistemicBadge.svelte'
  import ResearchTable from '../components/research/ResearchTable.svelte'
  import { societyGroups, type SocietyGroup } from '../research/spatial'
  import type { ResearchSelection } from '../research/selection'

  interface Props {
    runId: string
    selection?: ResearchSelection
  }

  let { runId, selection = undefined }: Props = $props()

  const SOCIETY_FAMILIES = [
    'society_emergence',
    'society_divergence',
    'society_isolation',
  ] as const

  type SocietyCard = {
    family: string
    availability: string
    values: Array<{ key: string; value: string }>
    reason?: string
  }

  let cards = $state<SocietyCard[]>([])
  let availability = $state('unavailable')
  let loading = $state(true)
  let error = $state<string | null>(null)
  let groups = $state<SocietyGroup[]>([])
  let groupStatus = $state<string>('unavailable')
  let groupReason = $state<string | null>(null)
  let selectedGroups = $state<string[]>([])

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

  async function loadCard(item: MetricCatalogItem): Promise<SocietyCard> {
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
      const items = SOCIETY_FAMILIES.flatMap((family) =>
        catalog.items.filter((item) => item.metric_family === family),
      )
      cards = await Promise.all(items.map(loadCard))
    } catch (err) {
      error = err instanceof ApiClientError ? err.code : 'fetch_failed'
      cards = []
    } finally {
      loading = false
    }
    await loadGroups()
  }

  async function loadGroups(): Promise<void> {
    const tick = selection?.tick ?? 0
    groupStatus = 'loading'
    try {
      const catalogue = await getCivilizationCatalogue(runId, {
        evidenceClass: 'ANALYTICAL',
        layer: 'social_groups',
        limit: 200,
      })
      const boundaries = Array.isArray(catalogue.boundaries)
        ? catalogue.boundaries
        : []
      const target =
        boundaries.find(
          (row) =>
            row !== null &&
            typeof row === 'object' &&
            (row as Record<string, unknown>).boundary_tick === tick,
        ) !== undefined
          ? tick
          : Number(
              (boundaries.at(-1) as Record<string, unknown> | undefined)
                ?.boundary_tick ?? 0,
            )
      const overlay = await getCivilizationOverlays(runId, {
        tick: target,
        layer: 'social_groups',
        evidenceClass: 'ANALYTICAL',
        limit: 200,
      })
      if (overlay.availability === 'unavailable') {
        groupStatus = 'unavailable'
        groupReason = overlay.reason ?? null
        groups = []
        return
      }
      const rows = Array.isArray(overlay.rows)
        ? overlay.rows.filter(
            (row): row is Record<string, unknown> =>
              row !== null && typeof row === 'object',
          )
        : []
      groups = societyGroups(rows)
      groupStatus = groups.length === 0 ? 'empty' : 'available'
      groupReason = null
    } catch (err) {
      groupStatus = 'error'
      groupReason = err instanceof ApiClientError ? err.code : 'fetch_failed'
      groups = []
    }
  }

  function toggleGroup(groupId: string): void {
    if (selectedGroups.includes(groupId)) {
      selectedGroups = selectedGroups.filter((item) => item !== groupId)
      return
    }
    if (selectedGroups.length < 2) {
      selectedGroups = [...selectedGroups, groupId]
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
      <h2>Candidate societies</h2>
      <p class="lede">
        Analytical communities inferred after the run. These labels never enter
        agent cognition, memory, or observations.
      </p>
    </div>
    <EpistemicBadge epistemic="research_inference" />
  </header>

  <section>
    <h3>Candidate community lanes</h3>
    <p class="muted">
      Analytical groups are scoped to run, policy and window. Equal generation
      numbers do not imply equal ages or community identity.
    </p>
    {#if groupStatus === 'unavailable'}
      <p class="muted">Community overlay unavailable{groupReason ? `: ${groupReason}` : ''}.</p>
    {:else if groupStatus === 'empty'}
      <p class="muted">Complete empty group inventory at this boundary.</p>
    {:else if groupStatus === 'error'}
      <p class="muted">Community overlay error: {groupReason}</p>
    {:else}
      <ResearchTable
        caption="Analytical community candidates"
        columns={[
          { key: 'group', label: 'Group' },
          { key: 'basis', label: 'Basis' },
          { key: 'members', label: 'Members', numeric: true },
          { key: 'missing', label: 'Missing lanes' },
          { key: 'policy', label: 'Policy' },
          { key: 'selected', label: 'Selected' },
        ]}
        rows={groups.map((group) => ({
          group: group.groupId,
          basis: group.basis,
          members: group.memberCount,
          missing: group.missingLanes.join(', ') || 'none',
          policy: group.policyVersion ?? 'unknown',
          selected: selectedGroups.includes(group.groupId) ? 'yes' : '',
        }))}
        rowKey={(row) => String(row.group)}
        onRowSelect={(row) => toggleGroup(String(row.group))}
      />
      {#if selectedGroups.length > 0}
        <p class="muted">
          Comparing {selectedGroups.join(' vs ')}. Sources and denominators are
          independent; no polity or society registry is created.
        </p>
      {/if}
    {/if}
  </section>

  {#if loading}
    <p class="muted">Loading society metrics…</p>
  {:else if error !== null}
    <p class="muted">Society metrics unavailable: {error}</p>
  {:else if cards.length === 0}
    <p class="muted">No society families in this run (catalog: {availability}).</p>
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
    text-align: right;
  }
</style>
