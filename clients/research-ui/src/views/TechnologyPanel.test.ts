import { afterEach, describe, expect, it, vi } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { emptyResearchSelection } from '../research/selection'
import { flushSync, render } from '../test/mount'
import TechnologyPanel from './TechnologyPanel.svelte'

vi.mock('cytoscape', () => ({
  default: () => ({ on: () => undefined, destroy: () => undefined }),
}))

const overlay = JSON.parse(
  readFileSync(
    resolve(
      process.cwd(),
      '../godot-observer/fixtures/protocol/civilization/overlay_technology.json',
    ),
    'utf8',
  ),
) as Record<string, unknown>

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
  await Promise.resolve()
  flushSync()
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('technology panel', () => {
  it('renders exact technology diffusion rows with grounding and denominators', async () => {
    const rows = overlay.rows as Array<Record<string, unknown>>
    const second = {
      ...rows[0],
      context: {
        ...(rows[0]?.context as Record<string, unknown>),
        row_id: 'technology:agent-b:knowledge-1',
        source_refs: [
          {
            source_kind: 'knowledge',
            source_id: 'knowledge-2',
            tick: 3,
            owner_id: 'agent-b',
          },
        ],
        anchors: [
          {
            kind: 'agent_at_evidence',
            location_id: 'loc-1',
            entity_id: 'entity-b',
            evidence_ref: {
              source_kind: 'knowledge',
              source_id: 'knowledge-2',
              tick: 3,
              owner_id: 'agent-b',
            },
            evidence_tick: 3,
          },
        ],
      },
      holder_id: 'agent-b',
      attribution: 'ambiguous',
      source_owner_id: 'agent-c',
      source_knowledge_id: 'knowledge-entry-c',
    }
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input)
        if (url.includes('/civilization/catalogue')) {
          return json({
            schema_version: 'observer-civilization-catalogue-v1',
            run_id: 'run-capture',
            publication: {
              publication_id: 'pub-1',
              digest: 'd'.repeat(64),
              policy_version: 'civilization-overlays.v1',
            },
            availability: 'available',
            boundaries: [{ boundary_tick: 4, revision: 4, coverage: {}, layers: ['technology'] }],
            next_cursor: null,
            truncated: false,
          })
        }
        if (url.includes('/civilization/overlays')) {
          return json({
            ...overlay,
            rows: [
              rows[0],
              second,
              { ...rows[0], holder_id: 'agent-d', knowledge_id: 'knowledge-1' },
            ],
          })
        }
        if (url.includes('/civilization/map')) {
          return json({
            schema_version: 'observer-civilization-map-v1',
            run_id: 'run-capture',
            rows: [{ location_id: 'loc-1', label: 'River camp' }],
          })
        }
        return json({}, 404)
      }),
    )
    const mounted = render(TechnologyPanel as never, {
      runId: 'run-capture',
      selection: emptyResearchSelection({
        runId: 'run-capture',
        view: 'technology',
        tick: 4,
      }),
      onSelectionChange: vi.fn(),
    })
    await settle()
    const diffusion = [...mounted.target.querySelectorAll('button')].find((button) =>
      button.textContent?.includes('Diffusion'),
    )
    diffusion?.click()
    await settle()
    await settle()
    expect(mounted.target.textContent).toContain('knowledge-1')
    expect(mounted.target.textContent).toContain('agent-a')
    expect(mounted.target.textContent).toContain('unknown')
    expect(mounted.target.textContent).toContain('ambiguous')
    expect(mounted.target.textContent).toContain('1 / 2')
    expect(mounted.target.textContent).toContain('Unlocated: no published anchor')
    expect(mounted.target.textContent).toContain('River camp')
    expect(mounted.target.textContent).toContain('evidence tick 3')
    // Repeated content keys with distinct holders remain separate rows.
    expect(
      [...mounted.target.querySelectorAll('tbody tr')].filter((row) =>
        row.textContent?.includes('knowledge-1'),
      ).length,
    ).toBeGreaterThanOrEqual(3)
    mounted.cleanup()
  })
})
