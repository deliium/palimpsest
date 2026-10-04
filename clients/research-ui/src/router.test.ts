import { describe, expect, it } from 'vitest'
import { parsePathname, resolveRoute } from './router'

describe('research ui router', () => {
  it('parses run list and run tabs', () => {
    expect(parsePathname('/research/').kind).toBe('run_list')
    expect(parsePathname('/research/runs/r1/graphs')).toEqual({
      kind: 'run',
      runId: 'r1',
      viewHint: 'graphs',
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
})
