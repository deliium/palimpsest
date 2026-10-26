import { describe, expect, it, vi } from 'vitest'
import { flushSync, render } from '../../test/mount'
import SeriesChart from './SeriesChart.svelte'

const series = [
  {
    id: 'living',
    label: 'Living',
    evidenceClass: 'objective_world' as const,
    ownerId: null,
    unit: 'agents',
    coverage: 1,
    sourceRef: 'observer-demographics-v1',
    points: [
      { tick: 0, value: 2 },
      { tick: 10, value: null },
      { tick: 20, value: 4 },
    ],
  },
]

describe('series chart', () => {
  it('renders gaps without connecting lines and mirrors data in a table', () => {
    const mounted = render(SeriesChart as never, {
      title: 'Population',
      description: 'Objective totals',
      series,
    })
    const paths = mounted.target.querySelectorAll('path.series')
    expect(paths).toHaveLength(2)
    const rows = mounted.target.querySelectorAll('tbody tr')
    expect(rows).toHaveLength(3)
    expect(rows[1]?.textContent).toContain('—')
    expect(mounted.target.textContent).toContain('Objective world')
    expect(mounted.target.textContent).toContain('agents')
    mounted.cleanup()
  })

  it('selects points by mouse and keyboard', () => {
    const onPointSelect = vi.fn()
    const mounted = render(SeriesChart as never, {
      title: 'Population',
      description: 'Objective totals',
      series,
      onPointSelect,
    })
    const circles = mounted.target.querySelectorAll('circle')
    circles[0]?.dispatchEvent(new MouseEvent('click', { bubbles: true }))
    flushSync()
    expect(onPointSelect).toHaveBeenCalledWith(0)
    circles[1]?.dispatchEvent(
      new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }),
    )
    flushSync()
    expect(onPointSelect).toHaveBeenCalledWith(20)
    mounted.cleanup()
  })
})
