import { afterEach, describe, expect, it, vi } from 'vitest'
import { emptyResearchSelection } from '../research/selection'
import { flushSync, render } from '../test/mount'
import SocialMobilityPanel from './SocialMobilityPanel.svelte'

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
  publication_id: 'socmob-pub-0000000000000000',
  digest: 'sha256:' + 'a'.repeat(64),
  schema_version: 'social-mobility-snapshot-v1',
  domain_row_count: 1,
  generation_row_count: 1,
  lag_row_count: 1,
  window_count: 1,
  owner_count: 16,
  generation_count: 2,
  genealogy_edge_count: 8,
  pair_count: 8,
  resolved_pair_count: 8,
  unresolved_pair_count: 0,
  domain_available_count: 1,
  coverage: 'complete',
  evidence_coverage: 'complete',
  domain_coverage: 'complete',
  generation_coverage: 'complete',
  truncated: false,
}

const domain = {
  window_index: 0,
  window_tick: 31,
  domain: 'resources',
  measure: 'observed_resource_item_count',
  pair_count: 8,
  resolved_pair_count: 8,
  rank_correlation_milli: 500,
  same_bin_share_milli: 600,
  upward_share_milli: 250,
  downward_share_milli: 150,
  mean_absolute_rank_change_milli: 200,
  persistence_direction: 'persistent',
  coverage: 'complete',
  availability: 'available',
}

const generation = {
  window_index: 0,
  window_tick: 31,
  generation_index: 1,
  owner_count: 8,
  pair_count: 8,
  comparable: true,
  same_bin_share_milli: 600,
  upward_share_milli: 250,
  downward_share_milli: 150,
  coverage: 'complete',
  availability: 'available',
}

const lag = {
  window_index: 0,
  window_tick: 31,
  generation_lag: 1,
  pair_count: 8,
  comparable: true,
  same_bin_share_milli: 600,
  upward_share_milli: 250,
  downward_share_milli: 150,
  coverage: 'complete',
  availability: 'available',
}

const coverage = {
  window_index: 0,
  window_tick: 31,
  generation_count: 2,
  owner_count: 16,
  genealogy_edge_count: 8,
  pair_count: 8,
  resolved_pair_count: 8,
  unresolved_pair_count: 0,
  domain_available_count: 1,
  truncated: false,
  coverage: 'complete',
}

function page<T>(rows: T[]) {
  return {
    run_id: 'run-1',
    publication_id: 'socmob-pub-0000000000000000',
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

function selection() {
  return emptyResearchSelection({ runId: 'run-1', view: 'social-mobility' })
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('SocialMobilityPanel', () => {
  it('renders domains, generations, lags, and coverage', async () => {
    installFetch((url) => {
      if (url.endsWith('/social-mobility')) return json(summary)
      if (url.includes('/domains')) return json(page([domain]))
      if (url.includes('/generations')) return json(page([generation, lag]))
      if (url.includes('/coverage')) return json(page([coverage]))
      return json({}, 404)
    })
    const view = render(SocialMobilityPanel as never, {
      runId: 'run-1',
      selection: selection(),
    })
    await settle()
    const text = view.target.textContent ?? ''
    expect(text).toContain('Domains')
    expect(text).toContain('Generations')
    expect(text).toContain('Generation lags')
    expect(text).toContain('Coverage')
    expect(text).toContain('persistent')
    expect(text.toLowerCase()).not.toContain('best')
    expect(text.toLowerCase()).not.toContain('worst')
    expect(text.toLowerCase()).not.toContain('class')
  })

  it('renders unavailable for the disabled gate', async () => {
    installFetch(() => json({ detail: 'social_mobility_disabled' }, 503))
    const view = render(SocialMobilityPanel as never, {
      runId: 'run-1',
      selection: selection(),
    })
    await settle()
    expect(view.target.textContent).toContain('unavailable')
  })

  it('renders empty and generic error states', async () => {
    installFetch((url) => {
      if (url.endsWith('/social-mobility')) return json(summary)
      return json(page([]))
    })
    const empty = render(SocialMobilityPanel as never, {
      runId: 'run-1',
      selection: selection(),
    })
    await settle()
    expect(empty.target.textContent).toContain('No social-mobility evidence')
    vi.unstubAllGlobals()
    installFetch(() => json({ detail: 'server_error' }, 500))
    const failed = render(SocialMobilityPanel as never, {
      runId: 'run-1',
      selection: selection(),
    })
    await settle()
    expect(failed.target.textContent).toContain('error')
  })

  it('renders insufficient samples literally and uses GET only', async () => {
    const calls: { url: string; method: string }[] = []
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input)
        calls.push({ url, method: init?.method ?? 'GET' })
        if (url.endsWith('/social-mobility')) return json(summary)
        if (url.includes('/domains')) {
          return json(
            page([{ ...domain, availability: 'insufficient_samples' }]),
          )
        }
        return json(page([]))
      }),
    )
    const view = render(SocialMobilityPanel as never, {
      runId: 'run-1',
      selection: selection(),
    })
    await settle()
    expect(view.target.textContent).toContain('insufficient samples')
    expect(calls.every((call) => call.method === 'GET')).toBe(true)
  })
})
