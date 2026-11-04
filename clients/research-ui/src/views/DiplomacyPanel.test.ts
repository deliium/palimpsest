import { afterEach, describe, expect, it, vi } from 'vitest'
import { emptyResearchSelection } from '../research/selection'
import { flushSync, render } from '../test/mount'
import DiplomacyPanel from './DiplomacyPanel.svelte'

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
  publication_id: 'dip-pub-0123456789abcdef',
  snapshot_digest: 'a'.repeat(64),
  relation_count: 1,
  party_count: 2,
  contact_count: 1,
  envoy_count: 1,
  negotiation_count: 0,
  instrument_count: 1,
  declaration_count: 1,
  misrepresentation_count: 1,
  termination_count: 1,
  conflict_count: 0,
  candidate_count: 1,
  lineage_edge_count: 0,
  coverage: 'partial',
}

const relation = {
  relation_id: 'dpl-0000000000000001',
  owner_token: '0'.repeat(16),
  party_tokens: ['0'.repeat(16), '1'.repeat(16)],
  opened_tick: 1,
  last_tick: 2,
  provenance: 'communicated',
}

const relations = { items: [relation], next_cursor: null }
const instruments = {
  items: [
    {
      instrument_id: 'dpi-0000000000000001',
      relation_id: relation.relation_id,
      owner_token: '0'.repeat(16),
      party_tokens: relation.party_tokens,
      instrument_kind: 'proposal',
      term_kind: 'material_exchange',
      subject_token: '2'.repeat(16),
      opener_envoy_token: null,
      opened_tick: 1,
      end_tick: null,
      anchor_refs: [],
      provenance: 'communicated',
    },
  ],
  next_cursor: null,
}
const lineage = { items: [], next_cursor: null }
const detail = {
  relation,
  parties: [
    {
      party_id: 'dpp-0000000000000001',
      owner_token: '0'.repeat(16),
      party_token: '1'.repeat(16),
      party_kind: 'agent',
      resolution: 'resolved',
      first_seen_tick: 1,
      provenance: 'communicated',
    },
  ],
  contacts: [],
  envoys: [
    {
      envoy_id: 'dpe-0000000000000001',
      relation_id: relation.relation_id,
      owner_token: '0'.repeat(16),
      party_token: '1'.repeat(16),
      envoy_token: '3'.repeat(16),
      mandate_token: null,
      status: 'contested',
      accredited_tick: 1,
      end_tick: null,
      provenance: 'communicated',
    },
  ],
  negotiations: [],
  instruments: instruments.items,
  declarations: [],
  misrepresentations: [
    {
      misrepresentation_id: 'dps-0000000000000001',
      instrument_id: 'dpi-0000000000000001',
      owner_token: '0'.repeat(16),
      kind: 'scope_exceeded',
      observed_tick: 2,
      envoy_token: '3'.repeat(16),
      party_token: null,
      provenance: 'representation_belief',
    },
  ],
  terminations: [
    {
      termination_id: 'dpt-0000000000000001',
      owner_token: '0'.repeat(16),
      target_kind: 'instrument',
      target_ref: 'dpi-0000000000000001',
      kind: 'superseded',
      tick: 2,
      provenance: 'communicated',
    },
  ],
  truncated: false,
}

function stubFetch(override?: (path: string) => Response | null): void {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const path = new URL(String(input), 'http://local.test').pathname
      const custom = override?.(path) ?? null
      if (custom !== null) return custom
      if (path.endsWith('/diplomacy')) return json(summary)
      if (path.endsWith('/diplomacy/relations')) return json(relations)
      if (path.endsWith('/diplomacy/instruments')) return json(instruments)
      if (path.endsWith('/diplomacy/lineage')) return json(lineage)
      if (path.includes('/diplomacy/relations/')) return json(detail)
      return json({ code: 'not_found' }, 404)
    }),
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('DiplomacyPanel', () => {
  it('renders retained rows and neutral labels without a score', async () => {
    stubFetch()
    const view = render(DiplomacyPanel as never, {
      runId: 'run-1',
      selection: emptyResearchSelection(),
    })
    await settle()
    const text = view.target.textContent ?? ''
    expect(text).toContain('Diplomacy')
    expect(text).toContain('scope exceeded')
    expect(text).toContain('standing: contested')
    expect(text).not.toContain('score')
    const buttons = Array.from(view.target.querySelectorAll('button'))
    ;(buttons[1] as HTMLButtonElement).click()
    await settle()
    expect(view.target.textContent).toContain('Retained misrepresentation observations')
    expect(view.target.textContent).toContain('Retained terminations')
  })

  it('renders the empty state', async () => {
    stubFetch((path) =>
      path.endsWith('/diplomacy/relations')
        ? json({ items: [], next_cursor: null })
        : null,
    )
    const view = render(DiplomacyPanel as never, {
      runId: 'run-1',
      selection: emptyResearchSelection(),
    })
    await settle()
    expect(view.target.textContent).toContain('No retained diplomacy relations')
  })

  it('maps the disabled code to unavailable', async () => {
    stubFetch(() => json({ code: 'diplomacy_disabled' }, 503))
    const view = render(DiplomacyPanel as never, {
      runId: 'run-1',
      selection: emptyResearchSelection(),
    })
    await settle()
    expect(view.target.textContent).toContain('disabled')
  })

  it('renders the error state', async () => {
    stubFetch(() => json({ code: 'diplomacy_not_found' }, 404))
    const view = render(DiplomacyPanel as never, {
      runId: 'run-1',
      selection: emptyResearchSelection(),
    })
    await settle()
    expect(view.target.textContent).toContain('could not be read')
  })
})
