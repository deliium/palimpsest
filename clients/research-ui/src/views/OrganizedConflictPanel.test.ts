import { afterEach, describe, expect, it, vi } from 'vitest'
import { emptyResearchSelection } from '../research/selection'
import { flushSync, render } from '../test/mount'
import OrganizedConflictPanel from './OrganizedConflictPanel.svelte'

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
  publication_id: 'oc-pub-0123456789abcdef',
  digest: 'a'.repeat(64),
  episode_count: 1,
  individual_episode_count: 1,
  coordinated_episode_count: 0,
  persistent_inter_group_episode_count: 0,
  participant_count: 1,
  plan_count: 1,
  interpretation_count: 1,
  outcome_count: 0,
  contradiction_count: 0,
  termination_count: 0,
  sustained_episode_count: 0,
  coverage: 'consistent',
}

const episode = {
  episode_id: 'oc-0123456789abcdef',
  classification: 'individual_violence',
  start_tick: 1,
  end_tick: 2,
  participant_tokens: ['a'.repeat(16)],
  opponent_tokens: ['b'.repeat(16)],
  side_count: 1,
  hostile_event_count: 1,
  active_window_count: 1,
  sustained: false,
  org_ids: [],
  msoc_ids: [],
}

const plan = {
  plan_id: 'ocp-0123456789abcdef',
  owner_token: 'a'.repeat(16),
  operation: 'coordinated_attack',
  target_kind: 'agent',
  status: 'active',
  participant_count: 1,
  tick: 1,
}

const interpretation = {
  interpretation_id: 'oci-0123456789abcdef',
  owner_token: 'a'.repeat(16),
  episode_id: 'oc-0123456789abcdef',
  kind: 'individual_violence',
  alignment: 'consistent',
  tick: 1,
}

function stubFetch(override?: (path: string) => Response | null): void {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const path = new URL(String(input), 'http://local.test').pathname
      const custom = override?.(path) ?? null
      if (custom !== null) return custom
      if (path.endsWith('/organized-conflict')) return json(summary)
      if (path.endsWith('/organized-conflict/episodes')) {
        return json({ items: [episode], next_cursor: null, truncated: false })
      }
      if (path.endsWith('/organized-conflict/plans')) {
        return json({ items: [plan], next_cursor: null, truncated: false })
      }
      if (path.endsWith('/organized-conflict/interpretations')) {
        return json({ items: [interpretation], next_cursor: null, truncated: false })
      }
      return json({ code: 'not_found' }, 404)
    }),
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('OrganizedConflictPanel', () => {
  it('renders neutral conflict facts without score or war language', async () => {
    stubFetch()
    const view = render(OrganizedConflictPanel as never, {
      runId: 'run-1',
      selection: emptyResearchSelection(),
    })
    await settle()
    const text = (view.target.textContent ?? '').toLowerCase()
    expect(text).toContain('organized conflict')
    expect(text).toContain('episodes')
    expect(text).toContain('individual violence')
    expect(text).toContain('alignment')
    expect(text).not.toContain('winner')
    expect(text).not.toContain('legitimate')
    expect(text).not.toContain('score')
  })

  it('renders disabled state explicitly', async () => {
    stubFetch(() =>
      json({ detail: 'organized_conflict_disabled' }, 503),
    )
    const view = render(OrganizedConflictPanel as never, {
      runId: 'run-1',
      selection: emptyResearchSelection(),
    })
    await settle()
    expect(view.target.textContent ?? '').toContain('not configured')
  })
})
