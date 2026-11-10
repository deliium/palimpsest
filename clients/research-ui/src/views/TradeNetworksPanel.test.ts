import { afterEach, describe, expect, it, vi } from 'vitest'
import { emptyResearchSelection } from '../research/selection'
import { flushSync, render } from '../test/mount'
import TradeNetworksPanel from './TradeNetworksPanel.svelte'

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  })
}

async function settle(): Promise<void> {
  await Promise.resolve()
  await new Promise((resolve) => setTimeout(resolve, 0))
  await Promise.resolve()
  flushSync()
}

const summary = {
  run_id: 'run-1',
  publication_id: 'trd-pub-0123456789abcdef0123456789abcdef',
  digest: 'a'.repeat(64),
  schema_version: 'trade-networks-snapshot-v1',
  window_tick: 64,
  corridor_count: 1,
  flow_count: 1,
  location_count: 2,
  major_location_count: 1,
  trade_post_location_count: 1,
  network_count: 1,
  cross_society_pair_count: 1,
  transfer_count: 2,
  emerged_count: 0,
  continued_count: 1,
  transformed_count: 0,
  split_count: 0,
  merge_count: 0,
  dissolved_count: 0,
  rerouted_count: 0,
  sustained_network_count: 1,
  lineage_edge_count: 1,
  coverage: 'complete',
  truncated: false,
}

const corridor = {
  corridor_id: 'trd-cor-0000000000000001',
  window_index: 0,
  from_location_id: 'loc-a',
  to_location_id: 'loc-b',
  flow_counts: { food: 2 },
  transfer_count: 2,
  coverage: 'complete',
}

const flow = {
  window_index: 0,
  flow_class: 'food',
  transfer_count: 2,
  cross_location_count: 2,
  imported_count: 2,
  exported_count: 2,
  local_count: 0,
  coverage: 'complete',
}

const location = {
  location_id: 'loc-b',
  window_index: 0,
  inflow_count: 2,
  outflow_count: 0,
  local_count: 0,
  corridor_degree: 1,
  is_major: true,
  trade_post_present: true,
  flow_counts: { food: 2 },
  coverage: 'complete',
}

const dependence = {
  location_id: 'loc-b',
  window_index: 0,
  flow_class: 'food',
  imported_count: 2,
  locally_originated_count: 0,
  dependence_milli: 1000,
  high_dependence: true,
  coverage: 'complete',
}

const pair = {
  pair_id: 'trd-pair-0000000000000001',
  window_index: 0,
  society_a: 'msoc-aaaaaaaaaaaaaaaa',
  society_b: 'msoc-bbbbbbbbbbbbbbbb',
  society_a_location_id: 'loc-a',
  society_b_location_id: 'loc-b',
  overlap_member_count: 0,
  flow_counts: { food: 2 },
  transfer_count: 2,
  society_a_to_b_count: 2,
  society_b_to_a_count: 0,
  coverage: 'complete',
}

const network = {
  network_id: 'trd-net-0000000000000001',
  window_index: 0,
  corridor_ids: ['trd-cor-0000000000000001'],
  location_ids: ['loc-a', 'loc-b'],
  flow_counts: { food: 2 },
  transfer_count: 2,
  status: 'continued',
  previous_network_ids: ['trd-net-0000000000000000'],
  next_network_ids: [],
  rerouted: false,
  sustained: true,
  coverage: 'complete',
}

function stubFetch(override?: (path: string) => Response | null): void {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const path = new URL(String(input), 'http://local.test').pathname
      const custom = override?.(path) ?? null
      if (custom !== null) return custom
      if (path.endsWith('/trade-networks')) return json(summary)
      if (path.endsWith('/trade-networks/corridors')) {
        return json({ items: [corridor], next_cursor: null })
      }
      if (path.endsWith('/trade-networks/flows')) {
        return json({ items: [flow], next_cursor: null })
      }
      if (path.endsWith('/trade-networks/locations')) {
        return json({ items: [location], next_cursor: null })
      }
      if (path.endsWith('/trade-networks/dependence')) {
        return json({ items: [dependence], next_cursor: null })
      }
      if (path.endsWith('/trade-networks/cross-society')) {
        return json({ items: [pair], next_cursor: null })
      }
      if (path.endsWith('/trade-networks/networks')) {
        return json({ items: [network], next_cursor: null })
      }
      return json({ code: 'not_found' }, 404)
    }),
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('TradeNetworksPanel', () => {
  it('renders six read-only sections without score or money chrome', async () => {
    stubFetch()
    const view = render(TradeNetworksPanel as never, {
      runId: 'run-1',
      selection: emptyResearchSelection({
        runId: 'run-1',
        view: 'trade-networks',
      }),
    })
    await settle()
    const text = (view.target.textContent ?? '').toLowerCase()
    expect(text).toContain('trade networks')
    expect(text).toContain('corridors')
    expect(text).toContain('flows')
    expect(text).toContain('exchange locations')
    expect(text).toContain('observed dependence')
    expect(text).toContain('cross-society flows')
    expect(text).toContain('analytical networks')
    expect(text).toContain('loc-a')
    expect(text).toContain('loc-b')
    expect(text).toContain('continued')
    expect(text).toContain('sustained')
    expect(text).toContain('trade post')
    expect(text).not.toContain('price')
    expect(text).not.toContain('money')
    expect(text).not.toContain('trade score')
    expect(text).not.toContain('planned route')
    expect(text).not.toContain('market price')
  })

  it('shows disabled state on 503', async () => {
    stubFetch(() => json({ code: 'trade_networks_disabled' }, 503))
    const view = render(TradeNetworksPanel as never, {
      runId: 'run-1',
      selection: emptyResearchSelection({
        runId: 'run-1',
        view: 'trade-networks',
      }),
    })
    await settle()
    expect(view.target.textContent ?? '').toContain('disabled')
  })

  it('shows empty state without inventing a network', async () => {
    stubFetch((path) => {
      if (path.endsWith('/trade-networks')) return json(summary)
      if (
        path.endsWith('/trade-networks/corridors') ||
        path.endsWith('/trade-networks/flows') ||
        path.endsWith('/trade-networks/locations') ||
        path.endsWith('/trade-networks/dependence') ||
        path.endsWith('/trade-networks/cross-society') ||
        path.endsWith('/trade-networks/networks')
      ) {
        return json({ items: [], next_cursor: null })
      }
      return null
    })
    const view = render(TradeNetworksPanel as never, {
      runId: 'run-1',
      selection: emptyResearchSelection({
        runId: 'run-1',
        view: 'trade-networks',
      }),
    })
    await settle()
    expect(view.target.textContent ?? '').toContain(
      'No trade evidence was published',
    )
  })

  it('shows a safe error for malformed responses', async () => {
    stubFetch(() => json({ unexpected: true }))
    const view = render(TradeNetworksPanel as never, {
      runId: 'run-1',
      selection: emptyResearchSelection({
        runId: 'run-1',
        view: 'trade-networks',
      }),
    })
    await settle()
    expect(view.target.textContent ?? '').toContain('could not be read')
  })
})
