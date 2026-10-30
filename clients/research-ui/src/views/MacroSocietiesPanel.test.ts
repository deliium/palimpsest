import { afterEach, describe, expect, it, vi } from 'vitest'
import { emptyResearchSelection } from '../research/selection'
import { flushSync, render } from '../test/mount'
import MacroSocietiesPanel from './MacroSocietiesPanel.svelte'

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
  publication_id: 'msoc-edge-0123456789abcdef',
  snapshot_digest: 'a'.repeat(64),
  schema_version: 'macro-society-snapshot-v1',
  policy_version: 'macro-society-identity.v1',
  run_id: 'run-1',
  input_revision: 'rev-1',
  generated_tick: 9,
  window_count: 2,
  candidate_count: 1,
  edge_count: 2,
  coverage: { observed: 4, expected: 8, ratio: 0.5 },
  provenance_code: 'ok',
}

const candidates = {
  items: [
    {
      macro_society_id: 'msoc-0123456789abcdef',
      creation_tick: 0,
      first_tick: 0,
      last_tick: 9,
      status: 'contested',
      member_count: 4,
      lane_signature: ['culture', 'interaction'],
      overlap_person_count: 2,
    },
  ],
  next_cursor: null,
}

const lineage = {
  items: [
    {
      from_id: null,
      to_id: 'msoc-0123456789abcdef',
      kind: 'emerged',
      from_tick: 0,
      to_tick: 9,
      jaccard: null,
    },
  ],
  next_cursor: null,
}

function stubFetch(handler?: (url: string) => Response | null): void {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      const handled = handler?.(url)
      if (handled !== undefined && handled !== null) {
        return handled
      }
      if (url.includes('/macro-societies/lineage')) {
        return json(lineage)
      }
      if (url.includes('/macro-societies/candidates')) {
        return json(candidates)
      }
      if (url.includes('/macro-societies')) {
        return json(summary)
      }
      return json({}, 404)
    }),
  )
}

afterEach(() => vi.unstubAllGlobals())

describe('macro-society panel', () => {
  it('renders summary, candidates, overlap, and lineage', async () => {
    stubFetch()
    const view = render(MacroSocietiesPanel as never, {
      runId: 'run-1',
      selection: emptyResearchSelection(),
    })
    await settle()

    const text = view.target.textContent ?? ''
    expect(text).toContain('Macro-society candidates')
    expect(text).toContain('macro-society-identity.v1')
    expect(text).toContain('msoc-0123456789abcdef')
    expect(text).toContain('contested')
    expect(text).toContain('emerged')
    expect(text).toContain('culture, interaction')
  })

  it('shows the disabled state without inventing data', async () => {
    stubFetch((url) =>
      url.includes('/macro-societies')
        ? json({ code: 'macro_society_disabled' }, 503)
        : null,
    )
    const view = render(MacroSocietiesPanel as never, {
      runId: 'run-1',
      selection: emptyResearchSelection(),
    })
    await settle()

    const text = view.target.textContent ?? ''
    expect(text).toContain('disabled')
    expect(text).not.toContain('msoc-0123456789abcdef')
  })

  it('shows an explicit empty state', async () => {
    stubFetch((url) => {
      if (url.includes('/macro-societies/candidates')) {
        return json({ items: [], next_cursor: null })
      }
      if (url.includes('/macro-societies/lineage')) {
        return json({ items: [], next_cursor: null })
      }
      return null
    })
    const view = render(MacroSocietiesPanel as never, {
      runId: 'run-1',
      selection: emptyResearchSelection(),
    })
    await settle()

    expect(view.target.textContent ?? '').toContain('No published macro-society snapshot')
  })
})
