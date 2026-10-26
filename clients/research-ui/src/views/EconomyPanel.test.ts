import { afterEach, describe, expect, it, vi } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { emptyResearchSelection } from '../research/selection'
import { flushSync, render } from '../test/mount'
import EconomyPanel from './EconomyPanel.svelte'

const root = resolve(process.cwd(), '../godot-observer/fixtures/protocol/civilization')
function fixture(name: string): Record<string, unknown> {
  return JSON.parse(readFileSync(resolve(root, `${name}.json`), 'utf8')) as Record<string, unknown>
}
function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } })
}
async function settle(): Promise<void> {
  await Promise.resolve()
  await new Promise((r) => setTimeout(r, 0))
  await Promise.resolve()
  await Promise.resolve()
  flushSync()
}
afterEach(() => vi.unstubAllGlobals())

describe('economy panel', () => {
  it('renders completed exchange hubs without prices or wealth', async () => {
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      if (url.includes('/catalogue')) {
        return json({
          schema_version: 'observer-civilization-catalogue-v1',
          run_id: 'run-capture',
          publication: { publication_id: 'pub-1', digest: 'd'.repeat(64), policy_version: 'v1' },
          availability: 'available',
          boundaries: [{ boundary_tick: 4, revision: 4, coverage: {}, layers: ['trade'] }],
          next_cursor: null,
          truncated: false,
        })
      }
      if (url.includes('/overlays')) return json(fixture('overlay_trade'))
      if (url.includes('/metrics')) return json({}, 404)
      return json({}, 404)
    }))
    const mounted = render(EconomyPanel as never, {
      runId: 'run-capture',
      selection: emptyResearchSelection({ runId: 'run-capture', view: 'economy', tick: 4 }),
    })
    const load = [...mounted.target.querySelectorAll('button')].find((item) =>
      item.textContent?.includes('Load exchange window'),
    )
    load?.click()
    await settle()
    await settle()
    const overlay = fixture('overlay_trade')
    const first = (overlay.rows as Array<Record<string, unknown>>)[0]!
    expect(mounted.target.textContent).toContain(String(first.completed_exchange_count))
    expect(mounted.target.textContent).toContain('Completed exchange hub network')
    expect(mounted.target.textContent).toContain('No price')
    mounted.cleanup()
  })
})
