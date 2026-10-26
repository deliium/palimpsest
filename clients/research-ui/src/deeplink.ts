/** Credential-free Research UI deep-link parse/build (mirrors Python). */

import {
  RESEARCH_UI_VIEWS,
  buildResearchSelectionQuery,
  parseResearchSelection,
  type ResearchUiView,
} from './research/selection'

export { RESEARCH_UI_VIEWS }
export type { ResearchUiView }

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

/**
 * Parse the legacy deep-link view of the canonical selection.
 *
 * New panels read `ResearchSelection` directly; this adapter keeps older
 * callers and stored links working without a second parser.
 */
export function parseResearchUiQuery(
  query: string | URLSearchParams | Record<string, string>,
): DeepLinkParseResult {
  const result = parseResearchSelection(query)
  if (!result.ok) {
    return { ok: false, reasonCode: result.reasonCode }
  }
  const selection = result.selection
  return {
    ok: true,
    state: {
      runId: selection.runId,
      tick: selection.tick,
      eventId: selection.eventId,
      sequence: selection.sequence,
      agentId:
        selection.focus?.kind === 'agent' && selection.focus.source === 'objective'
          ? selection.focus.agentId
          : null,
      view: selection.view,
    },
    warnings: result.warnings,
  }
}

export function buildResearchUiQuery(state: ResearchUiDeepLink): string {
  return buildResearchSelectionQuery({
    runId: state.runId,
    view: state.view,
    tick: state.tick,
    eventId: state.eventId,
    sequence: state.sequence,
    generationIndex: null,
    cohort: null,
    scopeOwnerId: null,
    evidenceClass: null,
    focus:
      state.agentId === null || state.agentId === ''
        ? null
        : {
            kind: 'agent',
            source: 'objective',
            agentId: state.agentId,
          },
  })
}

export type GodotLinkInput = {
  runId: string | null
  tick: number | null
  eventId: string | null
  sequence: number | null
  agentId: string | null
  debugger: boolean
  options?: Record<string, string | number | boolean | null | undefined>
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
  for (const [key, value] of Object.entries(state.options ?? {})) {
    if (value === undefined || value === null || value === '') {
      continue
    }
    params.set(key, String(value))
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
