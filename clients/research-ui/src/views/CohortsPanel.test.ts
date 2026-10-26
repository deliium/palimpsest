import { afterEach, describe, expect, it, vi } from 'vitest'
import { emptyResearchSelection } from '../research/selection'
import { flushSync, render } from '../test/mount'
import CohortsPanel from './CohortsPanel.svelte'

function json(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { 'content-type': 'application/json' },
  })
}

function envelope() {
  return {
    schema_version: 'observer-demographics-v1',
    run_id: 'run-1',
    requested_tick: 50,
    requested_through_sequence: null,
    resolved_tick: 50,
    revision: 2,
    evidence_class: 'objective',
    availability: 'available',
    reason_code: null,
    section: 'cohorts',
    selection_state: 'all',
    population: null,
    stage_counts_truncated: false,
    stage_rows: [],
    agents: [],
    cohorts: [
      { generation_index: 2, entry_tick: 10, cohort_id: 'cohort-a', admitted: 4, living: 2, dead: 2 },
      { generation_index: 3, entry_tick: 50, cohort_id: 'cohort-a', admitted: 0, living: 0, dead: 0 },
      { generation_index: 2, entry_tick: 20, cohort_id: 'cohort-b', admitted: 2, living: 2, dead: 0 },
    ],
    generations: [],
    next_after_agent_id: null,
    next_after_group_key: null,
    limit: 100,
  }
}

async function settle(): Promise<void> {
  await Promise.resolve()
  await new Promise((resolve) => setTimeout(resolve, 0))
  await Promise.resolve()
  flushSync()
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('cohorts panel', () => {
  it('selects the exact composite tuple and never merges reused IDs', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => json(envelope())),
    )
    const onSelectionChange = vi.fn()
    const mounted = render(CohortsPanel as never, {
      runId: 'run-1',
      selection: emptyResearchSelection({
        runId: 'run-1',
        view: 'cohorts',
        tick: 50,
        generationIndex: 2,
        cohort: { generationIndex: 2, entryTick: 10, cohortId: 'cohort-a' },
      }),
      onSelectionChange,
    })
    await settle()
    expect(mounted.target.textContent).toContain('Within-run cohort comparison')
    expect(mounted.target.textContent).toContain('cohort-a')
    expect(mounted.target.textContent).toContain('40 ticks')
    // Zero admitted cohort has no invented share.
    const rows = [...mounted.target.querySelectorAll('tbody tr')]
    const cohortRows = rows.filter((row) =>
      row.textContent?.includes('cohort-a'),
    )
    const zero = cohortRows.at(-1)
    expect(zero?.textContent).toContain('—')

    const target = zero
    target?.dispatchEvent(new MouseEvent('click', { bubbles: true }))
    flushSync()
    expect(onSelectionChange).toHaveBeenCalledWith({
      cohort: { generationIndex: 3, entryTick: 50, cohortId: 'cohort-a' },
    })
    mounted.cleanup()
  })
})
