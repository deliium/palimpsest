import { afterEach, describe, expect, it, vi } from 'vitest'
import { emptyResearchSelection } from '../research/selection'
import { flushSync, render } from '../test/mount'
import EconomicCascadesPanel from './EconomicCascadesPanel.svelte'

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
  publication_id: 'ecasc-0000000000000000',
  digest: 'sha256:' + 'a'.repeat(64),
  snapshot_version: 'economic-cascades-snapshot-v1',
  policy_version: 'economic-cascades.v1',
  generated_from_tick: 31,
  window_tick: 0,
  window_count: 1,
  coverage: 'complete',
  availability: 'available',
  event_count: 4,
  disruption_count: 1,
  stage_count: 2,
  dependency_edge_count: 1,
  chain_count: 1,
  linked_chain_count: 1,
  disruption_kind_count: 1,
  max_depth: 2,
}

const disruption = {
  window_index: 0,
  window_tick: 0,
  kind: 'resource_loss',
  disruption_count: 1,
  magnitude_total: 1,
  subject_count: 1,
  coverage: 'complete',
}

const dependency = {
  window_index: 0,
  window_tick: 0,
  upstream_token: 'harvest_ore',
  downstream_recipe_token: 'smelt_ore',
  kind: 'item_input',
  depth: 1,
  evidence_count: 1,
}

const chain = {
  chain_token: 'casc-0123456789abcdef',
  window_index: 0,
  window_tick: 0,
  disruption_kind: 'resource_loss',
  depth: 1,
  lag_windows: 0,
  shortfall_share_milli: 500,
  state: 'linked',
  coverage: 'complete',
}

const propagation = {
  window_index: 0,
  window_tick: 0,
  disruption_kind: 'resource_loss',
  chain_count: 1,
  linked_chain_count: 1,
  unlinked_chain_count: 0,
  unresolved_chain_count: 0,
  mean_depth_milli: 1000,
  mean_lag_milli: 0,
  downstream_stage_count: 1,
  coverage: 'complete',
  availability: 'insufficient_samples',
}

const coverage = {
  window_index: 0,
  window_tick: 0,
  window_count: 1,
  event_count: 4,
  disruption_count: 1,
  stage_count: 2,
  dependency_edge_count: 1,
  labor_join_count: 1,
  chain_count: 1,
  linked_chain_count: 1,
  truncated: false,
  coverage: 'complete',
  availability: 'available',
}

function page<T>(rows: T[]) {
  return {
    run_id: 'run-1',
    publication_id: 'ecasc-0000000000000000',
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
  return emptyResearchSelection({ runId: 'run-1', view: 'economic-cascades' })
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('EconomicCascadesPanel', () => {
  it('renders all six sections without severity vocabulary', async () => {
    installFetch((url) => {
      if (url.endsWith('/economic-cascades')) return json(summary)
      if (url.includes('/disruptions')) return json(page([disruption]))
      if (url.includes('/dependencies')) return json(page([dependency]))
      if (url.includes('/chains')) return json(page([chain]))
      if (url.includes('/propagation')) return json(page([propagation]))
      if (url.includes('/coverage')) return json(page([coverage]))
      return json({}, 404)
    })
    const view = render(EconomicCascadesPanel as never, {
      runId: 'run-1',
      selection: selection(),
    })
    await settle()
    const text = view.target.textContent ?? ''
    expect(text).toContain('Summary')
    expect(text).toContain('Disruptions')
    expect(text).toContain('Dependencies')
    expect(text).toContain('Chains')
    expect(text).toContain('Propagation')
    expect(text).toContain('Coverage')
    expect(text).toContain('linked')
    expect(text.toLowerCase()).not.toContain('severity')
    expect(text.toLowerCase()).not.toContain('cascade score')
    expect(text.toLowerCase()).not.toContain('root cause')
  })

  it('renders an explicit empty state', async () => {
    installFetch((url) => {
      if (url.endsWith('/economic-cascades')) return json(summary)
      return json(page([]))
    })
    const view = render(EconomicCascadesPanel as never, {
      runId: 'run-1',
      selection: selection(),
    })
    await settle()
    expect(view.target.textContent ?? '').toContain(
      'No economic-cascade evidence',
    )
  })

  it('renders the disabled state', async () => {
    installFetch(() => json({ code: 'economic_cascades_disabled' }, 503))
    const view = render(EconomicCascadesPanel as never, {
      runId: 'run-1',
      selection: selection(),
    })
    await settle()
    expect(view.target.textContent ?? '').toContain('unavailable')
  })
})
