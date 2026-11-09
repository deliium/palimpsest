import { afterEach, describe, expect, it, vi } from 'vitest'
import { emptyResearchSelection } from '../research/selection'
import { flushSync, render } from '../test/mount'
import InfrastructureNetworksPanel from './InfrastructureNetworksPanel.svelte'

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
  publication_id: 'infra-pub-0123456789abcdef',
  digest: 'a'.repeat(64),
  schema_version: 'infrastructure-networks-snapshot-v1',
  asset_count: 1,
  node_count: 1,
  edge_count: 1,
  operational_count: 1,
  damaged_count: 0,
  destroyed_count: 0,
  effects_active_count: 1,
  coverage: 'complete',
}

const asset = {
  asset_id: 'infra-0123456789abcdef0123456789ab',
  kind: 'bridge',
  topology: 'node',
  status: 'operational',
  integrity: 1,
  location_id: 'loc-a',
  endpoint_location_id: null,
  effects_active: true,
  created_tick: 1,
  last_maintained_tick: 1,
  ticks_since_maintained: 0,
  linked_project_id: 'proj-1',
  linked_structure_id: null,
}

const edge = {
  ...asset,
  asset_id: 'infra-edge0123456789abcdef01234567',
  topology: 'edge',
  endpoint_location_id: 'loc-b',
}

function stubFetch(override?: (path: string) => Response | null): void {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const path = new URL(String(input), 'http://local.test').pathname
      const custom = override?.(path) ?? null
      if (custom !== null) return custom
      if (path.endsWith('/infrastructure-networks')) return json(summary)
      if (path.endsWith('/infrastructure-networks/assets')) {
        return json({ items: [asset], next_cursor: null })
      }
      if (path.endsWith('/infrastructure-networks/edges')) {
        return json({ items: [edge], next_cursor: null })
      }
      if (path.endsWith('/infrastructure-networks/condition')) {
        return json({ items: [asset], next_cursor: null })
      }
      if (path.endsWith('/infrastructure-networks/effects')) {
        return json({ items: [asset], next_cursor: null })
      }
      if (path.endsWith('/infrastructure-networks/maintenance')) {
        return json({ items: [asset], next_cursor: null })
      }
      return json({ code: 'not_found' }, 404)
    }),
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('InfrastructureNetworksPanel', () => {
  it('renders ready objective sections without score chrome', async () => {
    stubFetch()
    const view = render(InfrastructureNetworksPanel as never, {
      runId: 'run-1',
      selection: emptyResearchSelection({
        runId: 'run-1',
        view: 'infrastructure-networks',
      }),
    })
    await settle()
    const text = (view.target.textContent ?? '').toLowerCase()
    expect(text).toContain('infrastructure networks')
    expect(text).toContain('assets')
    expect(text).toContain('edges')
    expect(text).toContain('condition')
    expect(text).toContain('effects')
    expect(text).toContain('maintenance')
    expect(text).toContain('objective')
    expect(text).not.toContain('score')
    expect(text).not.toContain('civilization')
    expect(text).not.toContain('composite')
    expect(text).not.toContain('winner')
    expect(view.target.querySelector('button,input,textarea,form')).toBeNull()
  })

  it('shows disabled state on 503', async () => {
    stubFetch(() => json({ code: 'infrastructure_networks_disabled' }, 503))
    const view = render(InfrastructureNetworksPanel as never, {
      runId: 'run-1',
      selection: emptyResearchSelection({
        runId: 'run-1',
        view: 'infrastructure-networks',
      }),
    })
    await settle()
    expect(view.target.textContent ?? '').toContain('disabled')
  })

  it('shows empty state on no rows', async () => {
    stubFetch((path) => {
      if (path.endsWith('/infrastructure-networks')) return json(summary)
      if (
        path.endsWith('/infrastructure-networks/assets') ||
        path.endsWith('/infrastructure-networks/edges') ||
        path.endsWith('/infrastructure-networks/condition') ||
        path.endsWith('/infrastructure-networks/effects') ||
        path.endsWith('/infrastructure-networks/maintenance')
      ) {
        return json({ items: [], next_cursor: null })
      }
      return null
    })
    const view = render(InfrastructureNetworksPanel as never, {
      runId: 'run-1',
      selection: emptyResearchSelection({
        runId: 'run-1',
        view: 'infrastructure-networks',
      }),
    })
    await settle()
    expect(view.target.textContent ?? '').toContain(
      'No infrastructure assets were published',
    )
  })
})
