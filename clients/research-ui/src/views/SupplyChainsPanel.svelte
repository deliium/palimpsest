<script lang="ts">
  import { ApiClientError } from '../api/client'
  import {
    fetchSupplyBottlenecks,
    fetchSupplyChainSummary,
    fetchSupplyChains,
    fetchSupplyDependencies,
    fetchSupplyLocations,
    fetchSupplyOrganizations,
    fetchSupplyStages,
    type SupplyBottleneck,
    type SupplyChain,
    type SupplyChainSummary,
    type SupplyDependency,
    type SupplyLocation,
    type SupplyOrganization,
    type SupplyStage,
  } from '../api/supplyChains'
  import EpistemicBadge from '../components/EpistemicBadge.svelte'

  interface Props {
    runId: string
    initialWindowIndex?: number | undefined
  }

  let { runId, initialWindowIndex = undefined }: Props = $props()

  type Status = 'idle' | 'loading' | 'ready' | 'unavailable' | 'error'
  let status = $state<Status>('idle')
  let summary = $state<SupplyChainSummary | null>(null)
  let stages = $state<SupplyStage[]>([])
  let dependencies = $state<SupplyDependency[]>([])
  let chains = $state<SupplyChain[]>([])
  let bottlenecks = $state<SupplyBottleneck[]>([])
  let locations = $state<SupplyLocation[]>([])
  let organizations = $state<SupplyOrganization[]>([])
  let windowInput = $state('')

  $effect(() => {
    if (initialWindowIndex !== undefined && windowInput === '') {
      windowInput = String(initialWindowIndex)
    }
  })

  function windowIndex(): number | undefined {
    const raw = String(windowInput).trim()
    if (raw === '') return undefined
    const parsed = Number(raw)
    return Number.isInteger(parsed) && parsed >= 0 ? parsed : undefined
  }

  async function load(): Promise<void> {
    status = 'loading'
    const windowIndexValue = windowIndex()
    try {
      summary = await fetchSupplyChainSummary(runId)
      const [stagePage, dependencyPage, chainPage, bottleneckPage, locationPage, organizationPage] =
        await Promise.all([
          fetchSupplyStages(runId, { windowIndex: windowIndexValue }),
          fetchSupplyDependencies(runId, { windowIndex: windowIndexValue }),
          fetchSupplyChains(runId, { windowIndex: windowIndexValue }),
          fetchSupplyBottlenecks(runId, { windowIndex: windowIndexValue }),
          fetchSupplyLocations(runId, { windowIndex: windowIndexValue }),
          fetchSupplyOrganizations(runId, { windowIndex: windowIndexValue }),
        ])
      stages = stagePage.items
      dependencies = dependencyPage.items
      chains = chainPage.items
      bottlenecks = bottleneckPage.items
      locations = locationPage.items
      organizations = organizationPage.items
      status = 'ready'
    } catch (error) {
      if (error instanceof ApiClientError) {
        status =
          error.code === 'supply_chains_disabled' || error.code === 'http_503'
            ? 'unavailable'
            : 'error'
      } else {
        status = 'error'
      }
    }
  }

  function changeWindow(): void {
    void load()
  }

  $effect(() => {
    void runId
    void load()
  })
</script>

<section class="supply-chains">
  <h2>Supply chains <EpistemicBadge epistemic="research_inference" /></h2>
  <p>
    Observed production stages, dependency edges, chains, and descriptive
    bottlenecks. No central planner or ranking exists.
  </p>
  <label>
    Window index
    <input
      type="number"
      min="0"
      max="511"
      bind:value={windowInput}
      onchange={changeWindow}
    />
  </label>

  {#if status === 'loading' || status === 'idle'}
    <p>Loading supply-chain evidence…</p>
  {:else if status === 'unavailable'}
    <p>Supply chains are not published for this run.</p>
  {:else if status === 'error'}
    <p>Supply-chain evidence could not be read.</p>
  {:else if summary}
    <dl>
      <dt>Stages</dt><dd>{summary.stage_count}</dd>
      <dt>Edges</dt><dd>{summary.edge_count}</dd>
      <dt>Chains</dt><dd>{summary.chain_count}</dd>
      <dt>Bottlenecks</dt><dd>{summary.bottleneck_count}</dd>
      <dt>Coverage</dt><dd>{summary.coverage}</dd>
    </dl>

    <h3>Stages</h3>
    <table>
      <thead><tr><th>Recipe</th><th>Action</th><th>Completed</th></tr></thead>
      <tbody>
        {#each stages as stage (stage.stage_token + stage.window_index)}
          <tr><td>{stage.recipe_id}</td><td>{stage.action}</td><td>{stage.completed}</td></tr>
        {/each}
      </tbody>
    </table>

    <h3>Dependencies</h3>
    <table>
      <thead><tr><th>From</th><th>To</th><th>Kind</th><th>Share</th></tr></thead>
      <tbody>
        {#each dependencies as edge (edge.edge_token)}
          <tr><td>{edge.from_token}</td><td>{edge.to_token}</td><td>{edge.edge_kind}</td><td>{edge.share_milli}</td></tr>
        {/each}
      </tbody>
    </table>

    <h3>Chains</h3>
    <ul>
      {#each chains as chain (chain.chain_token)}
        <li>{chain.stage_tokens.join(' → ')} (depth {chain.depth})</li>
      {/each}
    </ul>

    <h3>Bottlenecks</h3>
    <table>
      <thead><tr><th>Kind</th><th>Stage</th><th>Ratio</th></tr></thead>
      <tbody>
        {#each bottlenecks as row (row.bottleneck_token)}
          <tr><td>{row.kind}</td><td>{row.stage_token}</td><td>{row.ratio_milli}</td></tr>
        {/each}
      </tbody>
    </table>

    <h3>Locations</h3>
    <table>
      <thead><tr><th>Location</th><th>Completed</th></tr></thead>
      <tbody>
        {#each locations as row (row.location_token + row.window_index)}
          <tr><td>{row.location_token}</td><td>{row.completed_count}</td></tr>
        {/each}
      </tbody>
    </table>

    <h3>Organizations</h3>
    <table>
      <thead><tr><th>Organization</th><th>Completed</th></tr></thead>
      <tbody>
        {#each organizations as row (row.organization_token + row.window_index)}
          <tr><td>{row.organization_token}</td><td>{row.completed_count}</td></tr>
        {/each}
      </tbody>
    </table>
  {/if}
</section>
