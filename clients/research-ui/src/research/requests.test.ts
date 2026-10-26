import { afterEach, describe, expect, it, vi } from 'vitest'
import { saveCredentials } from '../auth/credentials'
import {
  BoundedRequestPool,
  ResearchScopeController,
  StaleResearchResponse,
  scopeKey,
} from './requests'

afterEach(() => {
  saveCredentials({
    simulation_control: '',
    objective_inspection: '',
    agent_visible: '',
    subjective_debug: '',
  })
})

function scope(view: string, tick = 0) {
  return {
    runId: 'run-1',
    view,
    tick,
    evidenceClass: null,
    ownerId: null,
    publicationId: null,
  }
}

describe('research request scope', () => {
  it('rejects A to B to A contamination after every await', async () => {
    const controller = new ResearchScopeController(scope('population'))
    const deferred: { resolve?: (value: string) => void } = {}
    const tokenA = controller.begin()
    const promiseA = new Promise<string>((resolve) => {
      deferred.resolve = resolve
    })

    controller.setScope(scope('lineage'))
    const tokenB = controller.begin()
    controller.setScope(scope('population'))
    const tokenC = controller.begin()

    deferred.resolve?.('A-result')
    await expect(
      promiseA.then((value) => controller.accept(tokenA, value)),
    ).rejects.toBeInstanceOf(StaleResearchResponse)
    expect(controller.isCurrent(tokenB)).toBe(false)
    expect(controller.isCurrent(tokenC)).toBe(true)
    expect(controller.accept(tokenC, 'C-result')).toBe('C-result')
  })

  it('cancels the signal on scope change and credential rotation', () => {
    const controller = new ResearchScopeController(scope('population'))
    const first = controller.begin()
    controller.setScope(scope('culture'))
    expect(first.signal.aborted).toBe(true)
    const second = controller.begin()
    saveCredentials({
      simulation_control: '',
      objective_inspection: 'new',
      agent_visible: '',
      subjective_debug: '',
    })
    expect(second.signal.aborted).toBe(true)
    expect(controller.isCurrent(second)).toBe(false)
  })

  it('aborts outstanding work on unmount', () => {
    const controller = new ResearchScopeController(scope('population'))
    const token = controller.begin()
    controller.dispose()
    expect(token.signal.aborted).toBe(true)
    expect(controller.isCurrent(token)).toBe(false)
  })

  it('resets listeners and keys filters deterministically', () => {
    const controller = new ResearchScopeController({
      ...scope('lineage'),
      filters: { b: 2, a: 1 },
    })
    let resets = 0
    controller.onReset(() => {
      resets += 1
    })
    controller.reset()
    expect(resets).toBe(1)
    expect(
      scopeKey({
        ...scope('lineage'),
        filters: { a: 1, b: 2 },
      }),
    ).toBe(controller.key)
  })

  it('bounds concurrent loads to four', async () => {
    const pool = new BoundedRequestPool(4)
    let active = 0
    let peak = 0
    const resolvers: Array<() => void> = []
    const run = () =>
      pool.run(async () => {
        active += 1
        peak = Math.max(peak, active)
        await new Promise<void>((resolve) => resolvers.push(resolve))
        active -= 1
        return true
      })
    const all = [run(), run(), run(), run(), run(), run()]
    await Promise.resolve()
    expect(pool.inFlight).toBe(4)
    resolvers.shift()?.()
    await Promise.resolve()
    resolvers.shift()?.()
    await Promise.resolve()
    while (resolvers.length > 0) {
      resolvers.shift()?.()
      await Promise.resolve()
    }
    await Promise.all(all)
    expect(peak).toBeLessThanOrEqual(4)
  })
})
