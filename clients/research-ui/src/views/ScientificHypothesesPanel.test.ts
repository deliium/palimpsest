import { afterEach, describe, expect, it, vi } from 'vitest'
import { emptyResearchSelection } from '../research/selection'
import { flushSync, render } from '../test/mount'
import ScientificHypothesesPanel from './ScientificHypothesesPanel.svelte'

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
  publication_id: 'schyp-0000000000000000',
  digest: 'sha256:' + 'a'.repeat(64),
  snapshot_version: 'scientific-hypotheses-snapshot-v1',
  policy_version: 'scientific-hypotheses.v1',
  generated_from_tick: 31,
  window_tick: 0,
  window_count: 1,
  coverage: 'complete',
  availability: 'available',
  owner_count: 1,
  hypothesis_count: 1,
  active_count: 1,
  supported_count: 0,
  contradicted_count: 1,
  inconclusive_count: 0,
  revision_count: 2,
  trial_count: 2,
  matched_count: 0,
  mismatched_count: 2,
}

const hypothesis = {
  window_index: 0,
  window_tick: 0,
  hypothesis_token: 'schyp-0123456789abcdef',
  claim_token: 'claim-0123456789abcdef',
  causal_hypothesis_token: 'none',
  status: 'contradicted',
  predicted_outcome: 'success',
  confidence_milli: 250,
  condition_count: 1,
  condition_pairs: [['day_phase', 'day']] as [string, string][],
  support_count: 0,
  contradiction_count: 2,
  revision_count: 2,
  source_kind: 'observed',
  active: true,
  created_tick: 0,
  coverage: 'complete',
}

const evidence = {
  window_index: 0,
  window_tick: 0,
  hypothesis_token: 'schyp-0123456789abcdef',
  support_observation_count: 0,
  contradiction_count: 2,
  evidence_event_count: 2,
  unlinked_event_count: 0,
  coverage: 'complete',
}

const test = {
  window_index: 0,
  window_tick: 0,
  hypothesis_token: 'schyp-0123456789abcdef',
  trial_count: 2,
  matched_count: 0,
  mismatched_count: 2,
  inconclusive_count: 0,
  last_trial_tick: 2,
  coverage: 'complete',
}

const revision = {
  window_index: 0,
  window_tick: 0,
  hypothesis_token: 'schyp-0123456789abcdef',
  revision_index: 1,
  revision_tick: 2,
  reason: 'contradiction_added',
  claim_token: 'claim-0123456789abcdef',
  predicted_outcome: 'success',
  condition_pairs: [['day_phase', 'day']] as [string, string][],
  confidence_milli: 250,
  coverage: 'complete',
}

const source = {
  window_index: 0,
  window_tick: 0,
  source_kind: 'observed',
  hypothesis_count: 1,
  adopted_count: 0,
  coverage: 'complete',
}

const coverage = {
  window_index: 0,
  window_tick: 0,
  window_count: 1,
  event_count: 2,
  owner_count: 1,
  hypothesis_count: 1,
  condition_count: 1,
  revision_count: 2,
  trial_count: 2,
  truncated: false,
  coverage: 'complete',
  availability: 'available',
}

function page<T>(rows: T[]) {
  return {
    run_id: 'run-1',
    publication_id: 'schyp-0000000000000000',
    window_index: 0,
    rows,
    next_cursor: null,
    coverage: 'complete',
  }
}

function installFetch(handler: (url: string) => Response): void {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => handler(String(input))),
  )
}

function selection() {
  return emptyResearchSelection({ runId: 'run-1', view: 'scientific-hypotheses' })
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('ScientificHypothesesPanel', () => {
  it('renders all seven sections with literal tokens and no truth vocabulary', async () => {
    installFetch((url) => {
      if (url.endsWith('/scientific-hypotheses')) return json(summary)
      if (url.includes('/hypotheses')) return json(page([hypothesis]))
      if (url.includes('/evidence')) return json(page([evidence]))
      if (url.includes('/tests')) return json(page([test]))
      if (url.includes('/revisions')) return json(page([revision]))
      if (url.includes('/sources')) return json(page([source]))
      if (url.includes('/coverage')) return json(page([coverage]))
      return json({}, 404)
    })
    const view = render(ScientificHypothesesPanel as never, {
      runId: 'run-1',
      selection: selection(),
    })
    await settle()
    const text = view.target.textContent ?? ''
    expect(text).toContain('Summary')
    expect(text).toContain('Hypotheses')
    expect(text).toContain('Evidence')
    expect(text).toContain('Tests')
    expect(text).toContain('Revisions')
    expect(text).toContain('Sources')
    expect(text).toContain('Coverage')
    expect(text).toContain('contradicted')
    expect(text).toContain('observed')
    expect(text).toContain('250/1000')
    expect(text).toContain('day_phase=day')
    const lowered = text.toLowerCase()
    for (const token of [
      'truth',
      'verified',
      'proven',
      'accuracy',
      'calibration',
      'score',
    ]) {
      expect(lowered).not.toContain(token)
    }
  })

  it('keeps old revisions visible in order', async () => {
    const older = { ...revision, revision_index: 0, reason: 'test_formulated' }
    installFetch((url) => {
      if (url.endsWith('/scientific-hypotheses')) return json(summary)
      if (url.includes('/hypotheses')) return json(page([hypothesis]))
      if (url.includes('/evidence')) return json(page([evidence]))
      if (url.includes('/tests')) return json(page([test]))
      if (url.includes('/revisions')) return json(page([revision, older]))
      if (url.includes('/sources')) return json(page([source]))
      if (url.includes('/coverage')) return json(page([coverage]))
      return json({}, 404)
    })
    const view = render(ScientificHypothesesPanel as never, {
      runId: 'run-1',
      selection: selection(),
    })
    await settle()
    const text = view.target.textContent ?? ''
    expect(text).toContain('#0')
    expect(text).toContain('#1')
    expect(text).toContain('test_formulated')
    expect(text).toContain('contradiction_added')
  })

  it('renders an explicit empty state', async () => {
    installFetch((url) => {
      if (url.endsWith('/scientific-hypotheses')) return json(summary)
      return json(page([]))
    })
    const view = render(ScientificHypothesesPanel as never, {
      runId: 'run-1',
      selection: selection(),
    })
    await settle()
    expect(view.target.textContent ?? '').toContain(
      'No scientific hypotheses were published',
    )
  })

  it('renders the disabled state', async () => {
    installFetch(() => json({ code: 'scientific_hypotheses_disabled' }, 503))
    const view = render(ScientificHypothesesPanel as never, {
      runId: 'run-1',
      selection: selection(),
    })
    await settle()
    expect(view.target.textContent ?? '').toContain(
      'Scientific hypotheses are disabled',
    )
  })
})
