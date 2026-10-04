import {
  type ResearchUiDeepLink,
  type ResearchUiView,
  parseResearchUiQuery,
} from './deeplink'
import { stripSecretQueryKeys } from './auth/credentials'

export type Route =
  | { kind: 'run_list' }
  | { kind: 'matrix_list' }
  | { kind: 'matrix_detail'; matrixId: string }
  | {
      kind: 'run'
      runId: string
      view: ResearchUiView
      deepLink: ResearchUiDeepLink
    }
  | { kind: 'not_found' }

const RUN_VIEWS = new Set<ResearchUiView>([
  'overview',
  'graphs',
  'agent',
  'analytics',
  'traces',
  'compare',
])

export function parsePathname(pathname: string): {
  kind: Route['kind']
  runId?: string
  matrixId?: string
  viewHint?: ResearchUiView
} {
  const base = '/research'
  let path = pathname
  if (path.startsWith(base)) {
    path = path.slice(base.length)
  }
  if (!path.startsWith('/')) {
    path = `/${path}`
  }
  if (path === '/' || path === '') {
    return { kind: 'run_list' }
  }
  if (path === '/matrix' || path === '/matrix/') {
    return { kind: 'matrix_list' }
  }
  const matrixMatch = /^\/matrix\/([^/]+)\/?$/.exec(path)
  if (matrixMatch !== null) {
    return { kind: 'matrix_detail', matrixId: decodeURIComponent(matrixMatch[1] ?? '') }
  }
  const runMatch = /^\/runs\/([^/]+)(?:\/([^/]+))?\/?$/.exec(path)
  if (runMatch !== null) {
    const runId = decodeURIComponent(runMatch[1] ?? '')
    const tab = (runMatch[2] ?? 'overview').toLowerCase()
    const viewHint = RUN_VIEWS.has(tab as ResearchUiView)
      ? (tab as ResearchUiView)
      : 'overview'
    return { kind: 'run', runId, viewHint }
  }
  return { kind: 'not_found' }
}

export function resolveRoute(
  pathname: string = window.location.pathname,
  search: string = window.location.search,
): Route {
  const { cleaned } = stripSecretQueryKeys(search)
  if (cleaned !== search && typeof history !== 'undefined') {
    history.replaceState(null, '', `${pathname}${cleaned}`)
  }

  const parsed = parsePathname(pathname)
  const deep = parseResearchUiQuery(cleaned)

  if (parsed.kind === 'run_list') {
    if (deep.ok && deep.state.runId !== null) {
      return {
        kind: 'run',
        runId: deep.state.runId,
        view: deep.state.view === 'matrix' ? 'overview' : deep.state.view,
        deepLink: deep.state,
      }
    }
    if (deep.ok && deep.state.view === 'matrix') {
      return { kind: 'matrix_list' }
    }
    return { kind: 'run_list' }
  }

  if (parsed.kind === 'matrix_list') {
    return { kind: 'matrix_list' }
  }
  if (parsed.kind === 'matrix_detail' && parsed.matrixId !== undefined) {
    return { kind: 'matrix_detail', matrixId: parsed.matrixId }
  }

  if (parsed.kind === 'run' && parsed.runId !== undefined) {
    const view =
      deep.ok && deep.state.view !== 'matrix'
        ? deep.state.view
        : (parsed.viewHint ?? 'overview')
    const deepLink: ResearchUiDeepLink = deep.ok
      ? {
          ...deep.state,
          runId: parsed.runId,
          view: view === 'matrix' ? 'overview' : view,
        }
      : {
          runId: parsed.runId,
          tick: null,
          eventId: null,
          sequence: null,
          agentId: null,
          view: view === 'matrix' ? 'overview' : view,
        }
    if (import.meta.env.DEV) {
      console.debug(
        `research_ui_deeplink_applied run_id=${deepLink.runId ?? ''} view=${deepLink.view}`,
      )
    }
    return {
      kind: 'run',
      runId: parsed.runId,
      view: deepLink.view,
      deepLink,
    }
  }

  return { kind: 'not_found' }
}

export function runPath(runId: string, view: ResearchUiView = 'overview'): string {
  const tab = view === 'overview' ? '' : `/${view}`
  return `/research/runs/${encodeURIComponent(runId)}${tab}`
}

export function pushRunRoute(
  runId: string,
  view: ResearchUiView,
  deepLink?: Partial<ResearchUiDeepLink>,
): void {
  const params = new URLSearchParams()
  params.set('run_id', runId)
  if (view !== 'overview') {
    params.set('view', view)
  }
  if (deepLink?.tick != null) {
    params.set('tick', String(deepLink.tick))
  }
  if (deepLink?.eventId) {
    params.set('event_id', deepLink.eventId)
  }
  if (deepLink?.sequence != null) {
    params.set('sequence', String(deepLink.sequence))
  }
  if (deepLink?.agentId) {
    params.set('agent_id', deepLink.agentId)
  }
  const q = params.toString()
  const url = `${runPath(runId, view)}${q === '' ? '' : `?${q}`}`
  history.pushState(null, '', url)
  window.dispatchEvent(new PopStateEvent('popstate'))
}
