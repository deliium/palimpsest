<script lang="ts">
  import { ApiClientError } from '../api/client'
  import {
    fetchCrossSocietyTrades,
    fetchTradeCorridors,
    fetchTradeDependence,
    fetchTradeFlows,
    fetchTradeLocations,
    fetchTradeNetworks,
    fetchTradeNetworksSummary,
    type CrossSocietyTrade,
    type TradeCorridor,
    type TradeDependence,
    type TradeFlow,
    type TradeLocation,
    type TradeNetwork,
    type TradeNetworksSummary,
  } from '../api/tradeNetworks'
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
  let summary = $state<TradeNetworksSummary | null>(null)
  let corridors = $state<TradeCorridor[]>([])
  let flows = $state<TradeFlow[]>([])
  let locations = $state<TradeLocation[]>([])
  let dependence = $state<TradeDependence[]>([])
  let crossSociety = $state<CrossSocietyTrade[]>([])
  let networks = $state<TradeNetwork[]>([])
  let windowInput = $state('')

  function label(value: string | null | undefined): string {
    return value ? value.replaceAll('_', ' ') : 'unknown'
  }

  function windowIndex(): number | undefined {
    if (windowInput.trim() === '') return undefined
    const parsed = Number(windowInput)
    return Number.isInteger(parsed) && parsed >= 0 ? parsed : undefined
  }

  async function load(): Promise<void> {
    status = 'loading'
    reason = null
    const windowIndexValue = windowIndex()
    try {
      summary = await fetchTradeNetworksSummary(runId)
      const [corridorPage, flowPage, locationPage, dependencePage, crossPage, networkPage] =
        await Promise.all([
          fetchTradeCorridors(runId, { windowIndex: windowIndexValue }),
          fetchTradeFlows(runId, { windowIndex: windowIndexValue }),
          fetchTradeLocations(runId, { windowIndex: windowIndexValue }),
          fetchTradeDependence(runId, { windowIndex: windowIndexValue }),
          fetchCrossSocietyTrades(runId, { windowIndex: windowIndexValue }),
          fetchTradeNetworks(runId, { windowIndex: windowIndexValue }),
        ])
      corridors = corridorPage.items
      flows = flowPage.items
      locations = locationPage.items
      dependence = dependencePage.items
      crossSociety = crossPage.items
      networks = networkPage.items
      const hasRows =
        corridors.length +
          flows.length +
          locations.length +
          dependence.length +
          crossSociety.length +
          networks.length >
        0
      status = hasRows ? 'ready' : 'empty'
    } catch (error) {
      if (error instanceof ApiClientError) {
        reason = error.code
        status =
          error.code === 'trade_networks_disabled' || error.code === 'http_503'
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

<section class="trade-networks">
  <h2>Trade networks <EpistemicBadge epistemic="research_inference" /></h2>
  <p>
    Exchange evidence and analytical corridors, dependence, locations, and
    networks. No central routing or aggregate model exists.
  </p>
  <label>
    Window index
    <input
      type="number"
      min="0"
      max="511"
      bind:value={windowInput}
      onchange={() => void load()}
    />
  </label>

  {#if status === 'loading'}
    <p>Loading exchange evidence…</p>
  {:else if status === 'unavailable'}
    <p>Trade networks are disabled for this run.</p>
  {:else if status === 'error'}
    <p>Trade networks could not be read. Reason: {reason ?? 'unknown'}.</p>
  {:else if status === 'empty'}
    <p>No trade evidence was published for this run and window.</p>
  {:else if summary}
    <dl>
      <dt>Corridors</dt><dd>{summary.corridor_count}</dd>
      <dt>Locations</dt><dd>{summary.location_count}</dd>
      <dt>Major locations</dt><dd>{summary.major_location_count}</dd>
      <dt>Trade posts</dt><dd>{summary.trade_post_location_count}</dd>
      <dt>Networks</dt><dd>{summary.network_count}</dd>
      <dt>Cross-society pairs</dt><dd>{summary.cross_society_pair_count}</dd>
      <dt>Transfers</dt><dd>{summary.transfer_count}</dd>
      <dt>Coverage</dt><dd>{label(summary.coverage)}</dd>
      <dt>Truncated</dt><dd>{summary.truncated ? 'yes' : 'no'}</dd>
    </dl>

    <h3>Corridors <span class="epistemic-word">analytical</span></h3>
    <ul>
      {#each corridors as corridor (corridor.corridor_id + ':' + corridor.window_index)}
        <li>
          <span>{corridor.from_location_id} → {corridor.to_location_id}</span>
          <span>window {corridor.window_index}</span>
          <span>transfers {corridor.transfer_count}</span>
          <span>
            {#each Object.entries(corridor.flow_counts) as [flowClass, count] (flowClass)}
              {label(flowClass)} {count}
            {/each}
          </span>
        </li>
      {:else}
        <li>empty</li>
      {/each}
    </ul>

    <h3>Flows <span class="epistemic-word">observed</span></h3>
    <ul>
      {#each flows as flow (flow.window_index + ':' + flow.flow_class)}
        <li>
          <span>{label(flow.flow_class)}</span>
          <span>transfers {flow.transfer_count}</span>
          <span>cross-location {flow.cross_location_count}</span>
          <span>imports {flow.imported_count}</span>
          <span>exports {flow.exported_count}</span>
          <span>local {flow.local_count}</span>
        </li>
      {:else}
        <li>empty</li>
      {/each}
    </ul>

    <h3>Exchange locations <span class="epistemic-word">analytical</span></h3>
    <ul>
      {#each locations as location (location.location_id + ':' + location.window_index)}
        <li>
          <span>{location.location_id}</span>
          <span>{location.is_major ? 'major' : 'minor'}</span>
          <span>{location.trade_post_present ? 'trade post' : 'no post'}</span>
          <span>in {location.inflow_count}</span>
          <span>out {location.outflow_count}</span>
          <span>local {location.local_count}</span>
          <span>degree {location.corridor_degree}</span>
        </li>
      {:else}
        <li>empty</li>
      {/each}
    </ul>

    <h3>Observed dependence <span class="epistemic-word">observation only</span></h3>
    <ul>
      {#each dependence as row (row.location_id + ':' + row.window_index + ':' + row.flow_class)}
        <li>
          <span>{row.location_id}</span>
          <span>{label(row.flow_class)}</span>
          <span>imported {row.imported_count}</span>
          <span>locally originated {row.locally_originated_count}</span>
          <span>milli {row.dependence_milli ?? 'unknown'}</span>
          <span>{row.high_dependence ? 'high dependence' : 'lower dependence'}</span>
          <span>{label(row.coverage)}</span>
        </li>
      {:else}
        <li>empty</li>
      {/each}
    </ul>

    <h3>Cross-society flows <span class="epistemic-word">analytical</span></h3>
    <ul>
      {#each crossSociety as pair (pair.pair_id + ':' + pair.window_index)}
        <li>
          <span>{pair.society_a} · {pair.society_b}</span>
          <span>anchors {pair.society_a_location_id} / {pair.society_b_location_id}</span>
          <span>transfers {pair.transfer_count}</span>
          <span>A→B {pair.society_a_to_b_count}</span>
          <span>B→A {pair.society_b_to_a_count}</span>
          <span>overlap {pair.overlap_member_count}</span>
        </li>
      {:else}
        <li>empty</li>
      {/each}
    </ul>

    <h3>Analytical networks</h3>
    <ul>
      {#each networks as network (network.network_id + ':' + network.window_index)}
        <li>
          <span>{network.network_id}</span>
          <span>{label(network.status)}</span>
          <span>{network.rerouted ? 'rerouted' : 'stable'}</span>
          <span>{network.sustained ? 'sustained' : 'single window'}</span>
          <span>corridors {network.corridor_ids.length}</span>
          <span>locations {network.location_ids.length}</span>
          <span>predecessors {network.previous_network_ids.length}</span>
          <span>successors {network.next_network_ids.length}</span>
        </li>
      {:else}
        <li>empty</li>
      {/each}
    </ul>
  {/if}
</section>

<style>
  .trade-networks {
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
    font-size: 0.85em;
    opacity: 0.8;
  }
</style>
