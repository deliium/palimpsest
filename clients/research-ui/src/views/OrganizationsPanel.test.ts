import { afterEach, describe, expect, it, vi } from 'vitest'
import { emptyResearchSelection } from '../research/selection'
import { flushSync, render } from '../test/mount'
import OrganizationsPanel from './OrganizationsPanel.svelte'

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
  publication_id: 'org-edge-0123456789abcdef',
  schema_version: 'organization-snapshot-v1',
  generated_tick: 9,
  candidate_count: 1,
  edge_count: 1,
  window_count: 2,
  coverage: { observed: 4, expected: 7, ratio: 0.57 },
  provenance_code: 'ok',
}

const candidates = {
  publication_id: 'org-edge-0123456789abcdef',
  items: [
    {
      organization_id: 'org-0123456789abcdef',
      creation_tick: 0,
      first_tick: 0,
      last_tick: 9,
      status: 'recognized',
      temporal_scope: 'ongoing',
      self_identified: true,
      member_count: 3,
      role_count: 1,
      goal_count: 1,
      resource_count: 0,
      procedure_count: 0,
      record_count: 1,
      commitment_count: 0,
      identity_count: 1,
      structural_channel_count: 4,
      window_indexes: [0],
    },
  ],
  next_cursor: null,
  truncated: false,
}

const lineage = {
  publication_id: 'org-edge-0123456789abcdef',
  items: [
    {
      kind: 'emerged',
      tick: 0,
      from_id: null,
      to_id: 'org-0123456789abcdef',
      jaccard: null,
      containment: null,
    },
  ],
  next_cursor: null,
  truncated: false,
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
      if (url.includes('/organizations/lineage')) {
        return json(lineage)
      }
      if (url.includes('/organizations/candidates')) {
        return json(candidates)
      }
      if (url.includes('/organizations')) {
        return json(summary)
      }
      return json({}, 404)
    }),
  )
}

afterEach(() => vi.unstubAllGlobals())

describe('organization panel', () => {
  it('renders summary, candidates, and lineage', async () => {
    stubFetch()
    const view = render(OrganizationsPanel as never, {
      runId: 'run-1',
      selection: emptyResearchSelection(),
    })
    await settle()

    const text = view.target.textContent ?? ''
    expect(text).toContain('Organization candidates')
    expect(text).toContain('org-0123456789abcdef')
    expect(text).toContain('recognized')
    expect(text).toContain('emerged')
  })

  it('shows the disabled state without inventing data', async () => {
    stubFetch((url) =>
      url.includes('/organizations')
        ? json({ code: 'organization_disabled' }, 503)
        : null,
    )
    const view = render(OrganizationsPanel as never, {
      runId: 'run-1',
      selection: emptyResearchSelection(),
    })
    await settle()

    const text = view.target.textContent ?? ''
    expect(text).toContain('disabled')
    expect(text).not.toContain('org-0123456789abcdef')
  })

  it('shows an explicit empty state', async () => {
    stubFetch((url) => {
      if (url.includes('/organizations/candidates')) {
        return json({ publication_id: 'x', items: [], next_cursor: null, truncated: false })
      }
      if (url.includes('/organizations/lineage')) {
        return json({ publication_id: 'x', items: [], next_cursor: null, truncated: false })
      }
      return null
    })
    const view = render(OrganizationsPanel as never, {
      runId: 'run-1',
      selection: emptyResearchSelection(),
    })
    await settle()

    expect(view.target.textContent ?? '').toContain('No published organization snapshot')
  })

  it('uses GET-only requests', async () => {
    stubFetch()
    const view = render(OrganizationsPanel as never, {
      runId: 'run-1',
      selection: emptyResearchSelection(),
    })
    await settle()
    const calls = (globalThis.fetch as unknown as { mock: { calls: unknown[][] } }).mock
      .calls
    for (const call of calls) {
      const init = call[1] as RequestInit | undefined
      expect(init?.method ?? 'GET').toBe('GET')
    }
  })
})
