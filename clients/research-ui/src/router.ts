import {
  RESEARCH_UI_VIEWS,
  buildResearchSelectionPath,
  emptyResearchSelection,
  parseResearchSelection,
  type ResearchSelection,
  type ResearchUiView,
} from './research/selection'
import type { ResearchUiDeepLink } from './deeplink'
import { stripSecretQueryKeys } from './auth/credentials'

export type Route =
  | { kind: 'run_list' }
  | { kind: 'matrix_list' }
  | { kind: 'matrix_detail'; matrixId: string }
  | {
      kind: 'run'
      runId: string
      view: ResearchUiView
      selection: ResearchSelection
      deepLink: ResearchUiDeepLink
    }
  | { kind: 'route_error'; code: string }
  | { kind: 'not_found' }

const RUN_VIEWS = new Set<ResearchUiView>(
  RESEARCH_UI_VIEWS.filter((view) => view !== 'matrix'),
)

function isRunView(value: string): value is ResearchUiView {
  return RUN_VIEWS.has(value as ResearchUiView)
}

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
  try {
    const matrixMatch = /^\/matrix\/([^/]+)\/?$/.exec(path)
    if (matrixMatch !== null) {
      return {
        kind: 'matrix_detail',
        matrixId: decodeURIComponent(matrixMatch[1] ?? ''),
      }
    }
    const runMatch = /^\/runs\/([^/]+)(?:\/([^/]+))?\/?$/.exec(path)
    if (runMatch !== null) {
      const runId = decodeURIComponent(runMatch[1] ?? '')
      const tab = (runMatch[2] ?? 'overview').toLowerCase()
      const viewHint = isRunView(tab) ? (tab as ResearchUiView) : 'overview'
      return { kind: 'run', runId, viewHint }
    }
  } catch {
    return { kind: 'not_found' }
  }
  return { kind: 'not_found' }
}

export function selectionToDeepLink(
  selection: ResearchSelection,
): ResearchUiDeepLink {
  return {
    runId: selection.runId,
    tick: selection.tick,
    eventId: selection.eventId,
    sequence: selection.sequence,
    agentId:
      selection.focus?.kind === 'agent' && selection.focus.source === 'objective'
        ? selection.focus.agentId
        : null,
    view: selection.view,
  }
}

function runRoute(
  runId: string,
  view: ResearchUiView,
  selection: ResearchSelection,
): Route {
  const resolved: ResearchSelection = { ...selection, runId, view }
  return {
    kind: 'run',
    runId,
    view,
    selection: resolved,
    deepLink: selectionToDeepLink(resolved),
  }
}

function explicitRunView(search: string): ResearchUiView | null {
  const raw = (new URLSearchParams(search).get('view') ?? '').trim().toLowerCase()
  return raw !== '' && isRunView(raw) ? (raw as ResearchUiView) : null
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
  const deep = parseResearchSelection(cleaned)

  if (parsed.kind === 'matrix_list') {
    return { kind: 'matrix_list' }
  }
  if (parsed.kind === 'matrix_detail' && parsed.matrixId !== undefined) {
    return { kind: 'matrix_detail', matrixId: parsed.matrixId }
  }

  if (parsed.kind === 'run_list') {
    if (!deep.ok) {
      return { kind: 'route_error', code: deep.reasonCode }
    }
    if (deep.selection.view === 'matrix') {
      return { kind: 'matrix_list' }
    }
    if (deep.selection.runId !== null) {
      const view = explicitRunView(cleaned) ?? 'overview'
      return runRoute(deep.selection.runId, view, deep.selection)
    }
    return { kind: 'run_list' }
  }

  if (parsed.kind === 'run' && parsed.runId !== undefined) {
    if (!deep.ok) {
      return { kind: 'route_error', code: deep.reasonCode }
    }
    if (deep.selection.runId !== null && deep.selection.runId !== parsed.runId) {
      return { kind: 'route_error', code: 'conflicting_run_id' }
    }
    const view = explicitRunView(cleaned) ?? parsed.viewHint ?? 'overview'
    return runRoute(parsed.runId, view, deep.selection)
  }

  return { kind: 'not_found' }
}

export function runPath(
  runId: string,
  view: ResearchUiView = 'overview',
): string {
  const tab = view === 'overview' ? '' : `/${view}`
  return `/research/runs/${encodeURIComponent(runId)}${tab}`
}

export function selectionPath(selection: ResearchSelection): string {
  return buildResearchSelectionPath(selection)
}

export function navigateToSelection(
  selection: ResearchSelection,
  mode: 'push' | 'replace' = 'push',
): void {
  const url = buildResearchSelectionPath(selection)
  if (typeof history === 'undefined') {
    return
  }
  if (mode === 'replace') {
    history.replaceState(null, '', url)
  } else {
    history.pushState(null, '', url)
  }
  window.dispatchEvent(new PopStateEvent('popstate'))
}

export function pushRunRoute(
  runId: string,
  view: ResearchUiView,
  selection: Partial<ResearchSelection> = {},
  mode: 'push' | 'replace' = 'push',
): void {
  navigateToSelection(
    {
      ...emptyResearchSelection(),
      ...selection,
      runId,
      view,
    },
    mode,
  )
}
