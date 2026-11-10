import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushSync, render } from '../test/mount'
import SupplyChainsPanel from './SupplyChainsPanel.svelte'

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
  publication_id: 'sc-pub-0123456789abcdef0123456789abcdef',
  digest: 'a'.repeat(64),
  schema_version: 'supply-chains-snapshot-v1',
  window_tick: 32,
  stage_count: 2,
  edge_count: 1,
  chain_count: 1,
  lineage_count: 0,
  bottleneck_count: 1,
  location_count: 1,
  organization_count: 1,
  sustained_chain_count: 0,
  max_depth: 2,
  coverage: 'partial',
  truncated: false,
}

const stage = {
  stage_token: 'harvest_grain',
  window_index: 0,
  recipe_id: 'harvest_grain',
  action: 'harvest',
  location_token: 'loc-1',
  actor_token: 'body-1',
  item_names: [],
  completed: true,
  attempt: true,
  duration_ticks: 2,
  created_item_token: 'item-grain',
  cause: 'harvest',
  coverage: 'complete',
}

const dependency = {
  edge_token: 'sc-edge-0000000000000001',
  window_index: 0,
  from_kind: 'resource',
  from_token: 'grain',
  to_kind: 'item',
  to_token: 'grain',
  edge_kind: 'resource_to_item',
  recipe_id: 'harvest_grain',
  observed_count: 1,
  completed_count: 1,
  share_milli: 1000,
  created_elsewhere_count: 0,
  coverage: 'complete',
}

const chain = {
  chain_token: 'sc-chain-0000000000000001',
  window_index: 0,
  stage_tokens: ['grain', 'flour'],
  edge_tokens: ['sc-edge-0000000000000001'],
  depth: 2,
  completed_count: 1,
  coverage: 'complete',
}

const bottleneck = {
  bottleneck_token: 'sc-neck-0000000000000001',
  window_index: 0,
  kind: 'upstream_shortfall',
  stage_token: 'flour',
  edge_token: 'sc-edge-0000000000000001',
  observed_count: 3,
  demand_count: 4,
  supply_count: 2,
  ratio_milli: 500,
  location_token: '-',
  organization_token: '-',
  skill_domain: '-',
  coverage: 'partial',
}

const location = {
  location_token: 'loc-1',
  window_index: 0,
  observed_count: 1,
  completed_count: 1,
  coverage: 'complete',
}

const organization = {
  organization_token: 'org-1',
  window_index: 0,
  actor_count: 1,
  claim_count: 1,
  completed_count: 1,
  coverage: 'complete',
}

function stubFetch(override?: (path: string) => Response | null): void {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const path = new URL(String(input), 'http://local.test').pathname
      const custom = override?.(path) ?? null
      if (custom !== null) return custom
      if (path.endsWith('/supply-chains')) return json(summary)
      if (path.endsWith('/supply-chains/stages')) return json({ items: [stage], next_cursor: null })
      if (path.endsWith('/supply-chains/dependencies')) return json({ items: [dependency], next_cursor: null })
      if (path.endsWith('/supply-chains/chains')) return json({ items: [chain], next_cursor: null })
      if (path.endsWith('/supply-chains/bottlenecks')) return json({ items: [bottleneck], next_cursor: null })
      if (path.endsWith('/supply-chains/locations')) return json({ items: [location], next_cursor: null })
      if (path.endsWith('/supply-chains/organizations')) return json({ items: [organization], next_cursor: null })
      return json({ code: 'not_found' }, 404)
    }),
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('SupplyChainsPanel', () => {
  it('renders summary and six read-only sections without score columns', async () => {
    stubFetch()
    const view = render(SupplyChainsPanel as never, { runId: 'run-1' })
    await settle()
    const text = (view.target.textContent ?? '').toLowerCase()
    expect(text).toContain('supply chains')
    expect(text).toContain('stages')
    expect(text).toContain('dependencies')
    expect(text).toContain('chains')
    expect(text).toContain('bottlenecks')
    expect(text).toContain('locations')
    expect(text).toContain('organizations')
    expect(text).not.toContain('severity')
    expect(text).not.toContain('recommendation')
    expect(text).not.toContain('score')
  })

  it('shows disabled message on 503', async () => {
    stubFetch(() => json({ code: 'supply_chains_disabled' }, 503))
    const view = render(SupplyChainsPanel as never, { runId: 'run-1' })
    await settle()
    expect(view.target.textContent ?? '').toContain(
      'Supply chains are not published for this run.',
    )
  })

  it('shows error state for another code', async () => {
    stubFetch(() => json({ code: 'supply_chains_run_not_found' }, 404))
    const view = render(SupplyChainsPanel as never, { runId: 'run-1' })
    await settle()
    expect(view.target.textContent ?? '').toContain('could not be read')
  })

  it('renders empty tables', async () => {
    stubFetch((path) => {
      if (path.endsWith('/supply-chains')) return json(summary)
      if (path.includes('/supply-chains/')) return json({ items: [], next_cursor: null })
      return null
    })
    const view = render(SupplyChainsPanel as never, { runId: 'run-1' })
    await settle()
    expect(view.target.textContent ?? '').toContain('Stages')
  })

  it('reloads with the selected window index', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = new URL(String(input), 'http://local.test')
      if (url.pathname.endsWith('/supply-chains')) return json(summary)
      return json({ items: [], next_cursor: null })
    })
    vi.stubGlobal('fetch', fetchMock)
    const view = render(SupplyChainsPanel as never, { runId: 'run-1' })
    await settle()
    const input = view.target.querySelector('input')
    expect(input).not.toBeNull()
    if (input) {
      input.value = '2'
      input.dispatchEvent(new Event('input', { bubbles: true }))
      input.dispatchEvent(new Event('change', { bubbles: true }))
    }
    await settle()
    const urls = fetchMock.mock.calls.map((call) =>
      new URL(String(call[0]), 'http://local.test').search,
    )
    expect(urls.some((search) => search.includes('window_index=2'))).toBe(true)
  })
})
