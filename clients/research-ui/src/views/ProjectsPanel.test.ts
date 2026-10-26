import { afterEach, describe, expect, it, vi } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { emptyResearchSelection } from '../research/selection'
import { flushSync, render } from '../test/mount'
import ProjectsPanel from './ProjectsPanel.svelte'

const fixture = JSON.parse(
  readFileSync(
    resolve(process.cwd(), '../godot-observer/fixtures/protocol/civilization/map_projects.json'),
    'utf8',
  ),
) as Record<string, unknown>

function json(body: unknown): Response {
  return new Response(JSON.stringify(body), { status: 200, headers: { 'content-type': 'application/json' } })
}
async function settle(): Promise<void> {
  await Promise.resolve()
  await new Promise((r) => setTimeout(r, 0))
  await Promise.resolve()
  await Promise.resolve()
  flushSync()
}
afterEach(() => vi.unstubAllGlobals())

describe('projects panel', () => {
  it('shows objective progress, counters and retained receipts', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => json(fixture)))
    const mounted = render(ProjectsPanel as never, {
      runId: 'run-capture',
      selection: emptyResearchSelection({ runId: 'run-capture', view: 'projects', tick: 4 }),
    })
    const load = [...mounted.target.querySelectorAll('button')].find((item) =>
      item.textContent?.includes('Load project boundary'),
    )
    load?.click()
    await settle()
    const first = ((fixture.rows as Array<Record<string, unknown>>)[0] ?? {}) as Record<string, unknown>
    expect(mounted.target.textContent).toContain(String(first.project_id))
    expect(mounted.target.textContent).toContain(`${first.labor_progress} / ${first.labor_required}`)
    expect(mounted.target.textContent).toContain('Accepted count')
    expect(mounted.target.textContent).toContain('not social rank')
    mounted.cleanup()
  })
})
