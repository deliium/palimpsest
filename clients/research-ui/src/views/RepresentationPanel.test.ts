import { afterEach, describe, expect, it, vi } from 'vitest'
import { emptyResearchSelection } from '../research/selection'
import { flushSync, render } from '../test/mount'
import RepresentationPanel from './RepresentationPanel.svelte'

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
  publication_id: 'drep-pub-0123456789abcdef',
  snapshot_digest: 'a'.repeat(64),
  generated_tick: 9,
  mandate_count: 1,
  position_count: 2,
  revocation_count: 1,
  conflict_count: 1,
  candidate_count: 1,
  lineage_edge_count: 1,
  owner_count: 1,
  coverage: 'partial',
  schema_version: 'delegation-representation-snapshot-v1',
}

const mandate = {
  mandate_id: 'rmd-0000000000000001',
  owner_token: '0'.repeat(16),
  principal_kind: 'agent',
  principal_token: '1'.repeat(16),
  representative_token: '2'.repeat(16),
  scope_kind: 'speak_for',
  scope_subject_token: 'border',
  duration_kind: 'until_revoked',
  start_tick: 1,
  end_tick: null,
  provenance: 'self_declared',
  status: 'contested',
  recognition_basis: 'none',
  support_roots: 1,
  opposition_roots: 1,
  confidence_band: 'mid',
  coverage: 'partial',
}

const mandates = { items: [mandate], next_cursor: null, truncated: false }
const positions = {
  items: [
    {
      position_id: 'rmp-0000000000000001',
      mandate_id: mandate.mandate_id,
      owner_token: '0'.repeat(16),
      actor_token: '3'.repeat(16),
      stance: 'oppose',
      provenance: 'communicated',
      tick: 2,
      active: true,
    },
  ],
  next_cursor: null,
  truncated: false,
}
const revocations = {
  items: [
    {
      revocation_id: 'rmv-0000000000000001',
      mandate_id: mandate.mandate_id,
      owner_token: '0'.repeat(16),
      actor_token: '4'.repeat(16),
      kind: 'principal_revoked',
      provenance: 'principal_declared',
      tick: 3,
      contested: true,
    },
  ],
  next_cursor: null,
  truncated: false,
}
const lineage = {
  items: [
    {
      edge_id: 'rep-edge-0000000000000001',
      from_candidate_id: 'rep-0000000000000001',
      to_candidate_id: 'rep-0000000000000001',
      kind: 'emerged',
      tick: 1,
    },
  ],
  next_cursor: null,
  truncated: false,
}

function stubFetch(override?: (path: string) => Response | null): void {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const path = new URL(String(input), 'http://local.test').pathname
      const custom = override?.(path) ?? null
      if (custom !== null) return custom
      if (path.endsWith('/representation')) return json(summary)
      if (path.endsWith('/representation/mandates')) return json(mandates)
      if (path.endsWith('/representation/lineage')) return json(lineage)
      if (path.endsWith('/positions')) return json(positions)
      if (path.endsWith('/revocations')) return json(revocations)
      if (path.includes('/representation/mandates/')) return json(mandate)
      return json({ code: 'not_found' }, 404)
    }),
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('RepresentationPanel', () => {
  it('renders summary, mandates, and explicit non-legitimacy chrome', async () => {
    stubFetch()
    const view = render(RepresentationPanel as never, {
      runId: 'run-1',
      selection: emptyResearchSelection(),
    })
    await settle()
    expect(view.target.textContent).toContain('Delegation and representation')
    expect(view.target.textContent).toContain('not legitimacy')
    expect(view.target.textContent).toContain('contested')
    const button = view.target.querySelector('button')
    ;(button as HTMLButtonElement).click()
    await settle()
    expect(view.target.textContent).toContain('Positions')
    expect(view.target.textContent).toContain('oppose')
    expect(view.target.textContent).toContain('Revocations')
  })

  it('renders the empty state', async () => {
    stubFetch((path) =>
      path.endsWith('/representation/mandates')
        ? json({ items: [], next_cursor: null, truncated: false })
        : null,
    )
    const view = render(RepresentationPanel as never, {
      runId: 'run-1',
      selection: emptyResearchSelection(),
    })
    await settle()
    expect(view.target.textContent).toContain('No representation was published')
  })

  it('maps the disabled code to unavailable', async () => {
    stubFetch(() => json({ code: 'representation_disabled' }, 503))
    const view = render(RepresentationPanel as never, {
      runId: 'run-1',
      selection: emptyResearchSelection(),
    })
    await settle()
    expect(view.target.textContent).toContain('unavailable')
  })

  it('renders the error state', async () => {
    stubFetch(() => json({ code: 'delegation_representation_not_found' }, 404))
    const view = render(RepresentationPanel as never, {
      runId: 'run-1',
      selection: emptyResearchSelection(),
    })
    await settle()
    expect(view.target.textContent).toContain('Representation read failed')
  })
})
