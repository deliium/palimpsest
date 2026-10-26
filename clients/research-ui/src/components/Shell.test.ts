import { afterEach, describe, expect, it, vi } from 'vitest'
import Shell from '../components/Shell.svelte'
import { flushSync, render, type Mounted } from '../test/mount'

let mounted: Mounted | null = null

afterEach(() => {
  mounted?.cleanup()
  mounted = null
  vi.unstubAllGlobals()
})

function visit(url: string): void {
  window.history.replaceState(null, '', url)
}

function activeTab(): string | null {
  return (
    document.querySelector('.tabs button.active')?.textContent?.trim() ?? null
  )
}

function clickTab(label: string): void {
  const buttons = Array.from(document.querySelectorAll('.tabs button'))
  const target = buttons.find((button) => button.textContent?.trim() === label)
  expect(target).toBeDefined()
  target?.dispatchEvent(new MouseEvent('click', { bubbles: true }))
  flushSync()
}

describe('research ui shell navigation', () => {
  it('reflects the pathname view on first mount', () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')))
    visit('/research/runs/run-1/population?run_id=run-1&tick=5')
    mounted = render(Shell as never)
    expect(activeTab()).toBe('Population')
  })

  it('updates the URL and keeps time selection on tab change', () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')))
    visit('/research/runs/run-1/overview?run_id=run-1&tick=5')
    mounted = render(Shell as never)
    clickTab('Cohorts')
    expect(activeTab()).toBe('Cohorts')
    expect(window.location.search).toContain('run_id=run-1')
    expect(window.location.search).toContain('tick=5')
    expect(window.location.search).toContain('view=cohorts')
  })

  it('re-renders the active view on popstate', () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')))
    visit('/research/runs/run-1/overview?run_id=run-1&tick=5')
    mounted = render(Shell as never)
    visit('/research/runs/run-1/culture?run_id=run-1&tick=5')
    window.dispatchEvent(new PopStateEvent('popstate'))
    flushSync()
    expect(activeTab()).toBe('Culture')
  })

  it('recovers the same view after reload', () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')))
    visit('/research/runs/run-1/language?run_id=run-1&tick=9')
    mounted = render(Shell as never)
    expect(activeTab()).toBe('Language')
    mounted.cleanup()
    mounted = render(Shell as never)
    expect(activeTab()).toBe('Language')
  })

  it('shows an accessible route error for conflicting run ids', () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')))
    visit('/research/runs/run-1/overview?run_id=run-2')
    mounted = render(Shell as never)
    const alert = document.querySelector('[role="alert"]')
    expect(alert?.textContent).toContain('conflicting_run_id')
    expect(document.querySelector('.tabs')).toBeNull()
  })
})
