import { afterEach, describe, expect, it, vi } from 'vitest'
import { emptyResearchSelection } from '../research/selection'
import { flushSync, render } from '../test/mount'
import CreditRelationshipsPanel from './CreditRelationshipsPanel.svelte'

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
  publication_id: 'cred-pub-0000000000000000',
  digest: 'sha256:' + 'a'.repeat(64),
  schema_version: 'credit-relationships-snapshot-v1',
  window_tick: 64,
  window_count: 2,
  relationship_count: 1,
  claim_count: 1,
  performance_count: 1,
  distribution_count: 1,
  counterparty_count: 1,
  alignment_count: 1,
  claim_event_count: 1,
  transfer_event_count: 1,
  evidence_coverage: 'complete',
  owner_coverage: 'complete',
  relationship_coverage: 'complete',
  performance_coverage: 'complete',
  distribution_coverage: 'complete',
  counterparty_coverage: 'complete',
  alignment_coverage: 'complete',
  coverage: 'complete',
  truncated: false,
}

const relationship = {
  relationship_id: 'credo-0000000000000000',
  window_index: 0,
  owner_token: 'agent-1',
  counterparty_token: 'credpeer-0000000000000000',
  direction: 'owner_debtor',
  anchor_token: 'crd-0000000000000000',
  principal_kind: 'food',
  principal_quantity: 2,
  repayment_kind: 'water',
  repayment_quantity: 3,
  repayment_ratio_milli: 1500,
  due_tick: 10,
  condition: 'by_deadline',
  collateral_kind: 'none',
  collateral_quantity: 0,
  status: 'repaid',
  confidence_milli: 500,
  expectation_milli: 500,
  trust_milli: 500,
  claim_count: 1,
  coverage: 'complete',
}

const claim = {
  claim_id: 'credcl-0000000000000000',
  window_index: 0,
  event_token: 'evt-1',
  actor_token: 'body-a',
  counterparty_token: 'body-b',
  act: 'propose',
  direction: 'owner_debtor',
  anchor_token: 'crd-0000000000000000',
  principal_kind: 'food',
  principal_quantity: 2,
  repayment_kind: 'water',
  repayment_quantity: 3,
  paid_quantity: 0,
  opened_tick: 0,
  due_tick: 10,
  condition: 'by_deadline',
  collateral_kind: 'none',
  collateral_quantity: 0,
  confidence_milli: 500,
  coverage: 'complete',
}

const performance = {
  performance_id: 'credp-0000000000000000',
  window_index: 0,
  anchor_token: 'crd-0000000000000000',
  claim_count: 1,
  repay_claim_count: 1,
  default_claim_count: 0,
  forgive_claim_count: 0,
  dispute_claim_count: 0,
  renegotiate_claim_count: 0,
  observed_transfer_count: 1,
  repaid_quantity: 3,
  principal_quantity: 2,
  repayment_quantity: 3,
  outcome: 'repaid',
  coverage: 'complete',
}

const distribution = {
  distribution_id: 'credd-0000000000000000',
  window_index: 0,
  principal_kind: 'food',
  repayment_kind: 'water',
  sample_source: 'agreed',
  sample_count: 4,
  min_ratio_milli: 1000,
  p25_ratio_milli: 1000,
  median_ratio_milli: 2000,
  p75_ratio_milli: 2000,
  max_ratio_milli: 3000,
  iqr_milli: 1000,
  dispersion_milli: 500,
  bin_shares_milli: [250, 0, 500, 0, 250],
  status: 'available',
  coverage: 'complete',
}

const counterparty = {
  counterparty_token: 'credcp-0000000000000000',
  window_index: 0,
  relationship_count: 1,
  owner_count: 1,
  claim_count: 1,
  repay_claim_count: 1,
  default_claim_count: 0,
  forgive_claim_count: 0,
  dispute_claim_count: 0,
  observed_transfer_count: 1,
  coverage: 'complete',
}

