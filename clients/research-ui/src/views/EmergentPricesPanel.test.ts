import { afterEach, describe, expect, it, vi } from 'vitest'
import { emptyResearchSelection } from '../research/selection'
import { flushSync, render } from '../test/mount'
import EmergentPricesPanel from './EmergentPricesPanel.svelte'

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
  publication_id: 'prc-pub-00000000000000000000000000000000',
  digest: 'sha256:' + 'a'.repeat(64),
  schema_version: 'emergent-prices-snapshot-v1',
  window_tick: 64,
  window_count: 3,
  unit_count: 1,
  expectation_count: 1,
  quote_count: 0,
  distribution_count: 1,
  market_count: 1,
  relation_count: 1,
  exchange_count: 8,
  quote_event_count: 0,
  evidence_coverage: 'complete',
  expectation_coverage: 'complete',
  quote_coverage: 'missing',
  distribution_coverage: 'complete',
  market_coverage: 'complete',
  relation_coverage: 'complete',
  coverage: 'partial',
  truncated: false,
}

const unit = {
  unit_token: 'water',
  unit_source: 'exchange_counterpart',
  owner_count: 2,
  expectation_count: 1,
  distribution_count: 1,
  median_confidence_milli: 650,
  unit_alignment: 'consistent',
  coverage: 'complete',
}

const distribution = {
  distribution_id: 'prcd-0000000000000000',
  window_index: 0,
  venue_id: 'mkt-ven-0000000000000000',
  market_token: 'none',
  item_kind: 'food',
  unit_kind: 'water',
  unit_source: 'exchange_counterpart',
  sample_source: 'completed',
  sample_count: 4,
  min_ratio_milli: 1000,
  p25_ratio_milli: 1000,
  median_ratio_milli: 1000,
  p75_ratio_milli: 1000,
  max_ratio_milli: 1000,
  iqr_milli: 0,
  dispersion_milli: 0,
  bin_shares_milli: [0, 0, 0, 0, 1000],
  status: 'available',
  coverage: 'complete',
}

const relation = {
  relation_id: 'prcr-0000000000000000',
  window_index: 0,
  group_kind: 'market',
  group_a_token: 'mktc-0000000000000000',
  group_b_token: 'mktc-1111111111111111',
  item_kind: 'food',
  unit_kind: 'water',
  unit_source: 'exchange_counterpart',
  sample_source: 'completed',
  overlap_milli: 1000,
  median_gap_milli: 0,
  relation: 'converged',
  sample_a: 4,
  sample_b: 4,
  coverage: 'complete',
}

function page(rows: unknown[]): Response {
  return json({
    run_id: 'run-1',
    publication_id: summary.publication_id,
    window_index: null,
    rows,
    next_cursor: null,
    coverage: 'complete',
  })
}

function mockFetch(): void {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      if (url.endsWith('/emergent-prices')) return json(summary)
      if (url.includes('/units')) return page([unit])
      if (url.includes('/distributions')) return page([distribution])
      if (url.includes('/relations')) return page([relation])
      return page([])
    }),
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('EmergentPricesPanel', () => {
  it('renders distributions, counts, and convergence tokens', async () => {
    mockFetch()
    const view = render(EmergentPricesPanel as never, {
      runId: 'run-1',
      selection: emptyResearchSelection({
        runId: 'run-1',
        view: 'emergent-prices',
      }),
    })
    await settle()
    const text = (view.target.textContent ?? '').toLowerCase()
    expect(text).toContain('distributions')
    expect(text).toContain('median ratio')
    expect(text).toContain('converged')
    expect(text).toContain('completed')
    expect(text).not.toMatch(/canonical price/)
    expect(view.target.querySelectorAll('form').length).toBe(0)
  })

  it('maps a disabled response to unavailable', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => json({ detail: 'emergent_prices_disabled' }, 503)),
    )
    const view = render(EmergentPricesPanel as never, {
      runId: 'run-1',
      selection: emptyResearchSelection({
        runId: 'run-1',
        view: 'emergent-prices',
      }),
    })
    await settle()
    const text = (view.target.textContent ?? '').toLowerCase()
    expect(text).toContain('disabled')
  })
})
