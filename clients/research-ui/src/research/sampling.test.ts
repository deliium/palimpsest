import { describe, expect, it } from 'vitest'
import {
  MarkerHighWater,
  defaultSamplingRange,
  pinHighWater,
  sampleBoundaries,
} from './sampling'

const markers = Array.from({ length: 60 }, (_, index) => ({
  generationIndex: index,
  seekTick: index * 10,
}))

describe('bounded history sampling', () => {
  it('defaults to the selected boundary only', () => {
    expect(defaultSamplingRange(7)).toEqual({ fromTick: 7, toTick: 7 })
  })

  it('samples deterministically with endpoints and explicit omission count', () => {
    const range = { fromTick: 0, toTick: 600 }
    const first = sampleBoundaries(markers, range, 32)
    const second = sampleBoundaries(markers, range, 32)
    expect(first.ticks).toEqual(second.ticks)
    expect(first.ticks.length).toBeLessThanOrEqual(32)
    expect(first.ticks[0]).toBe(0)
    expect(first.ticks.at(-1)).toBe(600)
    expect(first.sampled).toBe(true)
    expect(first.omittedCount).toBeGreaterThan(0)
  })

  it('keeps all boundaries when they fit', () => {
    const result = sampleBoundaries(markers.slice(0, 5), { fromTick: 0, toTick: 40 }, 32)
    expect(result.ticks).toEqual([0, 10, 20, 30, 40])
    expect(result.sampled).toBe(false)
    expect(result.omittedCount).toBe(0)
  })

  it('pins high water independently from the view tick', () => {
    const highWater = new MarkerHighWater()
    const run = { tick: 0, latest_tick: 50 }
    expect(pinHighWater(run)).toBe(50)
    const first = highWater.observe('run-1', run, 1, 0)
    expect(first.highWater).toBe(50)
    expect(highWater.acceptsContinuation(50)).toBe(true)
    // Viewing tick 0 and stepping to a later generation/back never lowers H.
    const later = highWater.observe('run-1', { tick: 40, latest_tick: 50 }, 1, 0)
    expect(later.highWater).toBe(50)
    const back = highWater.observe('run-1', { tick: 0, latest_tick: 50 }, 1, 0)
    expect(back.highWater).toBe(50)
    expect(highWater.acceptsContinuation(40)).toBe(false)
  })

  it('advances H only on explicit refresh and resets on credentials', () => {
    const highWater = new MarkerHighWater()
    highWater.observe('run-1', { tick: 0, latest_tick: 50 }, 1, 0)
    const unchanged = highWater.observe('run-1', { tick: 0, latest_tick: 80 }, 1, 0)
    expect(unchanged.highWater).toBe(50)
    const refreshed = highWater.refresh('run-1', { tick: 0, latest_tick: 80 }, 1, 0)
    expect(refreshed.changed).toBe(true)
    expect(refreshed.highWater).toBe(80)
    expect(highWater.acceptsContinuation(50)).toBe(false)
    expect(highWater.acceptsContinuation(80)).toBe(true)

    highWater.observe('run-1', { tick: 0, latest_tick: 80 }, 1, 1)
    expect(highWater.cacheKey).toContain(':1')
  })
})