const alignment = {
  alignment_id: 'creda-0000000000000000',
  window_index: 0,
  owner_token: 'agent-1',
  anchor_token: 'crd-0000000000000000',
  alignment: 'consistent',
  owner_status: 'repaid',
  analytical_outcome: 'repaid',
  owner_paid_quantity: 3,
  declared_repayment_quantity: 3,
  observed_transfer_count: 1,
  gap_milli: 0,
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

function mockFetch(): ReturnType<typeof vi.fn> {
  const spy = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input)
    if (url.endsWith('/credit-relationships')) return json(summary)
    if (url.includes('/relationships')) return page([relationship])
    if (url.includes('/claims')) return page([claim])
    if (url.includes('/performances')) return page([performance])
    if (url.includes('/distributions')) return page([distribution])
    if (url.includes('/counterparties')) return page([counterparty])
    if (url.includes('/alignment')) return page([alignment])
    return page([])
  })
  vi.stubGlobal('fetch', spy)
  return spy
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('CreditRelationshipsPanel', () => {
  it('renders summary and one row per family', async () => {
    mockFetch()
    const view = render(CreditRelationshipsPanel as never, {
      runId: 'run-1',
      selection: emptyResearchSelection({
        runId: 'run-1',
        view: 'overview',
      }),
    })
    await settle()
    const text = (view.target.textContent ?? '').toLowerCase()
    expect(text).toContain('credit relationships')
    expect(text).toContain('repaid')
    expect(text).toContain('consistent')
    expect(text).toContain('distributions')
    expect(text).toContain('no bank, money, enforceable debt')
    expect(text).toContain('canonical credit is shown')
    expect(view.target.querySelectorAll('form').length).toBe(0)
  })

  it('maps a disabled response to unavailable', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        json({ detail: 'credit_relationships_disabled' }, 503),
      ),
    )
    const view = render(CreditRelationshipsPanel as never, {
      runId: 'run-1',
      selection: emptyResearchSelection({
        runId: 'run-1',
        view: 'overview',
      }),
    })
    await settle()
    expect((view.target.textContent ?? '').toLowerCase()).toContain('disabled')
  })

  it('renders empty when all pages are empty', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) =>
        String(input).endsWith('/credit-relationships')
          ? json(summary)
          : page([]),
      ),
    )
    const view = render(CreditRelationshipsPanel as never, {
      runId: 'run-1',
      selection: emptyResearchSelection({
        runId: 'run-1',
        view: 'overview',
      }),
    })
    await settle()
    expect((view.target.textContent ?? '').toLowerCase()).toContain('no credit')
  })

  it('renders error on another client error', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => json({ detail: 'credit_relationships_store_corrupt' }, 500)),
    )
    const view = render(CreditRelationshipsPanel as never, {
      runId: 'run-1',
      selection: emptyResearchSelection({
        runId: 'run-1',
        view: 'overview',
      }),
    })
    await settle()
    expect((view.target.textContent ?? '').toLowerCase()).toContain('unavailable')
  })

  it('passes the parsed window filter to fetchers', async () => {
    const spy = mockFetch()
    const view = render(CreditRelationshipsPanel as never, {
      runId: 'run-1',
      selection: emptyResearchSelection({
        runId: 'run-1',
        view: 'overview',
      }),
    })
    await settle()
    const input = view.target.querySelector('input')
    if (input) {
      input.value = '2'
      input.dispatchEvent(new Event('input', { bubbles: true }))
      await settle()
    }
    const urls = spy.mock.calls.map((call) => String(call[0]))
    expect(urls.some((url) => url.includes('window_index=2'))).toBe(true)
  })

  it('never calls a write endpoint', async () => {
    const spy = mockFetch()
    render(CreditRelationshipsPanel as never, {
      runId: 'run-1',
      selection: emptyResearchSelection({
        runId: 'run-1',
        view: 'overview',
      }),
    })
    await settle()
    for (const call of spy.mock.calls) {
      const init = call[1] as RequestInit | undefined
      expect(init?.method ?? 'GET').toBe('GET')
    }
  })
})
