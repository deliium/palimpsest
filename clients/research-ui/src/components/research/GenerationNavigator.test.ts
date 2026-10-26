import { describe, expect, it, vi } from 'vitest'
import { flushSync, render } from '../../test/mount'
import { emptyResearchSelection } from '../../research/selection'
import GenerationNavigator from './GenerationNavigator.svelte'

const markers = [
  {
    generation_index: 0,
    first_entry_tick: 0,
    seek_tick: 0,
    admitted_count: 5,
    label_code: 'founders' as const,
  },
  {
    generation_index: 1,
    first_entry_tick: 10,
    seek_tick: 10,
    admitted_count: 2,
    label_code: 'generation_first_admission' as const,
  },
  {
    generation_index: 2,
    first_entry_tick: 20,
    seek_tick: 20,
    admitted_count: 2,
    label_code: 'generation_first_admission' as const,
  },
]

describe('generation navigator', () => {
  it('steps through actual admission markers and keeps high water fixed', () => {
    const onSelectionChange = vi.fn()
    const mounted = render(GenerationNavigator as never, {
      selection: emptyResearchSelection({
        runId: 'run-1',
        view: 'population',
        tick: 10,
        generationIndex: 1,
      }),
      markers,
      highWater: 40,
      markerStatus: 'available',
      onSelectionChange,
    })
    const buttons = [...mounted.target.querySelectorAll('button')]
    buttons.find((button) => button.textContent?.includes('Next'))?.click()
    flushSync()
    expect(onSelectionChange).toHaveBeenCalledWith({
      generationIndex: 2,
      tick: 20,
      eventId: null,
      sequence: null,
    })
    buttons.find((button) => button.textContent?.includes('Previous'))?.click()
    flushSync()
    expect(onSelectionChange).toHaveBeenCalledWith({
      generationIndex: 0,
      tick: 0,
      eventId: null,
      sequence: null,
    })
    expect(mounted.target.textContent).toContain('40')
    expect(mounted.target.textContent).toContain('view tick 10')
    mounted.cleanup()
  })

  it('shows a conflict without rewriting the explicit tick', () => {
    const mounted = render(GenerationNavigator as never, {
      selection: emptyResearchSelection({
        runId: 'run-1',
        view: 'population',
        tick: 12,
        generationIndex: 1,
      }),
      markers,
      highWater: 40,
      markerStatus: 'available',
      onSelectionChange: vi.fn(),
    })
    expect(mounted.target.textContent).toContain('generation_tick_mismatch')
    mounted.cleanup()
  })

  it('disables generation selection when discovery is unavailable', () => {
    const mounted = render(GenerationNavigator as never, {
      selection: emptyResearchSelection({ runId: 'run-1', view: 'population', tick: 0 }),
      markers: [],
      highWater: null,
      markerStatus: 'unavailable',
      markerReason: 'lifecycle_disabled',
      onSelectionChange: vi.fn(),
    })
    const select = mounted.target.querySelector('select')
    expect(select?.hasAttribute('disabled')).toBe(true)
    expect(mounted.target.textContent).toContain('Tick navigation remains usable')
    mounted.cleanup()
  })

  it('clears an event prefix explicitly', () => {
    const onSelectionChange = vi.fn()
    const mounted = render(GenerationNavigator as never, {
      selection: emptyResearchSelection({
        runId: 'run-1',
        view: 'population',
        tick: 5,
        sequence: 2,
        eventId: 'evt-1',
      }),
      markers,
      highWater: 40,
      markerStatus: 'available',
      onSelectionChange,
    })
    const clear = [...mounted.target.querySelectorAll('button')].find((button) =>
      button.textContent?.includes('Move to full boundary'),
    )
    clear?.click()
    flushSync()
    expect(onSelectionChange).toHaveBeenCalledWith({
      eventId: null,
      sequence: null,
      tick: 5,
    })
    mounted.cleanup()
  })
})
