<script lang="ts">
  import { ApiClientError } from '../api/client'
  import {
    fetchInfrastructureAssets,
    fetchInfrastructureCondition,
    fetchInfrastructureEdges,
    fetchInfrastructureEffects,
    fetchInfrastructureMaintenance,
    fetchInfrastructureNetworksSummary,
    type InfrastructureAsset,
    type InfrastructureNetworksSummary,
  } from '../api/infrastructureNetworks'
  import EpistemicBadge from '../components/EpistemicBadge.svelte'
  import type { ResearchSelection } from '../research/selection'

  interface Props {
    runId: string
    selection: ResearchSelection
  }

  let { runId }: Props = $props()

  type Status = 'loading' | 'ready' | 'empty' | 'unavailable' | 'error'
  let status = $state<Status>('loading')
  let reason = $state<string | null>(null)
  let summary = $state<InfrastructureNetworksSummary | null>(null)
  let assets = $state<InfrastructureAsset[]>([])
  let edges = $state<InfrastructureAsset[]>([])
  let condition = $state<InfrastructureAsset[]>([])
  let effects = $state<InfrastructureAsset[]>([])
  let maintenance = $state<InfrastructureAsset[]>([])

  function label(value: string | null | undefined): string {
    return value ? value.replaceAll('_', ' ') : 'unknown'
  }

  async function load(): Promise<void> {
    status = 'loading'
    reason = null
    try {
      summary = await fetchInfrastructureNetworksSummary(runId)
      const [assetPage, edgePage, conditionPage, effectsPage, maintenancePage] =
        await Promise.all([
          fetchInfrastructureAssets(runId),
          fetchInfrastructureEdges(runId),
          fetchInfrastructureCondition(runId),
          fetchInfrastructureEffects(runId),
          fetchInfrastructureMaintenance(runId),
        ])
      assets = assetPage.items
      edges = edgePage.items
      condition = conditionPage.items
      effects = effectsPage.items
      maintenance = maintenancePage.items
      const empty =
        assets.length === 0 &&
        edges.length === 0 &&
        condition.length === 0 &&
        effects.length === 0 &&
        maintenance.length === 0
      status = empty ? 'empty' : 'ready'
    } catch (error) {
      if (error instanceof ApiClientError) {
        reason = error.code
        status =
          error.code === 'infrastructure_networks_disabled' ||
          error.code === 'http_503'
            ? 'unavailable'
            : 'error'
      } else {
        status = 'error'
      }
    }
  }

  $effect(() => {
    void runId
    void load()
  })
</script>

<section class="infrastructure-networks">
  <h2>Infrastructure networks</h2>
  {#if status === 'loading'}
    <p>Loading infrastructure network rows…</p>
  {:else if status === 'unavailable'}
    <p>Infrastructure networks publication is disabled for this deployment.</p>
  {:else if status === 'error'}
    <p>Infrastructure networks could not be read. Reason: {reason ?? 'unknown'}.</p>
  {:else if status === 'empty'}
    <p>No infrastructure assets were published for this run.</p>
  {:else if summary}
    <dl>
      <dt>Assets</dt><dd>{summary.asset_count}</dd>
      <dt>Nodes</dt><dd>{summary.node_count}</dd>
      <dt>Edges</dt><dd>{summary.edge_count}</dd>
      <dt>Operational</dt><dd>{summary.operational_count}</dd>
      <dt>Damaged</dt><dd>{summary.damaged_count}</dd>
      <dt>Destroyed</dt><dd>{summary.destroyed_count}</dd>
      <dt>Effects active</dt><dd>{summary.effects_active_count}</dd>
      <dt>Coverage</dt><dd>{label(summary.coverage)}</dd>
    </dl>

    <h3>
      Assets
      <span class="epistemic-word">objective</span>
      <EpistemicBadge epistemic="objective_world" />
    </h3>
    <ul>
      {#each assets as asset (asset.asset_id)}
        <li>
          <span>{asset.asset_id}</span>
          <span>{label(asset.kind)}</span>
          <span>{label(asset.topology)}</span>
          <span>{label(asset.status)}</span>
          <span>integrity {asset.integrity}</span>
          <span>effects {asset.effects_active ? 'active' : 'inactive'}</span>
        </li>
      {:else}
        <li>empty</li>
      {/each}
    </ul>

    <h3>
      Edges
      <span class="epistemic-word">objective</span>
      <EpistemicBadge epistemic="objective_world" />
    </h3>
    <ul>
      {#each edges as edge (edge.asset_id)}
        <li>
          <span>{edge.asset_id}</span>
          <span>{edge.location_id} ↔ {edge.endpoint_location_id ?? 'none'}</span>
          <span>{label(edge.status)}</span>
        </li>
      {:else}
        <li>empty</li>
      {/each}
    </ul>

    <h3>
      Condition
      <span class="epistemic-word">objective</span>
      <EpistemicBadge epistemic="objective_world" />
    </h3>
    <ul>
      {#each condition as row (row.asset_id)}
        <li>
          <span>{row.asset_id}</span>
          <span>{label(row.status)}</span>
          <span>integrity {row.integrity}</span>
        </li>
      {:else}
        <li>empty</li>
      {/each}
    </ul>

    <h3>
      Effects
      <span class="epistemic-word">objective</span>
      <EpistemicBadge epistemic="objective_world" />
    </h3>
    <ul>
      {#each effects as row (row.asset_id)}
        <li>
          <span>{row.asset_id}</span>
          <span>{row.effects_active ? 'active' : 'inactive'}</span>
          <span>{label(row.status)}</span>
        </li>
      {:else}
        <li>empty</li>
      {/each}
    </ul>

    <h3>
      Maintenance
      <span class="epistemic-word">objective</span>
      <EpistemicBadge epistemic="objective_world" />
    </h3>
    <ul>
      {#each maintenance as row (row.asset_id)}
        <li>
          <span>{row.asset_id}</span>
          <span>last maintained {row.last_maintained_tick}</span>
          <span>ticks since {row.ticks_since_maintained}</span>
        </li>
      {:else}
        <li>empty</li>
      {/each}
    </ul>
  {/if}
</section>

<style>
  .infrastructure-networks {
    display: grid;
    gap: 0.75rem;
  }

  dl {
    display: grid;
    grid-template-columns: max-content 1fr;
    gap: 0.25rem 1rem;
  }

  ul {
    margin: 0;
    padding-left: 1.25rem;
  }

  .epistemic-word {
    font-size: 0.75rem;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    margin-inline: 0.35rem;
  }
</style>
