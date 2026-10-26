import { afterEach, describe, expect, it, vi } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { emptyResearchSelection } from '../research/selection'
import { flushSync, render } from '../test/mount'
import InstitutionsPanel from './InstitutionsPanel.svelte'

const source = readFileSync(
  resolve(process.cwd(), 'src/views/InstitutionsPanel.svelte'),
  'utf-8',
)

const fixture = JSON.parse(
  readFileSync(
    resolve(process.cwd(), '../godot-observer/fixtures/protocol/civilization/overlay_institutions.json'),
    'utf8',
  ),
) as Record<string, unknown>

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

describe('institutions view', () => {
  it('reads institution families through the generic metric endpoints', () => {
    expect(source).toContain('getMetricCatalog')
    expect(source).toContain('getMetricDocument')
    expect(source).toContain("'institution_emergence'")
    expect(source).toContain("'institutional_persistence'")
  })

  it('renders analytical results under research inference chrome', () => {
    expect(source).toContain('EpistemicBadge')
    expect(source).toContain('epistemic="research_inference"')
  })

  it('mounts timeline lanes and keeps office claims private', async () => {
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      if (url.includes('/catalogue')) {
        return json({
          schema_version: 'observer-civilization-catalogue-v1',
          run_id: 'run-capture',
          publication: { publication_id: 'pub-1', digest: 'd'.repeat(64), policy_version: 'v1' },
          availability: 'available',
          boundaries: [{ boundary_tick: 4, revision: 4, coverage: {}, layers: ['institutions'] }],
          next_cursor: null,
          truncated: false,
        })
      }
      if (url.includes('/overlays')) {
        const rows = (fixture.rows as Array<Record<string, unknown>>) ?? []
        return json({
          ...fixture,
          rows: [
            ...rows,
            {
              ...rows[0],
              kind: 'office',
              native_owner_id: 'agent-a',
              native_id: 'office-local',
              status: 'contested',
              context: {
                ...(rows[0]?.context as Record<string, unknown>),
                row_id: 'institutions:agent-a:office-local',
              },
            },
          ],
        })
      }
      if (url.includes('/metrics')) return json([], 200)
      return json({}, 404)
    }))
    const mounted = render(InstitutionsPanel as never, {
      runId: 'run-capture',
      selection: emptyResearchSelection({
        runId: 'run-capture',
        view: 'institutions',
        tick: 4,
        scopeOwnerId: 'agent-a',
      }),
      onSelectionChange: vi.fn(),
    })
    await settle()
    const load = [...mounted.target.querySelectorAll('button')].find((item) =>
      item.textContent?.includes('Load institution timeline'),
    )
    load?.click()
    await settle()
    expect(mounted.target.textContent).toContain('concept lane')
    expect(mounted.target.textContent).toContain('episode lane')
    expect(mounted.target.textContent).toContain('office lane')
    expect(mounted.target.textContent).toContain('No global current occupant')
    expect(mounted.target.textContent).toContain('No institution type registry')
    mounted.cleanup()
  })
})
