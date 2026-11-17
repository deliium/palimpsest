import { afterEach, describe, expect, it, vi } from 'vitest'
import { emptyResearchSelection } from '../research/selection'
import { flushSync, render } from '../test/mount'
import ReplicationPanel from './ReplicationPanel.svelte'

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
  publication_id: 'srep-0000000000000000',
  internal_digest: 'a'.repeat(64),
  policy_version: 'scientific-replication.v1',
  summary: {
    design_count: 1,
    attempt_count: 1,
    execution_count: 1,
    report_count: 1,
    comparison_count: 1,
    interpretation_count: 1,
    collaboration_count: 1,
    participant_count: 2,
    first_tick: 0,
    last_tick: 31,
    coverage: 'partial',
    availability: 'available',
    reason_codes: ['condition_unknown'],
  },
}

function page(rows: unknown[] = []) {
  return {
    run_id: 'run-1',
    publication_id: 'srep-0000000000000000',
    internal_digest: 'a'.repeat(64),
    policy_version: 'scientific-replication.v1',
    coverage: 'partial',
    availability: 'available',
    rows,
    next_cursor: null,
    truncated: false,
  }
}

function selection() {
  return emptyResearchSelection({
    runId: 'run-1',
    view: 'scientific-replication',
  })
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('ReplicationPanel', () => {
  it('renders separate objective and owner-report lanes without truth badges', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn((url: string) => {
        if (url.endsWith('/scientific-replication')) {
          return Promise.resolve(json(summary))
        }
        if (url.includes('/results')) {
          return Promise.resolve(
            json(
              page([
                {
                  record_type: 'execution',
                  row_kind: 'execution',
                  layer: 'objective',
                  row_token: 'rrow-1',
                  fact: { outcome: 'success' },
                },
                {
                  record_type: 'report',
                  row_kind: 'report',
                  layer: 'owner_scoped',
                  row_token: 'rrow-2',
                  fact: {
                    measurement: {
                      outcome: 'failure',
                      uncertainty_kind: 'unreported',
                      possible_outcomes: [],
                    },
                  },
                },
              ]),
            ),
          )
        }
        return Promise.resolve(json(page()))
      }),
    )
    const view = render(ReplicationPanel as never, {
      runId: 'run-1',
      selection: selection(),
    })
    await settle()
    const text = view.target.textContent ?? ''
    expect(text).toContain('Objective execution')
    expect(text).toContain('Owner report')
    expect(text).toContain('uncertainty unreported')
    expect(text).not.toContain('proven')
    expect(text).not.toContain('truth')
  })

  it('shows disabled/unavailable state distinctly', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        Promise.resolve(
          json({ code: 'scientific_replication_disabled' }, 503),
        ),
      ),
    )
    const view = render(ReplicationPanel as never, {
      runId: 'run-1',
      selection: selection(),
    })
    await settle()
    expect(view.target.textContent).toContain('disabled or unavailable')
  })
})
