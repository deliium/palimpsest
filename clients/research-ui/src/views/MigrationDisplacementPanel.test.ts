import { afterEach, describe, expect, it, vi } from 'vitest'
import { emptyResearchSelection } from '../research/selection'
import { flushSync, render } from '../test/mount'
import MigrationDisplacementPanel from './MigrationDisplacementPanel.svelte'

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
  publication_id: 'md-pub-0123456789abcdef',
  digest: 'a'.repeat(64),
  schema_version: 'migration-displacement-snapshot-v1',
  candidate_count: 1,
  wave_count: 1,
  cluster_count: 1,
  outcome_count: 1,
  movement_count: 1,
  cause_count: 1,
  displacement_like_count: 1,
  mixed_count: 0,
  not_displacement_like_count: 0,
  unknown_count: 0,
  coverage: 'complete',
}

const route = {
  route_token: 'mdr-0123456789abcdef',
  owner_token: 'mown-0123456789abcdef',
  origin_token: 'mdl-origin',
  destination_token: 'mdl-dest',
  route_tokens: ['mdl-origin', 'mdl-dest'],
  observed_duration_ticks: 2,
  fatigue_cost: 1,
  basis: 'own_journey',
  status: 'open',
  first_tick: 0,
  last_tick: 2,
}

const cause = {
  cause_token: 'mdcse-0123456789abcdef',
  owner_token: 'mown-0123456789abcdef',
  cause_kind: 'conflict',
  source_kind: 'direct_observation',
  anchor_token: '',
  confidence: 0.5,
  tick: 1,
  status: 'active',
}

const wave = {
  wave_token: 'mig-0123456789abcdef',
  origin_token: 'mdl-origin',
  destination_token: 'mdl-dest',
  participant_tokens: ['mdo-1', 'mdo-2'],
  route_tokens: ['mdl-origin', 'mdl-dest'],
  start_tick: 0,
  end_tick: 2,
  cause_support_counts: [['conflict', 1]],
  displacement_classification: 'displacement_like',
  displacement_bases: ['conflict'],
  independent_cause_count: 1,
  cluster_tokens: ['mdc-1'],
  coverage: 'complete',
}

const outcome = {
  outcome_token: 'mdo-0123456789abcdef',
  participant_token: 'mdp-0123456789abcdef',
  destination_token: 'mdl-dest',
  residence_ticks: 4,
  access_evidence_count: 1,
  participation_evidence_count: 0,
  relationship_evidence_count: 0,
  conflict_evidence_count: 0,
  classification: 'settled',
  coverage: 'complete',
  censored: false,
}

function stubFetch(override?: (path: string) => Response | null): void {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const path = new URL(String(input), 'http://local.test').pathname
      const custom = override?.(path) ?? null
      if (custom !== null) return custom
      if (path.endsWith('/migration')) return json(summary)
      if (path.endsWith('/migration/routes')) {
        return json({ items: [route], next_cursor: null })
      }
      if (path.endsWith('/migration/causes')) {
        return json({ items: [cause], next_cursor: null })
      }
      if (path.endsWith('/migration/waves')) {
        return json({ items: [wave], next_cursor: null })
      }
      if (path.endsWith('/migration/outcomes')) {
        return json({ items: [outcome], next_cursor: null })
      }
      return json({ code: 'not_found' }, 404)
    }),
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('MigrationDisplacementPanel', () => {
  it('renders four sections with badges', async () => {
    stubFetch()
    const view = render(MigrationDisplacementPanel as never, {
      runId: 'run-1',
      selection: emptyResearchSelection(),
    })
    await settle()
    const text = (view.target.textContent ?? '').toLowerCase()
    expect(text).toContain('migration and displacement')
    expect(text).toContain('movement and routes')
    expect(text).toContain('cause evidence')
    expect(text).toContain('waves and clusters')
    expect(text).toContain('integration outcomes')
    expect(text).toContain('objective')
    expect(text).toContain('subjective')
    expect(text).toContain('analytical')
    expect(text).toContain('integration')
    expect(text).toContain('displacement_like (analytical)')
    expect(text).toContain('researcher-only classification')
    expect(text).not.toContain('refugee')
    expect(text).not.toContain('asylum')
    expect(text).not.toContain('forced')
    expect(text).not.toContain('displaced person')
    expect(text).not.toContain('write')
    expect(text).not.toContain('save')
    expect(view.target.querySelector('button,input,textarea,form')).toBeNull()
  })

  it('shows disabled state on 503', async () => {
    stubFetch(() => json({ detail: 'migration_displacement_disabled' }, 503))
    const view = render(MigrationDisplacementPanel as never, {
      runId: 'run-1',
      selection: emptyResearchSelection(),
    })
    await settle()
    expect(view.target.textContent ?? '').toContain('disabled')
  })

  it('shows empty state on no rows', async () => {
    stubFetch((path) => {
      if (path.endsWith('/migration')) return json(summary)
      if (
        path.endsWith('/migration/routes') ||
        path.endsWith('/migration/causes') ||
        path.endsWith('/migration/waves') ||
        path.endsWith('/migration/outcomes')
      ) {
        return json({ items: [], next_cursor: null })
      }
      return null
    })
    const view = render(MigrationDisplacementPanel as never, {
      runId: 'run-1',
      selection: emptyResearchSelection(),
    })
    await settle()
    expect(view.target.textContent ?? '').toContain('No migration-displacement rows')
  })
})
