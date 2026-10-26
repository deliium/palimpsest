import { flushSync, mount, unmount, type Component } from 'svelte'

export type Mounted = {
  target: HTMLElement
  cleanup: () => void
}

export function render(
  component: Component<Record<string, unknown>>,
  props: Record<string, unknown> = {},
): Mounted {
  const target = document.createElement('div')
  document.body.appendChild(target)
  const instance = mount(component, { target, props })
  flushSync()
  return {
    target,
    cleanup: () => {
      unmount(instance)
      target.remove()
      flushSync()
    },
  }
}

export { flushSync }
