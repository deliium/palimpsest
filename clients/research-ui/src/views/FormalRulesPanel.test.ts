import { afterEach, describe, expect, it, vi } from 'vitest'
import { emptyResearchSelection } from '../research/selection'
import { flushSync, render } from '../test/mount'
import FormalRulesPanel from './FormalRulesPanel.svelte'

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
  publication_id: 'frule-pub-0123456789abcdef',
  schema_version: 'formal-rule-snapshot-v1',
  generated_tick: 9,
  candidate_count: 2,
  rule_count: 2,
  version_count: 2,
  window_count: 1,
  coverage: { observed: 1, expected: 1, partial: false },
  provenance_code: 'ok',
  snapshot_digest: 'a'.repeat(64),
}

const candidates = {
  items: [
    {
      candidate_id: 'frule-0000000000000001',
      status: 'contested',
      scope_kind: 'action',
      stage: 'documented',
      action_token: 'maintain',
      constraint_kinds: ['obligation'],
      authority_kinds: ['custom'],
      system_count: 1,
      rule_count: 1,
      version_count: 1,
      competing_candidate_ids: ['frule-0000000000000002'],
      first_tick: 0,
      last_tick: 9,
    },
    {
      candidate_id: 'frule-0000000000000002',
      status: 'contested',
      scope_kind: 'action',
      stage: 'norm',
      action_token: 'maintain',
      constraint_kinds: ['prohibition'],
      authority_kinds: ['office'],
      system_count: 1,
      rule_count: 1,
      version_count: 1,
      competing_candidate_ids: ['frule-0000000000000001'],
      first_tick: 0,
      last_tick: 9,
    },
  ],
  next_cursor: null,
  truncated: false,
}

const lineage = {
  items: [
    {
      edge_id: 'frule-edge-0000000000000001',
      source_candidate_id: 'frule-0000000000000001',
      target_candidate_id: 'frule-0000000000000002',
      kind: 'split',
      tick: 3,
      jaccard: 0.2,
      containment: 0.5,
    },
  ],
  next_cursor: null,
  truncated: false,
}

const detail = {
  candidate: candidates.items[0],
  coverage: summary.coverage,
}

const rules = {
  items: [
    {
      rule_id: 'frul-0000000000000001',
      candidate_id: 'frule-0000000000000001',
      stage: 'documented',
      constraint_kind: 'obligation',
      scope_kind: 'action',
      action_token: 'maintain',
      authority_kind: 'custom',
      recognition: 'contested',
      written_representation: {
        status: 'intact',
        artifact_present: true,
        artifact_revision: 1,
        repository_present: false,
      },
      sanction_kinds: ['criticism'],
      exception_count: 1,
      version_count: 1,
      latest_version: 1,
      proponent_count: 2,
      response_counts: [['follow', 1]],
    },
  ],
  next_cursor: null,
  truncated: false,
}

const versions = {
  items: [
    {
      version_id: 'fruv-0000000000000001',
      rule_id: 'frul-0000000000000001',
      version_number: 1,
      stage: 'documented',
      constraint_kind: 'obligation',
      scope_kind: 'action',
      scope_digest: 'b'.repeat(64),
      action_token: 'maintain',
      authority_kind: 'custom',
      recognition: 'contested',
      written_representation: {
        status: 'intact',
        artifact_present: true,
        artifact_revision: 1,
        repository_present: false,
      },
      sanction_kinds: ['criticism'],
      exception_count: 1,
      tick: 1,
      revision_kind: 'initial',
      supersedes_version_id: null,
    },
  ],
  next_cursor: null,
  truncated: false,
}

type Override = (url: string) => Response | null

function stubFetch(override?: Override): void {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      const custom = override?.(url) ?? null
      if (custom !== null) return custom
      if (url.endsWith('/formal-rules')) return json(summary)
      if (url.includes('/formal-rules/candidates/') && url.includes('/rules')) {
        return json(rules)
      }
      if (url.includes('/formal-rules/candidates/') && url.includes('/versions')) {
        return json(versions)
      }
      if (url.includes('/formal-rules/candidates/')) return json(detail)
      if (url.includes('/formal-rules/candidates')) return json(candidates)
      if (url.includes('/formal-rules/lineage')) return json(lineage)
      return json({ code: 'not_found' }, 404)
    }),
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('FormalRulesPanel', () => {
  it('renders summary, separate competing candidates, and declared responses', async () => {
    stubFetch()
    const view = render(FormalRulesPanel as never, {
      runId: 'run-1',
      selection: emptyResearchSelection(),
    })
    await settle()
    const text = view.target.textContent ?? ''
    expect(text).toContain('frule-0000000000000001')
    expect(text).toContain('frule-0000000000000002')
    expect(text).toContain('Declared responses, not objective compliance')
    expect(text).not.toContain('guilty')
    expect(text).not.toContain('violated')
  })

  it('renders rules and versions after selection', async () => {
    stubFetch()
    const view = render(FormalRulesPanel as never, {
      runId: 'run-1',
      selection: emptyResearchSelection(),
    })
    await settle()
    const button = view.target.querySelector('tbody button') as HTMLButtonElement
    button.click()
    await settle()
    const text = view.target.textContent ?? ''
    expect(text).toContain('frul-0000000000000001')
    expect(text).toContain('fruv-0000000000000001')
    expect(text).toContain('criticism')
  })

  it('shows the disabled state without inventing data', async () => {
    stubFetch((url) =>
      url.endsWith('/formal-rules')
        ? json({ code: 'formal_rule_disabled' }, 503)
        : null,
    )
    const view = render(FormalRulesPanel as never, {
      runId: 'run-1',
      selection: emptyResearchSelection(),
    })
    await settle()
    const text = view.target.textContent ?? ''
    expect(text).toContain('disabled')
    expect(text).not.toContain('frule-0000000000000001')
  })

  it('uses GET-only requests', async () => {
    stubFetch()
    render(FormalRulesPanel as never, {
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
