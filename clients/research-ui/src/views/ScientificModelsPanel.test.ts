import { afterEach, describe, expect, it, vi } from 'vitest'
import { emptyResearchSelection } from '../research/selection'
import { flushSync, render } from '../test/mount'
import ScientificModelsPanel from './ScientificModelsPanel.svelte'

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
  publication_id: 'pub-0000000000000000',
  snapshot_digest: 'a'.repeat(64),
  schema_version: 'scientific-models-snapshot-v1',
  policy_version: 'scientific-models-publication.v1',
  finalized_through_tick: 9,
  coverage_status: 'complete',
  counts: { predictions: 1, outcomes: 1 },
  publications: ['pub-0000000000000000'],
}

function page(rows: unknown[]) {
  return {
    run_id: 'run-1',
    publication_id: 'pub-0000000000000000',
    snapshot_digest: 'a'.repeat(64),
    section: 'predictions',
    rows,
    next_cursor: null,
    truncated: false,
  }
}

function selection() {
  return emptyResearchSelection({ runId: 'run-1', view: 'scientific-models' })
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('ScientificModelsPanel', () => {
  it('renders counts, prior predictions and qualification note', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn((url: string) => {
        if (url.includes('/predictions')) {
          return Promise.resolve(json(page([{ prediction_token: 'p1' }])))
        }
        return Promise.resolve(json(summary))
      }),
    )
    const mounted = render(ScientificModelsPanel, {
      runId: 'run-1',
      selection: selection(),
    })
    await settle()
    expect(mounted.target.textContent).toContain('Scientific models')
    expect(mounted.target.textContent).toContain('predictions: 1')
    expect(mounted.target.textContent).toContain('p1')
    expect(mounted.target.textContent).toContain('No truth')
    expect(mounted.target.textContent).toContain('Owner-observed outcome')
    expect(mounted.target.textContent).toContain('not isolated regeneration')
    mounted.cleanup()
  })

  it('distinguishes disabled artifacts from an error', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        Promise.resolve(
          json({ type: 'about:blank', title: 'x', status: 503, detail: 'scientific_models_disabled' }, 503),
        ),
      ),
    )
    const mounted = render(ScientificModelsPanel, {
      runId: 'run-1',
      selection: selection(),
    })
    await settle()
    expect(mounted.target.textContent).toContain('not configured')
    mounted.cleanup()
  })
})
