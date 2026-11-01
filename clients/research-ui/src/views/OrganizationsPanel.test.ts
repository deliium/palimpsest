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
  schema_version: 'organization-snapshot-v2',
  generated_tick: 9,
  candidate_count: 1,
  edge_count: 1,
  window_count: 2,
  coverage: { observed: 4, expected: 7, ratio: 0.57 },
  provenance_code: 'ok',
  operation_count: 2,
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
      operation_count: 2,
      contested_operation_count: 1,
    },
  ],
  next_cursor: null,
  truncated: false,
}


const operations = {
  publication_id: 'org-edge-0123456789abcdef',
  items: [
    {
      operation_id: 'orgop-0000000000000001',
      domain: 'resource_control',
      act: 'authorize_control',
      stance: 'recognized',
      authority_basis: 'role_belief',
      provenance_code: 'role_authorized',
      outcome: 'observed',
      command_kind: 'give',
      target_kind: 'anchor',
      anchor_kind: 'item',
      anchor_id: 'item-1',
      tick: 3,
      first_tick: 1,
      last_tick: 9,
      support_count: 1,
      contest_count: 0,
      resolved: true,
    },
    {
      operation_id: 'orgop-0000000000000002',
      domain: 'storage',
      act: 'authorize_control',
      stance: 'disputed',
      authority_basis: 'unknown',
      provenance_code: 'contested',
      outcome: 'observed',
      command_kind: 'none',
      target_kind: 'anchor',
      anchor_kind: 'repository',
      anchor_id: 'repository-beta',
      tick: 4,
      first_tick: 2,
      last_tick: 9,
      support_count: 2,
      contest_count: 1,
      resolved: true,
    },
  ],
  next_cursor: null,
  truncated: false,
}

const candidateDetail = {
  ...candidates.items[0],
  members: [],
  structure: [],
  operations: operations.items,
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
      if (url.includes('/organizations/candidates/')) {
        return json(candidateDetail)
      }
      if (url.includes('/organizations/candidates')) {
        return json(candidates)
      }
      if (url.includes('/organizations/operations')) {
        return json(operations)
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
    expect(text).toContain('orgop-0000000000000001')
    expect(text).toContain('resource_control')
    expect(text).toContain('storage')
    expect(text).toContain('contested')
  })

  it('narrows the operation table by domain', async () => {
    stubFetch()
    const view = render(OrganizationsPanel as never, {
      runId: 'run-1',
      selection: emptyResearchSelection(),
    })
    await settle()
    const select = view.target.querySelector(
      'select.operation-domain',
    ) as HTMLSelectElement | null
    expect(select).not.toBeNull()
    select!.value = 'storage'
    select!.dispatchEvent(new Event('change', { bubbles: true }))
    await settle()
    const rows = view.target.querySelectorAll('table.operations tbody tr')
    expect(rows.length).toBe(1)
    expect(rows[0].textContent ?? '').toContain('orgop-0000000000000002')
  })

  it('renders candidate detail operations after selection', async () => {
    stubFetch()
    const view = render(OrganizationsPanel as never, {
      runId: 'run-1',
      selection: emptyResearchSelection(),
    })
    await settle()
    const button = view.target.querySelector('tbody button') as HTMLButtonElement
    button.click()
    await settle()
    const text = view.target.textContent ?? ''
    expect(text).toContain('Operations')
    expect(text).toContain('orgop-0000000000000001')
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
      if (url.includes('/organizations/operations')) {
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
