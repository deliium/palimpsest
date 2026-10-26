import { afterEach, describe, expect, it, vi } from 'vitest'
import { emptyResearchSelection } from '../research/selection'
import { flushSync, render } from '../test/mount'
import CulturePanel from './CulturePanel.svelte'

function json(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { 'content-type': 'application/json' },
  })
}

function page(runId = 'run-1') {
  return {
    schema_version: 'research-cultural-evidence-page-v1',
    run_id: runId,
    matrix_id: 'm1',
    cell_id: 'cell-a',
    section: 'traits',
    artifact_digest: 'a'.repeat(64),
    source_revision: 'rev-1',
    binding_state: 'legacy_unverified',
    requested_window: { from_tick: 0, to_tick: 10 },
    capture_status: { active: true, failed: false },
    gaps: [{ tick: 3 }],
    rows: [
      { boundary_tick: 0, owner_id: 'a', dimension: 'belief', content_digest: 'x' },
      { boundary_tick: 0, owner_id: 'b', dimension: 'belief', content_digest: 'y' },
      { boundary_tick: 5, owner_id: 'a', dimension: 'vocabulary', content_digest: 'v' },
    ],
    next_cursor: null,
    truncated: false,
    coverage: 1,
  }
}

async function settle(): Promise<void> {
  await Promise.resolve()
  await new Promise((resolve) => setTimeout(resolve, 0))
  await Promise.resolve()
  flushSync()
}

afterEach(() => vi.unstubAllGlobals())

describe('culture panel', () => {
  it('renders dimensions, binding and gaps from a real-shaped page', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => json(page())))
    const mounted = render(CulturePanel as never, {
      runId: 'run-1',
      selection: emptyResearchSelection({ runId: 'run-1', view: 'culture', tick: 5 }),
    })
    const inputs = mounted.target.querySelectorAll('input')
    inputs[0]!.value = 'm1'
    inputs[0]!.dispatchEvent(new Event('input', { bubbles: true }))
    inputs[1]!.value = 'cell-a'
    inputs[1]!.dispatchEvent(new Event('input', { bubbles: true }))
    const button = [...mounted.target.querySelectorAll('button')].find((item) =>
      item.textContent?.includes('Load captured inventory'),
    )
    button?.click()
    await settle()
    expect(mounted.target.textContent).toContain('belief')
    expect(mounted.target.textContent).toContain('vocabulary')
    expect(mounted.target.textContent).toContain('legacy_unverified')
    expect(mounted.target.textContent).toContain('Gaps')
    mounted.cleanup()
  })

  it('rejects a matrix/cell whose run does not match the selected run', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => json(page('run-other'))))
    const mounted = render(CulturePanel as never, {
      runId: 'run-1',
      selection: emptyResearchSelection({ runId: 'run-1', view: 'culture', tick: 5 }),
    })
    const inputs = mounted.target.querySelectorAll('input')
    inputs[0]!.value = 'm1'
    inputs[0]!.dispatchEvent(new Event('input', { bubbles: true }))
    inputs[1]!.value = 'cell-a'
    inputs[1]!.dispatchEvent(new Event('input', { bubbles: true }))
    const button = [...mounted.target.querySelectorAll('button')].find((item) =>
      item.textContent?.includes('Load captured inventory'),
    )
    button?.click()
    await settle()
    expect(mounted.target.textContent).toContain('matrix_run_mismatch')
    mounted.cleanup()
  })
})
