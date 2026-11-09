import { afterEach, describe, expect, it, vi } from 'vitest'
import { emptyResearchSelection } from '../research/selection'
import { flushSync, render } from '../test/mount'
import InterSocietyRelationsPanel from './InterSocietyRelationsPanel.svelte'

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
  publication_id: 'isr-pub-' + 'a'.repeat(32),
  digest: 'a'.repeat(64),
  schema_version: 'inter-society-relations-snapshot-v1',
  pair_count: 1,
  window_count: 1,
  series_point_count: 1,
  comparison_count: 0,
  coverage: 'partial',
}

const panel = {
  domain: 'exchange',
  event_count: 2,
  availability: 'present',
  coverage_observed: 2,
  coverage_expected: 2,
  values: { availability: 'present' },
}

const pair = {
  pair_id: 'isr-' + 'b'.repeat(16),
  society_a: 'msoc-' + 'c'.repeat(16),
  society_b: 'msoc-' + 'd'.repeat(16),
  window_tick: 32,
  status: 'partial',
  overlap_member_count: 0,
  panels: [panel],
}

const seriesPoint = {
  pair_id: pair.pair_id,
  window_index: 1,
  window_start_tick: 32,
  window_end_tick: 63,
  panels: [panel],
}

function stubFetch(override?: (path: string) => Response | null): void {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const path = new URL(String(input), 'http://local.test').pathname
      const custom = override?.(path) ?? null
      if (custom !== null) return custom
      if (path.endsWith('/inter-society-relations')) return json(summary)
      if (path.endsWith('/inter-society-relations/pairs')) {
        return json({ items: [pair], next_cursor: null })
      }
      if (path.endsWith('/inter-society-relations/windows')) {
        return json({ items: [seriesPoint], next_cursor: null })
      }
      if (path.includes('/comparison')) {
        return json({
          left_pair_id: pair.pair_id,
          right_pair_id: pair.pair_id,
          left_window_tick: 32,
          right_window_tick: 32,
          domain_deltas: [
            {
              domain: 'exchange',
              count_delta: 0,
              left_availability: 'present',
              right_availability: 'present',
            },
          ],
        })
      }
      return json({ code: 'not_found' }, 404)
    }),
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('InterSocietyRelationsPanel', () => {
  it('renders domain panels without score chrome', async () => {
    stubFetch()
    const view = render(InterSocietyRelationsPanel as never, {
      runId: 'run-1',
      selection: emptyResearchSelection(),
    })
    await settle()
    const text = (view.target.textContent ?? '').toLowerCase()
    expect(text).toContain('inter-society relations')
    expect(text).toContain('society pairs')
    expect(text).toContain('window series')
    expect(text).toContain('pair comparison')
    expect(text).toContain('exchange')
    expect(text).not.toContain('civilization relationship score')
    expect(text).not.toContain('alliance score')
    expect(text).not.toContain('trust score')
  })

  it('maps disabled status to unavailable', async () => {
    stubFetch(() =>
      json({ code: 'inter_society_relations_disabled' }, 503),
    )
    const view = render(InterSocietyRelationsPanel as never, {
      runId: 'run-1',
      selection: emptyResearchSelection(),
    })
    await settle()
    expect(view.target.textContent ?? '').toContain('disabled')
  })
})
