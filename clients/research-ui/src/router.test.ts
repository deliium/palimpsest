import { describe, expect, it } from 'vitest'
import { parsePathname, resolveRoute } from './router'
import { RESEARCH_UI_VIEWS } from './research/selection'

describe('research ui router', () => {
  it('parses run list and run tabs', () => {
    expect(parsePathname('/research/').kind).toBe('run_list')
    expect(parsePathname('/research/runs/r1/graphs')).toEqual({
      kind: 'run',
      runId: 'r1',
      viewHint: 'graphs',
    })
    expect(parsePathname('/research/runs/r1/societies')).toEqual({
      kind: 'run',
      runId: 'r1',
      viewHint: 'societies',
    })
  })

  it('applies query deep link onto run route', () => {
    const route = resolveRoute(
      '/research/',
      '?run_id=run-9&view=traces&tick=4&agent_id=alice',
    )
    expect(route.kind).toBe('run')
    if (route.kind === 'run') {
      expect(route.runId).toBe('run-9')
      expect(route.view).toBe('traces')
      expect(route.deepLink.tick).toBe(4)
      expect(route.deepLink.agentId).toBe('alice')
    }
  })

  it('strips secret keys before applying deep links', () => {
    const route = resolveRoute('/research/', '?run_id=run-1&token=nope')
    expect(route.kind).toBe('run')
    if (route.kind === 'run') {
      expect(route.runId).toBe('run-1')
    }
  })

  it('keeps a pathname-only view when the query has no view', () => {
    const route = resolveRoute('/research/runs/run-1/population', '?run_id=run-1')
    expect(route.kind).toBe('run')
    if (route.kind === 'run') {
      expect(route.view).toBe('population')
    }
  })

  it('lets an explicit valid query view override the pathname view', () => {
    const route = resolveRoute(
      '/research/runs/run-1/graphs',
      '?run_id=run-1&view=culture',
    )
    expect(route.kind).toBe('run')
    if (route.kind === 'run') {
      expect(route.view).toBe('culture')
    }
  })

  it('rejects a conflicting pathname and query run id', () => {
    const route = resolveRoute(
      '/research/runs/run-1/overview',
      '?run_id=run-2',
    )
    expect(route).toEqual({ kind: 'route_error', code: 'conflicting_run_id' })
  })

  it('does not silently clear malformed selectors', () => {
    const route = resolveRoute('/research/runs/run-1/overview', '?run_id=run-1&tick=nope')
    expect(route).toEqual({ kind: 'route_error', code: 'invalid_tick' })
  })

  it('returns not_found for malformed percent escapes', () => {
    expect(parsePathname('/research/runs/%E0%A4%A')).toEqual({ kind: 'not_found' })
  })

  it('resolves every new run view', () => {
    for (const view of RESEARCH_UI_VIEWS) {
      if (view === 'matrix') {
        continue
      }
      const route = resolveRoute(
        `/research/runs/run-1/${view}`,
        `?run_id=run-1&view=${view}`,
      )
      expect(route.kind).toBe('run')
      if (route.kind === 'run') {
        expect(route.view).toBe(view)
      }
    }
  })

  it('preserves selection on tab navigation', () => {
    const route = resolveRoute(
      '/research/runs/run-1/overview',
      '?run_id=run-1&tick=4&generation_index=2&cohort_generation_index=3&cohort_entry_tick=50&cohort_id=cohort-a',
    )
    expect(route.kind).toBe('run')
    if (route.kind === 'run') {
      const switched = resolveRoute(
        '/research/runs/run-1/population',
        '?run_id=run-1&tick=4&generation_index=2&cohort_generation_index=3&cohort_entry_tick=50&cohort_id=cohort-a',
      )
      expect(switched.kind).toBe('run')
      if (switched.kind === 'run') {
        expect(switched.selection.tick).toBe(4)
        expect(switched.selection.generationIndex).toBe(2)
        expect(switched.selection.cohort?.cohortId).toBe('cohort-a')
        expect(route.selection.view).toBe('overview')
      }
    }
  })
})
