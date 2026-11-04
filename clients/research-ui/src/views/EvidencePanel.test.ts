import { afterEach, describe, expect, it, vi } from 'vitest'
import { emptyResearchSelection } from '../research/selection'
import { flushSync, render } from '../test/mount'
import EvidencePanel from './EvidencePanel.svelte'

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
  publication_id: 'evid-pub-0123456789abcdef',
  snapshot_digest: 'a'.repeat(64),
  generated_tick: 9,
  candidate_count: 1,
  source_count: 1,
  testimony_count: 1,
  item_count: 1,
  custody_link_count: 1,
  contradiction_count: 1,
  evaluation_count: 1,
  edge_count: 1,
  coverage: 'partial',
  schema_version: 'evidence-testimony-snapshot-v1',
  window_count: 1,
  provenance_code: 'evidence_testimony_published',
}

const candidates = {
  items: [
    {
      candidate_id: 'evid-0000000000000001',
      subject_token: 'artifact-1',
      source_kind_family: 'documentary',
      owner_count: 2,
      item_count: 1,
      source_count: 1,
      testimony_count: 0,
      contradiction_count: 1,
      status: 'contested',
      coverage: 'partial',
      first_tick: 1,
      last_tick: 4,
    },
  ],
  next_cursor: null,
  truncated: false,
}

const lineage = {
  items: [
    {
      edge_id: 'evid-edge-0000000000000001',
      kind: 'emerged',
      source_ids: [],
      target_ids: ['evid-0000000000000001'],
      window_index: 0,
    },
  ],
  next_cursor: null,
  truncated: false,
}

const sources = {
  items: [
    {
      owner_token: '0'.repeat(16),
      local_id: 'evs-0000000000000001',
      source_kind: 'artifact',
      reference_kind: 'artifact',
      provenance: 'direct_observation',
      confidence_band: 'mid',
      tick: 1,
      subject_token: 'artifact-1',
      custody_status: 'complete_belief',
    },
  ],
  next_cursor: null,
  truncated: false,
}

const contradictions = {
  items: [
    {
      owner_token: '0'.repeat(16),
      local_id: 'evx-0000000000000001',
      candidate_id: 'evid-0000000000000001',
      first_ref: 'evs-0000000000000001',
      second_ref: 'evi-0000000000000001',
      kind: 'interpretation_conflict',
      status: 'unresolved',
      tick: 2,
    },
  ],
  next_cursor: null,
  truncated: false,
}

const detail = {
  candidate: candidates.items[0],
  sources: sources.items,
  contradictions: contradictions.items,
  custody_complete_count: 1,
  custody_incomplete_count: 0,
  custody_conflicting_count: 0,
  sources_truncated: false,
  contradictions_truncated: false,
  alignment_label: 'researcher-only',
}

function stubFetch(override?: (path: string) => Response | null): void {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const path = new URL(String(input), 'http://local.test').pathname
      const custom = override?.(path) ?? null
      if (custom !== null) return custom
      if (path.endsWith('/evidence')) return json(summary)
      if (path.endsWith('/evidence/candidates')) return json(candidates)
      if (path.endsWith('/evidence/lineage')) return json(lineage)
      if (path.endsWith('/sources')) return json(sources)
      if (path.endsWith('/contradictions')) return json(contradictions)
      if (path.includes('/evidence/candidates/')) return json(detail)
      return json({ code: 'not_found' }, 404)
    }),
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('EvidencePanel', () => {
  it('renders summary, candidates, and researcher-only detail', async () => {
    stubFetch()
    const view = render(EvidencePanel as never, {
      runId: 'run-1',
      selection: emptyResearchSelection(),
    })
    await settle()
    expect(view.target.textContent).toContain('Evidence and testimony')
    expect(view.target.textContent).toContain('artifact-1')
    expect(view.target.textContent).toContain('researcher-only')
    const candidateButton = view.target.querySelector('button')
    ;(candidateButton as HTMLButtonElement).click()
    await settle()
    expect(view.target.textContent).toContain('Sources')
    expect(view.target.textContent).toContain('interpretation conflict')
  })

  it('renders the empty state', async () => {
    stubFetch((path) =>
      path.endsWith('/evidence/candidates')
        ? json({ items: [], next_cursor: null, truncated: false })
        : null,
    )
    const view = render(EvidencePanel as never, {
      runId: 'run-1',
      selection: emptyResearchSelection(),
    })
    await settle()
    expect(view.target.textContent).toContain('No evidence was published')
  })

  it('maps the disabled code to unavailable', async () => {
    stubFetch(() => json({ code: 'evidence_testimony_disabled' }, 503))
    const view = render(EvidencePanel as never, {
      runId: 'run-1',
      selection: emptyResearchSelection(),
    })
    await settle()
    expect(view.target.textContent).toContain('unavailable')
  })

  it('renders the error state', async () => {
    stubFetch(() => json({ code: 'evidence_testimony_not_found' }, 404))
    const view = render(EvidencePanel as never, {
      runId: 'run-1',
      selection: emptyResearchSelection(),
    })
    await settle()
    expect(view.target.textContent).toContain('Evidence read failed')
  })
})
