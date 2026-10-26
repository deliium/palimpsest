import { afterEach, describe, expect, it, vi } from 'vitest'
import { emptyResearchSelection } from '../research/selection'
import { flushSync, render } from '../test/mount'
import LanguagePanel from './LanguagePanel.svelte'

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } })
}

async function settle(): Promise<void> {
  await Promise.resolve()
  await new Promise((resolve) => setTimeout(resolve, 0))
  await Promise.resolve()
  flushSync()
}

afterEach(() => vi.unstubAllGlobals())

describe('language panel', () => {
  it('renders retained semantic transitions at the checkpoint', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input)
        if (url.includes('/semantic-history')) {
          return json({
            schema_version: 'observer-semantic-history-v1',
            run_id: 'run-1',
            agent_id: 'agent-a',
            source: 'label',
            checkpoint_tick: 9,
            retained_only: true,
            prefix_complete: false,
            availability: 'available',
            reason: null,
            terms: [],
            rows: [
              { ordinal: 1, tick: 2, trigger: 'promoted', term_source: 'label', term_digest: 't', local_id: 'b', referent_kind: 'entity', referent_digest: 'r1', associated_digests: [], confidence: 0.4 },
              { ordinal: 2, tick: 6, trigger: 'shifted', term_source: 'label', term_digest: 't', local_id: 'b', referent_kind: 'entity', referent_digest: 'r2', associated_digests: [], confidence: 0.8 },
            ],
            next_cursor: null,
            count: 2,
          })
        }
        return json({}, 404)
      }),
    )
    const mounted = render(LanguagePanel as never, {
      runId: 'run-1',
      selection: emptyResearchSelection({ runId: 'run-1', view: 'language', tick: 9 }),
    })
    const semantics = [...mounted.target.querySelectorAll('button')].find((item) =>
      item.textContent?.includes('Semantics'),
    )
    semantics?.click()
    flushSync()
    const inputs = mounted.target.querySelectorAll('input')
    const owner = inputs[2]
    if (owner !== undefined) {
      owner.value = 'agent-a'
      owner.dispatchEvent(new Event('input', { bubbles: true }))
    }
    const load = [...mounted.target.querySelectorAll('button')].find((item) =>
      item.textContent?.includes('Load semantics'),
    )
    load?.click()
    await settle()
    expect(mounted.target.textContent).toContain('Checkpoint tick 9')
    expect(mounted.target.textContent).toContain('shifted')
    expect(mounted.target.textContent).toContain('retained-only')
    mounted.cleanup()
  })
})
