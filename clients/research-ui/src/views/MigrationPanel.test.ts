import { afterEach, describe, expect, it, vi } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { emptyResearchSelection } from '../research/selection'
import { flushSync, render } from '../test/mount'
import MigrationPanel from './MigrationPanel.svelte'

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

describe('migration panel', () => {
  it('renders actual journey phases, routes, topology and unlocated anchors', async () => {
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      if (url.includes('/catalogue')) {
        return json({
          schema_version: 'observer-civilization-catalogue-v1',
          run_id: 'run-capture',
          publication: { publication_id: 'pub-1', digest: 'd'.repeat(64), policy_version: 'v1' },
          availability: 'available',
          boundaries: [{ boundary_tick: 4, revision: 4, coverage: {}, layers: ['migration'] }],
          next_cursor: null,
          truncated: false,
        })
      }
      if (url.includes('/overlays')) return json(fixture('overlay_migration'))
      if (url.includes('section=locations')) return json(fixture('map_locations'))
      if (url.includes('section=regions')) return json(fixture('map_regions'))
      if (url.includes('section=routes')) return json(fixture('map_routes'))
      return json({}, 404)
    }))
    const mounted = render(MigrationPanel as never, {
      runId: 'run-capture',
      selection: emptyResearchSelection({ runId: 'run-capture', view: 'migration', tick: 4 }),
    })
    const load = [...mounted.target.querySelectorAll('button')].find((item) =>
      item.textContent?.includes('Load migration window'),
    )
    load?.click()
    await settle()
    await settle()
    const overlay = fixture('overlay_migration')
    const first = (overlay.rows as Array<Record<string, unknown>>)[0]!
    expect(mounted.target.textContent).toContain(String(first.route_id))
    expect(mounted.target.textContent).toContain(String(first.phase))
    expect(mounted.target.textContent).toContain('Routes, regions and locations')
    expect(mounted.target.textContent).toContain('not citizenship')
    mounted.cleanup()
  })
})
