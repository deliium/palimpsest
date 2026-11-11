import { afterEach, describe, expect, it, vi } from 'vitest'
import { emptyResearchSelection } from '../research/selection'
import { flushSync, render } from '../test/mount'
import MarketInstitutionsPanel from './MarketInstitutionsPanel.svelte'

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
  publication_id: 'mkt-pub-00000000000000000000000000000000',
  digest: 'a'.repeat(64),
  schema_version: 'market-institutions-snapshot-v1',
  window_tick: 64,
  venue_count: 1,
  gathering_count: 2,
  market_like_venue_count: 1,
  recurring_venue_count: 0,
  expected_venue_count: 0,
  market_count: 1,
  expectation_row_count: 0,
  role_row_count: 0,
  record_anchor_count: 0,
  emerged_count: 0,
  continued_count: 1,
  transformed_count: 0,
  split_count: 0,
  merge_count: 0,
  dissolved_count: 0,
  sustained_market_count: 1,
  lineage_edge_count: 1,
  coverage: 'complete',
  truncated: false,
}

const venue = {
  venue_id: 'mkt-ven-0000000000000001',
  window_index: 0,
  location_id: 'loc-a',
  exchange_count: 2,
  proposal_count: 0,
  withdrawn_count: 0,
  distinct_party_count: 2,
  distinct_actor_count: 1,
  active_window_count: 1,
  recurrence_milli: 1000,
  status: 'single_gathering',
  market_like: false,
  coverage: 'complete',
}

function page(rows: unknown[]): Response {
  return json({
    run_id: 'run-1',
    publication_id: summary.publication_id,
    window_index: null,
    rows,
    next_cursor: null,
    lineage: [],
    coverage: 'complete',
  })
}

function mockFetch(): void {
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input)
    if (url.endsWith('/market-institutions')) return json(summary)
    if (url.includes('/venues')) return page([venue])
    return page([])
  }))
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('MarketInstitutionsPanel', () => {
  it('renders counts and venue status tokens', async () => {
    mockFetch()
    const view = render(MarketInstitutionsPanel as never, {
      runId: 'run-1',
      selection: emptyResearchSelection({
        runId: 'run-1',
        view: 'market-institutions',
      }),
    })
    await settle()
    const text = (view.target.textContent ?? '').toLowerCase()
    expect(text).toContain('venues')
    expect(text).toContain('single gathering')
    expect(text).not.toMatch(/price|money|currency|ranking|recommendation/i)
  })

  it('maps a disabled response to unavailable', async () => {
    vi.stubGlobal('fetch', vi.fn(async () =>
      json({ detail: 'market_institutions_disabled' }, 503)))
    const view = render(MarketInstitutionsPanel as never, {
      runId: 'run-1',
      selection: emptyResearchSelection({
        runId: 'run-1',
        view: 'market-institutions',
      }),
    })
    await settle()
    const text = (view.target.textContent ?? '').toLowerCase()
    expect(text).toContain('disabled')
  })
})
