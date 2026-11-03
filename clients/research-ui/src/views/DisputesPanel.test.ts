import { afterEach, describe, expect, it, vi } from 'vitest'
import { emptyResearchSelection } from '../research/selection'
import { flushSync, render } from '../test/mount'
import DisputesPanel from './DisputesPanel.svelte'

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

const coverage = { observed: 1, expected: 2, ratio: 0.5, note: 'partial' }

const summary = {
  run_id: 'run-1',
  publication_id: 'disp-pub-0123456789abcdef',
  schema_version: 'dispute-resolution-snapshot-v1',
  generated_tick: 9,
  candidate_count: 2,
  case_count: 1,
  claim_count: 2,
  counterclaim_count: 1,
  testimony_count: 1,
  evidence_count: 1,
  resolution_count: 1,
  accepted_count: 1,
  rejected_count: 0,
  edge_count: 1,
  window_count: 1,
  coverage,
  provenance_code: 'ok',
  snapshot_digest: 'a'.repeat(64),
}

const candidates = {
  items: [
    {
      candidate_id: 'disp-0000000000000001',
      kind: 'contested_debt',
      subject_token: 'subject-1',
      party_count: 2,
      owner_count: 2,
      case_count: 1,
      claim_count: 2,
      counterclaim_count: 1,
      testimony_count: 1,
      evidence_count: 1,
      resolution_count: 1,
      disagreement_count: 1,
      status: 'contested',
      first_tick: 2,
      last_tick: 6,
      coverage,
    },
    {
      candidate_id: 'disp-0000000000000002',
      kind: 'broken_promise',
      subject_token: 'subject-2',
      party_count: 2,
      owner_count: 1,
      case_count: 0,
      claim_count: 0,
      counterclaim_count: 0,
      testimony_count: 0,
      evidence_count: 0,
      resolution_count: 0,
      disagreement_count: 0,
      status: 'emerging',
      first_tick: 5,
      last_tick: 5,
      coverage,
    },
  ],
  next_cursor: null,
  truncated: false,
}

const claims = {
  items: [
    {
      claim_id: 'dcl-0000000000000001',
      case_ref: 'b'.repeat(64),
      claimant_id: 'agent-1',
      respondent_id: 'agent-2',
      role: 'claim',
      claim_kind: 'debt_owed',
      polarity: 'affirm',
      subject_token: 'subject-1',
      counters_claim_ref: null,
      evidence_count: 1,
      first_tick: 2,
      last_tick: 3,
      candidate_id: 'disp-0000000000000001',
    },
    {
      claim_id: 'dcl-0000000000000002',
      case_ref: 'b'.repeat(64),
      claimant_id: 'agent-2',
      respondent_id: 'agent-1',
      role: 'counterclaim',
      claim_kind: 'debt_owed',
      polarity: 'deny',
      subject_token: 'subject-1',
      counters_claim_ref: 'dcl-0000000000000001',
      evidence_count: 0,
      first_tick: 4,
      last_tick: 4,
      candidate_id: 'disp-0000000000000001',
    },
  ],
  next_cursor: null,
  truncated: false,
}

const resolutions = {
  items: [
    {
      resolution_id: 'drs-0000000000000001',
      resolution_ref: 'c'.repeat(64),
      case_ref: 'b'.repeat(64),
      proposer_id: 'agent-1',
      source: 'mediator',
      terms_digest: 'd'.repeat(64),
      status: 'apparently_accepted',
      first_tick: 5,
      last_tick: 6,
      expires_tick: null,
      accepted_party_count: 2,
      rejected_party_count: 0,
      candidate_id: 'disp-0000000000000001',
    },
  ],
  next_cursor: null,
  truncated: false,
}

const detail = {
  candidate: candidates.items[0],
  coverage,
  testimony: [
    {
      testimony_id: 'dts-0000000000000001',
      case_ref: 'b'.repeat(64),
      claim_id: 'dcl-0000000000000001',
      speaker_id: 'agent-1',
      channel: 'direct',
      root_token: 'root-1',
      independently_evidenced: true,
      tick: 3,
    },
  ],
  evidence: [
    {
      evidence_id: 'dev-0000000000000001',
      case_ref: 'b'.repeat(64),
      claim_id: 'dcl-0000000000000001',
      channel: 'observed',
      reference_kind: 'observed_occurrence',
      reference_token: 'e'.repeat(64),
      tick: 3,
      independently_evidenced: true,
    },
  ],
  rule_references: [
    {
      rule_reference_id: 'drf-0000000000000001',
      case_ref: 'b'.repeat(64),
      claim_ref: 'dcl-0000000000000001',
      system_token: 'custom',
      rule_token: 'payment-rule',
      version_number: 1,
      applicability: 'applies',
      interpretation: 'literal',
      status: 'resolved',
    },
  ],
  authority_references: [
    {
      authority_reference_id: 'dar-0000000000000001',
      case_ref: 'b'.repeat(64),
      authority_kind: 'office',
      reference_token: 'office-token-1',
      strength: 0.6,
      uncertainty: 0.4,
      dissenting: false,
    },
  ],
  mediation_references: [
    {
      mediation_reference_id: 'dmr-0000000000000001',
      case_ref: 'b'.repeat(64),
      mediation_case_token: 'mediation-case-1',
      recommendation_token: 'recommendation-1',
      response_token: 'response-1',
      outcome_token: null,
      link_status: 'linked',
    },
  ],
  responses: [
    {
      response_id: 'drp-0000000000000001',
      resolution_ref: 'c'.repeat(64),
      party_id: 'agent-2',
      kind: 'accept',
      tick: 6,
      terms_digest: 'd'.repeat(64),
      active: true,
    },
  ],
  truncated: false,
}

