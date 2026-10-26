import { describe, expect, it } from 'vitest'
import { flushSync, render } from '../test/mount'
import GodotEmbed from './GodotEmbed.svelte'

describe('godot embed fallback', () => {
  it('offers an explicit safe new-tab anchor without credentials', () => {
    const mounted = render(GodotEmbed as never, {
      deepLink: {
        runId: 'run-1',
        tick: 4,
        eventId: null,
        sequence: null,
        agentId: 'agent-a',
        view: 'overview',
      },
    })
    const anchor = mounted.target.querySelector('a')
    expect(anchor).not.toBeNull()
    expect(anchor?.getAttribute('target')).toBe('_blank')
    expect(anchor?.getAttribute('rel')).toContain('noopener')
    expect(anchor?.getAttribute('href')).toContain('run_id=run-1')
    expect(anchor?.getAttribute('href')).not.toContain('token=')
    const iframe = mounted.target.querySelector('iframe')
    expect(iframe).toBeNull()
    flushSync()
    mounted.cleanup()
  })
})
