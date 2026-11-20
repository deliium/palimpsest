import { afterEach, describe, expect, it, vi } from 'vitest'
import { emptyResearchSelection } from '../research/selection'
import { flushSync, render } from '../test/mount'
import CompetingTheoriesPanel from './CompetingTheoriesPanel.svelte'

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
  schema_version: 'competing-theories-snapshot-v1',
  counts: { theories: 1, support: 4, citations: 2, predictions: 3 },
  summary: {
    claim_count: 2,
    support_edge_count: 4,
    community_count: 2,
    failure_count: 1,
  },
  omitted_windows: 0,
  first_retained_window: 0,
  publications: ['pub-0000000000000000'],
}

function page(rows: unknown[], next: string | null = null) {
  return {
    run_id: 'run-1',
    publication_id: 'pub-0000000000000000',
    snapshot_digest: 'a'.repeat(64),
    section: 'theories',
    rows,
    next_cursor: next,
    truncated: next !== null,
  }
}

function row(key: string, theory: string, fields: [string, string | number][]) {
  return {
    section: 'theories',
    window_start: 0,
    window_end: 31,
    theory_id: theory,
    row_key: key,
    fields,
  }
}

function selection() {
  return emptyResearchSelection({ runId: 'run-1', view: 'competing-theories' })
}

function mountPanel() {
  return render(CompetingTheoriesPanel as never, {
    runId: 'run-1',
    selection: selection(),
  })
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('CompetingTheoriesPanel', () => {
  it('keeps declared support and predictive performance on separate axes', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn((url: string) => {
        if (url.includes('/support')) {
          return Promise.resolve(
            json(
              page([
                row('support:0:a2:c1', 'c1', [
                  ['owner_token', 'a2'],
                  ['support_edge_count', 1],
                ]),
              ]),
            ),
          )
        }
        if (url.includes('/predictions')) {
          return Promise.resolve(
            json(
              page([
                row('case-1', 'c1', [
                  ['state', 'scored'],
                  ['observed', 'summer'],
                ]),
              ]),
            ),
          )
        }
        if (url.includes('/competing-theories?') || url.endsWith('/competing-theories')) {
          return Promise.resolve(json(summary))
        }
        return Promise.resolve(
          json(page([row('theories:0', 'window:0', [['claim_count', 2]])])),
        )
      }),
    )
    const mounted = mountPanel()
    await settle()
    expect(mounted.target.textContent).toContain('Competing theories')
    expect(mounted.target.textContent).toContain('2 claims')
    expect(mounted.target.textContent).toContain('Declared support and observed predictive performance are separate axes')

    const supportTab = [...mounted.target.querySelectorAll('button')].find(
      (button) => button.textContent?.trim() === 'Declared support',
    )
    supportTab?.click()
    await settle()
    expect(mounted.target.textContent).toContain('Social axis')
    expect(mounted.target.textContent).toContain('testimony')

    const predictionsTab = [...mounted.target.querySelectorAll('button')].find(
      (button) => button.textContent?.trim() === 'Predictions',
    )
    predictionsTab?.click()
    await settle()
    expect(mounted.target.textContent).toContain('Predictive axis')
    expect(mounted.target.textContent).toContain('never failures')
    expect(mounted.target.textContent).not.toContain('winner')
    mounted.cleanup()
  })

  it('distinguishes disabled from a missing run', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        Promise.resolve(
          json(
            {
              type: 'about:blank',
              title: 'x',
              status: 503,
              detail: 'competing_theories_disabled',
            },
            503,
          ),
        ),
      ),
    )
    const mounted = mountPanel()
    await settle()
    expect(mounted.target.textContent).toContain('disabled')

    vi.unstubAllGlobals()
    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        Promise.resolve(
          json(
            {
              type: 'about:blank',
              title: 'x',
              status: 404,
              detail: 'competing_theories_publication_not_found',
            },
            404,
          ),
        ),
      ),
    )
    const missing = mountPanel()
    await settle()
    expect(missing.target.textContent).toContain('No matching run or publication')
    mounted.cleanup()
    missing.cleanup()
  })

  it('reports a known-empty section without claiming unavailable data', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn((url: string) => {
        if (url.includes('/competing-theories?') || url.endsWith('/competing-theories')) {
          return Promise.resolve(json(summary))
        }
        return Promise.resolve(json(page([])))
      }),
    )
    const mounted = mountPanel()
    await settle()
    expect(mounted.target.textContent).toContain('No retained rows')
    mounted.cleanup()
  })

  it('drops stale responses after a run or tab change', async () => {
    let resolveFirst: ((value: Response) => void) | undefined
    let calls = 0
    vi.stubGlobal(
      'fetch',
      vi.fn((url: string) => {
        if (url.includes('/competing-theories?') || url.endsWith('/competing-theories')) {
          return Promise.resolve(json(summary))
        }
        calls += 1
        if (calls === 1) {
          return new Promise<Response>((resolve) => {
            resolveFirst = resolve
          })
        }
        return Promise.resolve(
          json(page([row('predictions:0', 'c1', [['scored_count', 3]])])),
        )
      }),
    )
    const mounted = mountPanel()
    await settle()
    const predictionsTab = [...mounted.target.querySelectorAll('button')].find(
      (button) => button.textContent?.trim() === 'Predictions',
    )
    predictionsTab?.click()
    await settle()
    resolveFirst?.(json(page([row('stale', 'c9', [['claim_count', 99]])])))
    await settle()
    expect(mounted.target.textContent).toContain('predictions:0')
    expect(mounted.target.textContent).not.toContain('stale')
    mounted.cleanup()
  })

  it('pins publication and cursor across paging', async () => {
    const urls: string[] = []
    vi.stubGlobal(
      'fetch',
      vi.fn((url: string) => {
        urls.push(url)
        if (url.includes('/competing-theories?') || url.endsWith('/competing-theories')) {
          return Promise.resolve(json(summary))
        }
        if (url.includes('cursor=')) {
          return Promise.resolve(
            json(page([row('support:1:a3:c1', 'c1', [['owner_token', 'a3']])])),
          )
        }
        return Promise.resolve(
          json(page([row('support:0:a2:c1', 'c1', [['owner_token', 'a2']])], 'next-1')),
        )
      }),
    )
    const mounted = mountPanel()
    await settle()
    const supportTab = [...mounted.target.querySelectorAll('button')].find(
      (button) => button.textContent?.trim() === 'Declared support',
    )
    supportTab?.click()
    await settle()
    const more = [...mounted.target.querySelectorAll('button')].find(
      (button) => button.textContent?.trim() === 'Load more',
    )
    more?.click()
    await settle()
    expect(urls.some((url) => url.includes('publication_id=pub-0000000000000000'))).toBe(true)
    expect(urls.some((url) => url.includes('cursor=next-1'))).toBe(true)
    expect(mounted.target.textContent).toContain('support:1:a3:c1')
    mounted.cleanup()
  })
})
