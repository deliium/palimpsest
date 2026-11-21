import { afterEach, describe, expect, it, vi } from 'vitest'
import { saveCredentials } from '../auth/credentials'
import {
  getScienceDiffusionPage,
  getScienceDiffusionSummary,
} from '../api/scienceDiffusion'
import { emptyResearchSelection } from '../research/selection'
import { flushSync, render } from '../test/mount'
import ScienceDiffusionPanel from './ScienceDiffusionPanel.svelte'

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
  publication_id: 'sdf-0000000000000000',
  snapshot_digest: 'a'.repeat(64),
  schema_version: 'science-diffusion-snapshot-v1',
  policy_version: 'science-diffusion.v1',
  input_revision: 'rev-1',
  boundary_tick: 64,
  counts: { coverage: 2, versions: 1, transmissions: 1, changes: 0, genealogy: 0 },
  publications: ['sdf-0000000000000000'],
}

function page(rows: unknown[], next: string | null = null) {
  return {
    run_id: 'run-1',
    publication_id: 'sdf-0000000000000000',
    snapshot_digest: 'a'.repeat(64),
    section: 'coverage',
    rows,
    next_cursor: next,
    truncated: next !== null,
  }
}

function mountPanel() {
  return render(ScienceDiffusionPanel as never, {
    runId: 'run-1',
    selection: emptyResearchSelection({
      runId: 'run-1',
      view: 'science-diffusion',
    }),
  })
}

afterEach(() => {
  vi.unstubAllGlobals()
  saveCredentials({
    simulation_control: '',
    objective_inspection: '',
    agent_visible: '',
    subjective_debug: '',
  })
})

describe('ScienceDiffusionPanel', () => {
  it('renders coverage, transmission and genealogy labels separately', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn((url: string) => {
        if (url.endsWith('/science-diffusion')) {
          return Promise.resolve(json(summary))
        }
        if (url.includes('/transmissions')) {
          return Promise.resolve(
            json(
              page([
                {
                  row_key: 'sdfo:1',
                  stage: 'adopted',
                  from_version_key: 'sdf:a',
                  to_version_key: 'sdf:b',
                },
              ]),
            ),
          )
        }
        if (url.includes('/genealogy')) {
          return Promise.resolve(
            json(
              page([
                {
                  row_key: 'sdfo:2',
                  transmission_key: 'sdfo:1',
                  v3_node_key: 'sdfo:v3',
                  origin: 'teaching',
                  relation: 'teaching_uptake',
                  ambiguity: 'exact',
                },
              ]),
            ),
          )
        }
        return Promise.resolve(
          json(
            page([
              {
                row_key: 'coverage:0:32',
                lane: 'science',
                state: 'complete',
                observed: 0,
              },
            ]),
          ),
        )
      }),
    )
    const panel = mountPanel()
    await settle()
    expect(panel.target.textContent).toContain('coverage: complete')
    expect(panel.target.textContent).toContain('Delivery is not uptake')
    flushSync()
  })

  it('keeps credentials in headers, not URLs', async () => {
    saveCredentials({
      simulation_control: '',
      objective_inspection: '',
      agent_visible: '',
      subjective_debug: 'secret-token',
    })
    const fetchMock = vi.fn(() => Promise.resolve(json(summary)))
    vi.stubGlobal('fetch', fetchMock)
    await getScienceDiffusionSummary('run-1')
    await getScienceDiffusionPage('run-1', 'coverage')
    for (const call of fetchMock.mock.calls) {
      const [url, init] = call as unknown as [string, RequestInit]
      expect(url).not.toContain('secret-token')
      expect((init.headers as Record<string, string>)['x-palimpsest-token']).toBe(
        'secret-token',
      )
    }
  })

  it('offers a pinned reload after cursor expiration', async () => {
    let pages = 0
    vi.stubGlobal(
      'fetch',
      vi.fn((url: string) => {
        if (url.endsWith('/science-diffusion')) {
          return Promise.resolve(json(summary))
        }
        pages += 1
        if (pages === 1) {
          return Promise.resolve(
            json(page([{ row_key: 'coverage:0:32', state: 'complete' }], 'next')),
          )
        }
        return Promise.resolve(
          json({ detail: 'science_diffusion_cursor_expired' }, 410),
        )
      }),
    )
    const panel = mountPanel()
    await settle()
    const next = [...panel.target.querySelectorAll('button')].find(
      (button) => button.textContent?.trim() === 'Next page',
    )
    expect(next).toBeTruthy()
    next?.dispatchEvent(new MouseEvent('click', { bubbles: true }))
    await settle()
    expect(panel.target.textContent).toContain('cursor expired')
    expect(panel.target.textContent).toContain('Reload publication')
  })
})
