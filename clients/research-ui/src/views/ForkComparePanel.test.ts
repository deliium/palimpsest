import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { saveCredentials } from '../auth/credentials'
import { flushSync, render } from '../test/mount'
import ForkComparePanel from './ForkComparePanel.svelte'

type RecordedCall = { url: string; init: RequestInit }

const calls: RecordedCall[] = []
const SECRET = 'secret-inspection-token'

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  })
}

function child(
  childRunId: string,
  interventionKind: string,
  forkTick = 12,
): Record<string, unknown> {
  return {
    child_run_id: childRunId,
    parent_run_id: 'run-parent',
    fork_tick: forkTick,
    intervention_kind: interventionKind,
    intervention_summary: `controlled ${interventionKind}`,
    branch_id: `branch-${childRunId}`,
  }
}

function compareResult(): Record<string, unknown> {
  return {
    left_run_id: 'child-a',
    right_run_id: 'child-b',
    fork_tick: 12,
    prefix_equivalent: true,
    diverge_tick: 15,
    diverge_sequence: 44,
    reason_code: null,
    left_post_fork_trajectory_hash: 'a'.repeat(64),
    right_post_fork_trajectory_hash: 'b'.repeat(64),
    event_kind_counts: {
      left: { Talk: 2 },
      right: { Talk: 3, Death: 1 },
    },
  }
}

async function settle(): Promise<void> {
  await Promise.resolve()
  await new Promise((resolve) => setTimeout(resolve, 0))
  await Promise.resolve()
  await Promise.resolve()
  flushSync()
}

function installFetch(children: unknown[] = [
  child('child-a', 'teaching'),
  child('child-b', 'migration'),
  child('child-c', 'office_succession'),
]): void {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      calls.push({ url, init: init ?? {} })
      if (url.includes('/branches/compare')) {
        return json(compareResult())
      }
      if (url.includes('/branches')) {
        return json({ items: children, next_cursor: null, count: children.length })
      }
      if (url.endsWith('/branch')) {
        return json({
          child_run_id: 'run-parent',
          parent_run_id: 'run-root',
          fork_tick: 12,
          intervention_kind: 'founder_event',
          intervention_summary: 'controlled founder event',
          branch_id: 'branch-parent',
        })
      }
      return json({}, 404)
    }),
  )
}

function buttonByText(text: string): HTMLButtonElement | undefined {
  return [...document.querySelectorAll('button')].find(
    (button) => button.textContent?.trim() === text,
  ) as HTMLButtonElement | undefined
}

function linkByText(text: string): HTMLAnchorElement | undefined {
  return [...document.querySelectorAll('a')].find((link) =>
    link.textContent?.includes(text),
  ) as HTMLAnchorElement | undefined
}

function mountPanel(runId = 'run-parent'): ReturnType<typeof render> {
  return render(ForkComparePanel as never, {
    runId,
    deepLink: {
      runId,
      tick: null,
      eventId: null,
      sequence: null,
      agentId: null,
      view: 'compare',
    },
  })
}

beforeEach(() => {
  saveCredentials({
    simulation_control: '',
    objective_inspection: SECRET,
    agent_visible: '',
    subjective_debug: '',
  })
  window.history.replaceState(null, '', '/research/')
})

afterEach(() => {
  saveCredentials({
    simulation_control: '',
    objective_inspection: '',
    agent_visible: '',
    subjective_debug: '',
  })
  vi.unstubAllGlobals()
  calls.length = 0
})

describe('fork compare panel', () => {
  it('lists real child lineage, compares two children and shows coverage', async () => {
    installFetch()
    const mounted = mountPanel()
    await settle()

    expect(mounted.target.textContent).toContain('Child runs at this fork')
    expect(mounted.target.textContent).toContain('child-a')
    expect(mounted.target.textContent).toContain('child-b')
    expect(mounted.target.textContent).toContain('child-c')
    expect(mounted.target.textContent).toContain('fork tick 12')

    buttonByText('child-a')?.click()
    buttonByText('child-b')?.click()
    flushSync()
    const compareButton = buttonByText('Compare selected children')
    expect(compareButton?.disabled).toBe(false)
    compareButton?.click()
    await settle()

    const compareCall = calls.find((call) => call.url.includes('/branches/compare'))
    expect(compareCall).toBeDefined()
    expect(JSON.parse(String(compareCall?.init.body))).toEqual({
      left_run_id: 'child-a',
      right_run_id: 'child-b',
      include_event_kind_counts: true,
    })
    expect(
      (compareCall?.init.headers as Record<string, string>)['x-palimpsest-token'],
    ).toBe(SECRET)
    expect(compareCall?.url).not.toContain(SECRET)

    expect(mounted.target.textContent).toContain('prefix coverage')
    expect(mounted.target.textContent).toContain('equivalent')
    expect(mounted.target.textContent).toContain('tick 15')
    expect(mounted.target.textContent).toContain('event kind groups')
    expect(mounted.target.textContent).toContain('Talk=2')
    expect(mounted.target.textContent).toContain('Death=1')
    expect(mounted.target.textContent).toContain('aaaaaaaaaaaa…')

    const parentLink = linkByText('parent run')
    expect(parentLink?.getAttribute('href')).toContain('run_id=run-root')
    expect(parentLink?.getAttribute('href')).toContain('tick=12')

    const observerLinks = [...mounted.target.querySelectorAll('.actions a')].filter(
      (link) => link.textContent?.includes('Observer'),
    )
    expect(observerLinks).toHaveLength(2)
    const hrefs = [...mounted.target.querySelectorAll('a')].map((link) =>
      link.getAttribute('href') ?? '',
    )
    for (const href of hrefs) {
      expect(href).not.toContain(SECRET)
      expect(href).not.toContain('token=')
    }
    expect(window.location.search).not.toContain(SECRET)
    expect(window.history.state).toBeNull()
    mounted.cleanup()
  })

  it('keeps at most two children selected and compares the latest pair', async () => {
    installFetch()
    const mounted = mountPanel()
    await settle()

    buttonByText('child-a')?.click()
    buttonByText('child-b')?.click()
    buttonByText('child-c')?.click()
    await settle()
    expect(buttonByText('child-a')?.getAttribute('aria-pressed')).toBe('false')
    expect(buttonByText('child-b')?.getAttribute('aria-pressed')).toBe('true')
    expect(buttonByText('child-c')?.getAttribute('aria-pressed')).toBe('true')

    buttonByText('Compare selected children')?.click()
    await settle()
    const compareCall = calls.find((call) => call.url.includes('/branches/compare'))
    expect(JSON.parse(String(compareCall?.init.body))).toMatchObject({
      left_run_id: 'child-b',
      right_run_id: 'child-c',
    })
    mounted.cleanup()
  })

  it('distinguishes a leaf run with no child history from an error', async () => {
    installFetch([])
    const mounted = mountPanel()
    await settle()
    expect(mounted.target.textContent).toContain(
      'No child runs are indexed for this run.',
    )
    expect(mounted.target.textContent).not.toContain('children_fetch_failed')
    mounted.cleanup()
  })

  it('surfaces child-lineage failures without inventing children', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input)
        calls.push({ url, init: {} })
        if (url.includes('/branches')) {
          return json({ code: 'forbidden' }, 403)
        }
        if (url.endsWith('/branch')) {
          return json({}, 404)
        }
        return json({}, 404)
      }),
    )
    const mounted = mountPanel()
    await settle()
    expect(mounted.target.textContent).toContain('forbidden')
    expect(mounted.target.textContent).not.toContain('child-a')
    mounted.cleanup()
  })
})
