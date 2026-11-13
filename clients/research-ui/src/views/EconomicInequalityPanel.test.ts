import { afterEach, describe, expect, it, vi } from 'vitest'
import { emptyResearchSelection } from '../research/selection'
import { flushSync, render } from '../test/mount'
import EconomicInequalityPanel from './EconomicInequalityPanel.svelte'

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
  publication_id: 'econ-pub-0000000000000000',
  digest: 'sha256:' + 'a'.repeat(64),
  schema_version: 'economic-inequality-snapshot-v1',
  dimension_row_count: 1,
  cohort_row_count: 1,
  society_row_count: 1,
  window_count: 1,
  owner_count: 8,
  observed_owner_count: 8,
  overlap_member_count: 0,
  coverage: 'complete',
  evidence_coverage: 'complete',
  dimension_coverage: 'complete',
  comparison_coverage: 'complete',
  truncated: false,
}

const dimension = {
  dimension: 'resource_possession',
  measure: 'observed_item_count',
  window_index: 0,
  window_tick: 31,
  owner_count: 8,
  observed_owner_count: 8,
  minimum: 0,
  p25: 1,
  median: 2,
  p75: 3,
  maximum: 4,
  iqr: 2,
  dispersion: 4,
  bin_shares_milli: [250, 250, 250, 250, 0],
  gini_milli: 200,
  theil_t_milli: 100,
  atkinson_eps_1_milli: 80,
  top_share_milli: 300,
  availability: 'available',
  coverage: 'complete',
}

const cohort = {
  cohort_token: 'eic-0000000000000001',
  generation_index: 0,
  window_index: 0,
  owner_count: 8,
  comparable: true,
  gini_milli: 200,
  median_milli: 2,
  iqr_milli: 1,
  trend: 'stable',
  availability: 'available',
}

const society = {
  society_token: 'eis-0000000000000001',
  window_index: 0,
  owner_count: 8,
  comparable: true,
  gini_milli: 200,
  median_milli: 2,
  iqr_milli: 1,
  trend: 'stable',
  availability: 'available',
}

function page<T>(rows: T[]) {
  return {
    run_id: 'run-1',
    publication_id: 'econ-pub-0000000000000000',
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

describe('EconomicInequalityPanel', () => {
  it('renders dimensions, cohorts, societies, and the disclaimer', async () => {
    installFetch((url) => {
      if (url.endsWith('/economic-inequality')) return json(summary)
      if (url.includes('/dimensions')) return json(page([dimension]))
      if (url.includes('/cohorts')) return json(page([cohort]))
      if (url.includes('/societies')) return json(page([society]))
      return json({}, 404)
    })
    const view = render(EconomicInequalityPanel as never, {
      runId: 'run-1',
      selection: emptyResearchSelection({
        runId: 'run-1',
        view: 'economic-inequality',
      }),
    })
    await settle()
    const text = view.target.textContent ?? ''
    expect(text).toContain('descriptive distributions')
    expect(text).toContain('Dimensions')
    expect(text).toContain('Cohorts')
    expect(text).toContain('Societies')
    expect(text.toLowerCase()).not.toContain('net worth')
    expect(text.toLowerCase()).not.toContain('best')
    expect(text.toLowerCase()).not.toContain('worst')
  })

  it('renders the disabled state', async () => {
    installFetch(() => json({ detail: 'economic_inequality_disabled' }, 503))
    const view = render(EconomicInequalityPanel as never, {
      runId: 'run-1',
      selection: emptyResearchSelection({
        runId: 'run-1',
        view: 'economic-inequality',
      }),
    })
    await settle()
    expect(view.target.textContent).toContain('disabled')
  })

  it('renders empty and generic error states', async () => {
    installFetch((url) => {
      if (url.endsWith('/economic-inequality')) return json(summary)
      return json(page([]))
    })
    const empty = render(EconomicInequalityPanel as never, {
      runId: 'run-1',
      selection: emptyResearchSelection({
        runId: 'run-1',
        view: 'economic-inequality',
      }),
    })
    await settle()
    expect(empty.target.textContent).toContain('No economic inequality')
    vi.unstubAllGlobals()
    installFetch(() => json({ detail: 'server_error' }, 500))
    const failed = render(EconomicInequalityPanel as never, {
      runId: 'run-1',
      selection: emptyResearchSelection({
        runId: 'run-1',
        view: 'economic-inequality',
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
        if (url.endsWith('/economic-inequality')) return json(summary)
        return json(page([]))
      }),
    )
    const view = render(EconomicInequalityPanel as never, {
      runId: 'run-1',
      selection: emptyResearchSelection({
        runId: 'run-1',
        view: 'economic-inequality',
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
