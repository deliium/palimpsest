import { afterEach, describe, expect, it, vi } from 'vitest'
import { emptyResearchSelection } from '../research/selection'
import { flushSync, render } from '../test/mount'
import ScientificInstitutionsPanel from './ScientificInstitutionsPanel.svelte'

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
  schema_version: 'scientific-institutions-snapshot-v1',
  policy_version: 'scientific-institutions.v1',
  input_revision: 'rev-1',
  boundary_tick: 64,
  counts: { windows: 2, practice: 2, signals: 1, lineage: 2 },
  summary: { stable_row_count: 2, episode_count: 1 },
  publications: ['pub-0000000000000000'],
}

function page(rows: unknown[], next: string | null = null) {
  return {
    run_id: 'run-1',
    publication_id: 'pub-0000000000000000',
    snapshot_digest: 'a'.repeat(64),
    section: 'practice',
    rows,
    next_cursor: next,
    truncated: next !== null,
  }
}

function row(key: string, fields: [string, string | number][]) {
  return {
    section: 'practice',
    window_index: 0,
    row_key: key,
    fields,
  }
}

function mountPanel() {
  return render(ScientificInstitutionsPanel as never, {
    runId: 'run-1',
    selection: emptyResearchSelection({
      runId: 'run-1',
      view: 'scientific-institutions',
    }),
  })
}

function findTab(target: HTMLElement, label: string) {
  return [...target.querySelectorAll('button')].find(
    (button) => button.textContent?.trim() === label,
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('ScientificInstitutionsPanel', () => {
  it('shows distinct statuses and keeps the no-truth caveat', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn((url: string) => {
        if (url.endsWith('/scientific-institutions')) {
          return Promise.resolve(json(summary))
        }
        return Promise.resolve(
          json(
            page([
              row('practice:stable', [
                ['status', 'stable'],
                ['organization_token', 't:org'],
                ['operator', 'vary_process'],
                ['process_token', 'harvest'],
                ['actor_tokens', 't:a'],
                ['surviving_carrier_tokens', 'record|t:c'],
              ]),
              row('practice:observed', [
                ['status', 'observed_only'],
                ['organization_token', 't:org'],
                ['operator', 'combine'],
                ['process_token', 'harvest'],
                ['actor_tokens', 't:b'],
                ['surviving_carrier_tokens', ''],
              ]),
            ]),
          ),
        )
      }),
    )
    const mounted = mountPanel()
    await settle()
    const practiceTab = findTab(mounted.target, 'Practice')
    practiceTab?.click()
    await settle()
    expect(mounted.target.textContent).toContain('stable')
    expect(mounted.target.textContent).toContain('observed_only')
    expect(mounted.target.textContent).toContain('not truth')
    mounted.cleanup()
  })

  it('pages with the pinned publication and drops stale tab responses', async () => {
    let resolveFirst: ((value: Response) => void) | undefined
    let calls = 0
    const urls: string[] = []
    vi.stubGlobal(
      'fetch',
      vi.fn((url: string) => {
        urls.push(url)
        if (url.endsWith('/scientific-institutions')) {
          return Promise.resolve(json(summary))
        }
        calls += 1
        if (calls === 1) {
          return new Promise<Response>((resolve) => {
            resolveFirst = resolve
          })
        }
        return Promise.resolve(
          json(page([row('practice:current', [['status', 'stable']])])),
        )
      }),
    )
    const mounted = mountPanel()
    await settle()
    const practiceTab = findTab(mounted.target, 'Practice')
    practiceTab?.click()
    await settle()
    const windowsTab = findTab(mounted.target, 'Windows & coverage')
    windowsTab?.click()
    await settle()
    resolveFirst?.(json(page([row('practice:stale', [['status', 'stable']])])))
    await settle()
    expect(mounted.target.textContent).toContain('practice:current')
    expect(mounted.target.textContent).not.toContain('practice:stale')
    expect(urls.some((url) => url.includes('publication_id='))).toBe(true)
    expect(urls.every((url) => !url.includes('method=POST'))).toBe(true)
    mounted.cleanup()
  })

  it('pages lineage with load more under the pinned publication', async () => {
    const urls: string[] = []
    vi.stubGlobal(
      'fetch',
      vi.fn((url: string) => {
        urls.push(url)
        if (url.endsWith('/scientific-institutions')) {
          return Promise.resolve(json(summary))
        }
        if (url.includes('/lineage') && !url.includes('cursor=')) {
          return Promise.resolve(
            json(
              page(
                [
                  {
                    section: 'lineage',
                    window_index: 1,
                    row_key: 'lineage:first',
                    fields: [
                      ['record_kind', 'transition'],
                      ['transition_kind', 'continued'],
                      ['known_at_window', 1],
                    ],
                  },
                ],
                'cursor-1',
              ),
            ),
          )
        }
        return Promise.resolve(
          json(
            page([
              {
                section: 'lineage',
                window_index: 2,
                row_key: 'lineage:second',
                fields: [
                  ['record_kind', 'transition'],
                  ['transition_kind', 'handoff'],
                  ['known_at_window', 2],
                ],
              },
            ]),
          ),
        )
      }),
    )
    const mounted = mountPanel()
    await settle()
    findTab(mounted.target, 'Lineage')?.click()
    await settle()
    expect(mounted.target.textContent).toContain('lineage:first')
    const more = [...mounted.target.querySelectorAll('button')].find(
      (button) => button.textContent?.trim() === 'Load more',
    )
    expect(more).toBeTruthy()
    more?.click()
    await settle()
    expect(mounted.target.textContent).toContain('lineage:second')
    expect(urls.some((url) => url.includes('cursor='))).toBe(true)
    expect(
      urls.every(
        (url) =>
          !url.includes('/lineage') || url.includes('publication_id='),
      ),
    ).toBe(true)
    mounted.cleanup()
  })

  it('renders disabled and empty states safely', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        Promise.resolve(
          json({ detail: 'scientific_institutions_disabled' }, 503),
        ),
      ),
    )
    const disabled = mountPanel()
    await settle()
    expect(disabled.target.textContent).toContain('disabled')
    disabled.cleanup()

    vi.stubGlobal(
      'fetch',
      vi.fn((url: string) => {
        if (url.endsWith('/scientific-institutions')) {
          return Promise.resolve(json(summary))
        }
        return Promise.resolve(json(page([])))
      }),
    )
    const empty = mountPanel()
    await settle()
    expect(empty.target.textContent).toContain('completely observed empty window')
    empty.cleanup()
  })
})