const lineage = {
  items: [
    {
      edge_id: 'dse-0000000000000001',
      source: 'disp-0000000000000001',
      target: 'disp-0000000000000002',
      kind: 'emerged',
      tick: 5,
    },
  ],
  next_cursor: null,
  truncated: false,
}

type Override = (path: string) => Response | null

function stubFetch(override?: Override): void {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const path = new URL(String(input), 'http://local.test').pathname
      const custom = override?.(path) ?? null
      if (custom !== null) return custom
      if (path.endsWith('/disputes')) return json(summary)
      if (path.endsWith('/disputes/candidates')) return json(candidates)
      if (path.endsWith('/disputes/lineage')) return json(lineage)
      if (path.includes('/disputes/candidates/') && path.endsWith('/claims')) {
        return json(claims)
      }
      if (
        path.includes('/disputes/candidates/') &&
        path.endsWith('/resolutions')
      ) {
        return json(resolutions)
      }
      if (path.includes('/disputes/candidates/')) return json(detail)
      return json({ code: 'not_found' }, 404)
    }),
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('DisputesPanel', () => {
  it('renders claims and counterclaims separately after selection', async () => {
    stubFetch()
    const view = render(DisputesPanel as never, {
      runId: 'run-1',
      selection: emptyResearchSelection(),
    })
    await settle()
    expect(view.target.textContent).toContain('disp-0000000000000001')

    const button = view.target.querySelector('tbody button') as HTMLButtonElement
    button.click()
    await settle()
    const text = view.target.textContent ?? ''
    expect(text).toContain('agent-1')
    expect(text).toContain('agent-2')
    expect(text).toContain('counterclaim')
    const rows = view.target.querySelectorAll('table.claims tbody tr')
    expect(rows).toHaveLength(2)
    expect(rows[0]?.querySelectorAll('td')[1]?.textContent).toBe('claim')
    expect(rows[1]?.querySelectorAll('td')[1]?.textContent).toBe('counterclaim')
  })

  it('renders declared acceptance without judgment labels', async () => {
    stubFetch()
    const view = render(DisputesPanel as never, {
      runId: 'run-1',
      selection: emptyResearchSelection(),
    })
    await settle()
    const button = view.target.querySelector('tbody button') as HTMLButtonElement
    button.click()
    await settle()
    const text = view.target.textContent ?? ''
    expect(text).toContain('declared accept')
    expect(text).toContain('apparently accepted')
    for (const forbidden of [
      'verdict',
      'guilty',
      'liable',
      'winner',
      'true owner',
      'binding',
    ]) {
      expect(text.toLowerCase()).not.toContain(forbidden)
    }
  })

  it('maps dispute_disabled to unavailable', async () => {
    stubFetch((path) =>
      path.endsWith('/disputes') ? json({ code: 'dispute_disabled' }, 503) : null,
    )
    const view = render(DisputesPanel as never, {
      runId: 'run-1',
      selection: emptyResearchSelection(),
    })
    await settle()
    const text = view.target.textContent ?? ''
    expect(text).toContain('disabled')
    expect(text).not.toContain('disp-0000000000000001')
  })

  it('shows an empty state when no candidates are published', async () => {
    stubFetch((path) =>
      path.endsWith('/disputes/candidates')
        ? json({ items: [], next_cursor: null, truncated: false })
        : null,
    )
    const view = render(DisputesPanel as never, {
      runId: 'run-1',
      selection: emptyResearchSelection(),
    })
    await settle()
    expect(view.target.textContent).toContain(
      'No published dispute-resolution snapshot',
    )
  })

  it('loads detail, claims, and resolutions on candidate selection', async () => {
    stubFetch()
    const view = render(DisputesPanel as never, {
      runId: 'run-1',
      selection: emptyResearchSelection(),
    })
    await settle()
    const button = view.target.querySelector('tbody button') as HTMLButtonElement
    button.click()
    await settle()

    const paths = (
      globalThis.fetch as unknown as { mock: { calls: unknown[][] } }
    ).mock.calls.map((call) =>
      new URL(String(call[0]), 'http://local.test').pathname,
    )
    expect(
      paths.some((path) =>
        path.endsWith('/candidates/disp-0000000000000001'),
      ),
    ).toBe(true)
    expect(paths.some((path) => path.endsWith('/claims'))).toBe(true)
    expect(paths.some((path) => path.endsWith('/resolutions'))).toBe(true)
  })

  it('uses GET-only requests', async () => {
    stubFetch()
    render(DisputesPanel as never, {
      runId: 'run-1',
      selection: emptyResearchSelection(),
    })
    await settle()
    const calls = (globalThis.fetch as unknown as { mock: { calls: unknown[][] } })
      .mock.calls
    for (const call of calls) {
      const init = call[1] as RequestInit | undefined
      expect(init?.method ?? 'GET').toBe('GET')
    }
  })
})
