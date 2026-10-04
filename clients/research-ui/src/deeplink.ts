/** Credential-free Research UI deep-link parse/build (mirrors Python). */

export const RESEARCH_UI_VIEWS = [
  'overview',
  'graphs',
  'agent',
  'analytics',
  'traces',
  'compare',
  'matrix',
] as const

export type ResearchUiView = (typeof RESEARCH_UI_VIEWS)[number]

const SECRET_KEYS = new Set([
  'token',
  'credential',
  'credentials',
  'secret',
  'api_key',
  'apikey',
  'authorization',
  'password',
  'access_token',
])

const RUN_SCOPED_VIEWS = new Set<ResearchUiView>([
  'overview',
  'graphs',
  'agent',
  'analytics',
  'traces',
  'compare',
])

export type ResearchUiDeepLink = {
  runId: string | null
  tick: number | null
  eventId: string | null
  sequence: number | null
  agentId: string | null
  view: ResearchUiView
}

export type DeepLinkParseResult =
  | { ok: true; state: ResearchUiDeepLink; warnings: string[] }
  | { ok: false; reasonCode: string }

function optionalNonNegInt(raw: string | undefined, field: string): number | null {
  if (raw === undefined || raw.trim() === '') {
    return null
  }
  const value = Number.parseInt(raw.trim(), 10)
  if (!Number.isFinite(value) || value < 0 || String(value) !== raw.trim()) {
    throw new Error(`invalid_${field}`)
  }
  return value
}

function isView(value: string): value is ResearchUiView {
  return (RESEARCH_UI_VIEWS as readonly string[]).includes(value)
}

export function parseResearchUiQuery(
  query: string | URLSearchParams | Record<string, string>,
): DeepLinkParseResult {
  let params: URLSearchParams
  if (typeof query === 'string') {
    const text = query.startsWith('?') ? query.slice(1) : query
    params = new URLSearchParams(text)
  } else if (query instanceof URLSearchParams) {
    params = query
  } else {
    params = new URLSearchParams(query)
  }

  for (const key of params.keys()) {
    if (SECRET_KEYS.has(key.toLowerCase())) {
      if (import.meta.env.DEV) {
        console.warn(`research_ui_state_rejected reason_code=query_string_secret`)
      }
      return { ok: false, reasonCode: 'query_string_secret' }
    }
  }

  const warnings: string[] = []
  const runIdRaw = (params.get('run_id') ?? '').trim()
  const runId = runIdRaw === '' ? null : runIdRaw

  let tick: number | null
  let sequence: number | null
  try {
    tick = optionalNonNegInt(params.get('tick') ?? undefined, 'tick')
    sequence = optionalNonNegInt(params.get('sequence') ?? undefined, 'sequence')
  } catch (err) {
    const reason = err instanceof Error ? err.message : 'invalid_query'
    return { ok: false, reasonCode: reason }
  }

  const eventIdRaw = (params.get('event_id') ?? params.get('event') ?? '').trim()
  const eventId = eventIdRaw === '' ? null : eventIdRaw
  const agentIdRaw = (params.get('agent_id') ?? params.get('agent') ?? '').trim()
  const agentId = agentIdRaw === '' ? null : agentIdRaw

  const viewRaw = (params.get('view') ?? '').trim().toLowerCase()
  let view: ResearchUiView = 'overview'
  if (viewRaw !== '') {
    if (isView(viewRaw)) {
      view = viewRaw
    } else {
      warnings.push('unknown_view')
      if (import.meta.env.DEV) {
        console.warn(`research_ui_state_rejected reason_code=unknown_view`)
      }
      view = 'overview'
    }
  }

  if (RUN_SCOPED_VIEWS.has(view) && runId === null) {
    return { ok: false, reasonCode: 'run_id_missing' }
  }

  if (tick === null && sequence !== null) {
    return { ok: false, reasonCode: 'incomplete_event_cursor' }
  }

  const state: ResearchUiDeepLink = {
    runId,
    tick,
    eventId,
    sequence,
    agentId,
    view,
  }

  if (import.meta.env.DEV) {
    console.debug(
      `research_ui_deeplink_applied run_id=${state.runId ?? ''} view=${state.view}`,
    )
  }

  return { ok: true, state, warnings }
}

export function buildResearchUiQuery(state: ResearchUiDeepLink): string {
  const params = new URLSearchParams()
  if (state.runId !== null && state.runId !== '') {
    params.set('run_id', state.runId)
  }
  if (state.tick !== null) {
    params.set('tick', String(state.tick))
  }
  if (state.eventId !== null && state.eventId !== '') {
    params.set('event_id', state.eventId)
  }
  if (state.sequence !== null) {
    params.set('sequence', String(state.sequence))
  }
  if (state.agentId !== null && state.agentId !== '') {
    params.set('agent_id', state.agentId)
  }
  if (state.view !== 'overview') {
    params.set('view', state.view)
  }
  const text = params.toString()
  return text === '' ? '' : `?${text}`
}

export type GodotLinkInput = {
  runId: string | null
  tick: number | null
  eventId: string | null
  sequence: number | null
  agentId: string | null
  debugger: boolean
}

/** Build Godot observer URL (Research UI → World Observer). */
export function buildGodotObserverUrl(state: GodotLinkInput, origin = ''): string {
  const params = new URLSearchParams()
  if (state.runId !== null && state.runId !== '') {
    params.set('run_id', state.runId)
  }
  if (state.tick !== null) {
    params.set('tick', String(state.tick))
  }
  if (state.eventId !== null && state.eventId !== '') {
    params.set('event_id', state.eventId)
  }
  if (state.sequence !== null) {
    params.set('sequence', String(state.sequence))
  }
  if (state.agentId !== null && state.agentId !== '') {
    params.set('agent_id', state.agentId)
  }
  if (state.debugger) {
    params.set('debugger', '1')
  }
  const q = params.toString()
  return `${origin}/${q === '' ? '' : `?${q}`}`
}

/** Build Research UI path (Godot → Research UI). */
export function buildResearchUiPath(state: ResearchUiDeepLink): string {
  return `/research/${buildResearchUiQuery(state)}`
}
