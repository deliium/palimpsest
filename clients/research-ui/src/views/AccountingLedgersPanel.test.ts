import { afterEach, describe, expect, it, vi } from 'vitest'
import { emptyResearchSelection } from '../research/selection'
import { flushSync, render } from '../test/mount'
import AccountingLedgersPanel from './AccountingLedgersPanel.svelte'

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
  publication_id: 'acct-pub-0000000000000000',
  digest: 'sha256:' + 'a'.repeat(64),
  schema_version: 'accounting-ledgers-snapshot-v1',
  entry_count: 1,
  record_count: 1,
  condition_count: 1,
  flow_count: 1,
  counterparty_count: 1,
  alignment_count: 1,
  window_count: 1,
  entry_coverage: 'complete',
  record_coverage: 'complete',
  alignment_coverage: 'complete',
  condition_coverage: 'complete',
  flow_coverage: 'complete',
  counterparty_coverage: 'complete',
  truncated: false,
}

const entry = {
  entry_token: 'acce-0000000000000000',
  window_index: 0,
  record_token: 'accrec-0000000000000000',
  entry_kind: 'exchange',
  direction: 'inflow',
  item_kind: 'food',
  quantity: 2,
  assessment: 'consistent',
  confidence_milli: 700,
  first_tick: 0,
  last_tick: 1,
}
const record = {
  record_token: 'accrec-0000000000000000',
  window_index: 0,
  record_genre: 'agreement',
  observed_integrity: 'intact',
  content_revision: 0,
  author_token: 'body-a',
  tick: 1,
  event_ordinal: 0,
  copy_generation: 0,
  tombstoned: false,
}
const condition = {
  condition: 'consistent',
  window_index: 0,
  record_count: 1,
  share_milli: 1000,
  availability: 'available',
}
const flow = {
  flow_token: 'exchange-inflow',
  window_index: 0,
  entry_kind: 'exchange',
  direction: 'inflow',
  event_count: 1,
  quantity_sum: 2,
  owner_count: 1,
  counterparty_count: 1,
}
const counterparty = {
  counterparty_token: 'accpeer-0000000000000000',
  window_index: 0,
  entry_count: 1,
  kinds: ['exchange'],
  first_tick: 0,
  last_tick: 1,
}
const alignment = {
  alignment_token: 'acca-0000000000000000',
  window_index: 0,
  entry_token: 'acce-0000000000000000',
  alignment: 'consistent',
  gap_milli: 0,
  record_token: 'accrec-0000000000000000',
}

function page<T>(rows: T[]) {
  return {
    run_id: 'run-1',
    publication_id: 'acct-pub-0000000000000000',
    window_index: 0,
    rows,
    next_cursor: null,
    coverage: 'complete',
  }
}

function installFetch(handler: (url: string) => Response): void {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => handler(String(input))),
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('AccountingLedgersPanel', () => {
  it('renders every family and the belief disclaimer', async () => {
    installFetch((url) => {
      if (url.endsWith('/accounting-ledgers')) return json(summary)
      if (url.includes('/entries')) return json(page([entry]))
      if (url.includes('/records')) return json(page([record]))
      if (url.includes('/conditions')) return json(page([condition]))
      if (url.includes('/flows')) return json(page([flow]))
      if (url.includes('/counterparties')) return json(page([counterparty]))
      if (url.includes('/alignment')) return json(page([alignment]))
      return json({}, 404)
    })
    const view = render(AccountingLedgersPanel as never, {
      runId: 'run-1',
      selection: emptyResearchSelection({
        runId: 'run-1',
        view: 'accounting-ledgers',
      }),
    })
    await settle()
    const text = view.target.textContent ?? ''
    expect(text).toContain('Accounting entries are owner beliefs')
    expect(text).toContain('Entries')
    expect(text).toContain('Records')
    expect(text).toContain('Conditions')
    expect(text).toContain('Flows')
    expect(text).toContain('Counterparties')
    expect(text).toContain('Alignment')
    expect(text.toLowerCase()).not.toContain('net worth')
    expect(text.toLowerCase()).not.toContain('solvency')
  })

  it('renders the disabled state', async () => {
    installFetch(() => json({ detail: 'accounting_ledgers_disabled' }, 503))
    const view = render(AccountingLedgersPanel as never, {
      runId: 'run-1',
      selection: emptyResearchSelection({
        runId: 'run-1',
        view: 'accounting-ledgers',
      }),
    })
    await settle()
    expect(view.target.textContent).toContain('disabled')
  })

  it('renders the empty and generic error states', async () => {
    installFetch((url) => {
      if (url.endsWith('/accounting-ledgers')) return json(summary)
      return json(page([]))
    })
    const empty = render(AccountingLedgersPanel as never, {
      runId: 'run-1',
      selection: emptyResearchSelection({
        runId: 'run-1',
        view: 'accounting-ledgers',
      }),
    })
    await settle()
    expect(empty.target.textContent).toContain('No accounting ledgers')
    vi.unstubAllGlobals()
    installFetch(() => json({ detail: 'server_error' }, 500))
    const failed = render(AccountingLedgersPanel as never, {
      runId: 'run-1',
      selection: emptyResearchSelection({
        runId: 'run-1',
        view: 'accounting-ledgers',
      }),
    })
    await settle()
    expect(failed.target.textContent).toContain('unavailable')
  })

  it('propagates the window filter and uses GET only', async () => {
    const calls: { url: string; method: string }[] = []
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input)
        calls.push({ url, method: init?.method ?? 'GET' })
        if (url.endsWith('/accounting-ledgers')) return json(summary)
        return json(page([]))
      }),
    )
    const view = render(AccountingLedgersPanel as never, {
      runId: 'run-1',
      selection: emptyResearchSelection({
        runId: 'run-1',
        view: 'accounting-ledgers',
      }),
    })
    await settle()
    const input = view.target.querySelector(
      'input[aria-label="Window filter"]',
    ) as HTMLInputElement
    input.value = '3'
    input.dispatchEvent(new Event('input', { bubbles: true }))
    await settle()
    expect(calls.every((call) => call.method === 'GET')).toBe(true)
    expect(calls.some((call) => call.url.includes('window_index=3'))).toBe(true)
  })
})
