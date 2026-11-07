import { afterEach, describe, expect, it, vi } from 'vitest'
import { emptyResearchSelection } from '../research/selection'
import { flushSync, render } from '../test/mount'
import BordersPanel from './BordersPanel.svelte'

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
  publication_id: 'bd-pub-0123456789abcdef',
  digest: 'a'.repeat(64),
  schema_version: 'borders-snapshot-v1',
  candidate_count: 1,
  claim_count: 1,
  agreement_count: 1,
  dispute_count: 1,
  physical_row_count: 1,
  pattern_count: 1,
  coverage: 'complete',
}

const claim = {
  claim_token: 'bdc-0123456789abcdef',
  owner_token: 'bown-0123456789abcdef',
  domain_token: 'bdc-0123456789abcdef',
  location_tokens: ['bloc-0123456789abcdef'],
  boundary_edge_tokens: [],
  status: 'claimed',
  strength: 0.8,
  anchor_token: '',
}

const agreement = {
  agreement_token: 'bda-0123456789abcdef',
  domain_token: 'bdc-0123456789abcdef',
  counterparty_token: 'bcp-0123456789abcdef',
  provision_tokens: ['passage'],
  status: 'apparent_acceptance',
  recognition: 'recognized',
  effective_tick: 1,
  expiry_tick: null,
}

const physical = {
  layer: 'physical',
  location_token: 'bloc-0123456789abcdef',
  window_start: 0,
  window_end: 5,
  actor_count: 1,
  action_count: 2,
  hostile_count: 0,
  assistance_count: 0,
  presence_ticks: 2,
  classification: 'repeated_use',
  location_tokens: [],
  physical_actions: 0,
  claim_count: 0,
  agreement_count: 0,
  dispute_count: 0,
}

const pattern = {
  layer: 'analytical',
  pattern_token: 'bpat-0123456789abcdef',
  domain_token: 'bdc-0123456789abcdef',
  location_tokens: ['bloc-0123456789abcdef'],
  pattern: 'claim_aligned',
  physical_actions: 2,
  claim_count: 1,
  agreement_count: 1,
  dispute_count: 0,
  actor_count: 0,
  action_count: 0,
  hostile_count: 0,
  assistance_count: 0,
  presence_ticks: 0,
}

function stubFetch(override?: (path: string) => Response | null): void {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const path = new URL(String(input), 'http://local.test').pathname
      const custom = override?.(path) ?? null
      if (custom !== null) return custom
      if (path.endsWith('/borders')) return json(summary)
      if (path.endsWith('/borders/claims')) {
        return json({ items: [claim], next_cursor: null })
      }
      if (path.endsWith('/borders/agreements')) {
        return json({ items: [agreement], next_cursor: null })
      }
      if (path.endsWith('/borders/control')) {
        return json({ items: [physical, pattern], next_cursor: null })
      }
      return json({ code: 'not_found' }, 404)
    }),
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('BordersPanel', () => {
  it('renders four neutral epistemic sections', async () => {
    stubFetch()
    const view = render(BordersPanel as never, {
      runId: 'run-1',
      selection: emptyResearchSelection(),
    })
    await settle()
    const text = (view.target.textContent ?? '').toLowerCase()
    expect(text).toContain('borders and claims')
    expect(text).toContain('physical control')
    expect(text).toContain('claims')
    expect(text).toContain('agreements')
    expect(text).toContain('control patterns')
    expect(text).not.toContain('winner')
    expect(text).not.toContain('loser')
    expect(text).not.toContain('legitimate')
    expect(text).not.toContain('sovereignty')
    expect(text).not.toContain('ownership')
    expect(text).not.toContain('score')
  })

  it('renders disabled state explicitly', async () => {
    stubFetch(() => json({ detail: 'borders_disabled' }, 503))
    const view = render(BordersPanel as never, {
      runId: 'run-1',
      selection: emptyResearchSelection(),
    })
    await settle()
    expect(view.target.textContent ?? '').toContain('not configured')
  })
})
