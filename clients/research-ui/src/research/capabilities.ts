/**
 * Closed registry of Research UI evidence sources and their honest outcomes.
 *
 * Missing, forbidden and partial evidence must never render as a complete zero.
 * Discovery is lazy per active panel and never enables capture or downgrades a
 * subjective query into an objective one.
 */

import type { CapabilitySlot } from '../auth/credentials'
import type { EvidenceClass } from './selection'

export const PANEL_SOURCE_IDS = [
  'demographics',
  'generation_markers',
  'lineage',
  'civilization_catalogue',
  'civilization_map',
  'civilization_overlays',
  'civilization_markers',
  'stored_metrics',
  'cultural_artifacts',
  'semantic_history',
] as const

export type PanelSourceId = (typeof PANEL_SOURCE_IDS)[number]

export type TemporalSemantics =
  | 'boundary'
  | 'tick'
  | 'retained_checkpoint'
  | 'artifact'

export type PanelSource = Readonly<{
  id: PanelSourceId
  endpoint: string
  capabilities: Readonly<Partial<Record<EvidenceClass, CapabilitySlot>>>
  evidenceClasses: readonly EvidenceClass[]
  temporal: TemporalSemantics
}>

export const PANEL_SOURCES: Readonly<Record<PanelSourceId, PanelSource>> = {
  demographics: {
    id: 'demographics',
    endpoint: '/v1/simulations/{run_id}/observer/demographics',
    capabilities: { objective: 'objective_inspection' },
    evidenceClasses: ['objective'],
    temporal: 'boundary',
  },
  generation_markers: {
    id: 'generation_markers',
    endpoint: '/v1/simulations/{run_id}/observer/demographics/markers',
    capabilities: { objective: 'objective_inspection' },
    evidenceClasses: ['objective'],
    temporal: 'boundary',
  },
  lineage: {
    id: 'lineage',
    endpoint: '/v1/simulations/{run_id}/lineage/{family}/{nodes|traverse|snapshots}',
    capabilities: {
      objective: 'objective_inspection',
      subjective: 'subjective_debug',
      analytical: 'subjective_debug',
    },
    evidenceClasses: ['objective', 'subjective', 'analytical'],
    temporal: 'boundary',
  },
  civilization_catalogue: {
    id: 'civilization_catalogue',
    endpoint: '/v1/simulations/{run_id}/observer/civilization/{layer}/catalogue',
    capabilities: {
      objective: 'objective_inspection',
      subjective: 'subjective_debug',
      analytical: 'subjective_debug',
    },
    evidenceClasses: ['objective', 'subjective', 'analytical'],
    temporal: 'boundary',
  },
  civilization_map: {
    id: 'civilization_map',
    endpoint: '/v1/simulations/{run_id}/observer/civilization/{layer}/map',
    capabilities: {
      objective: 'objective_inspection',
      subjective: 'subjective_debug',
      analytical: 'subjective_debug',
    },
    evidenceClasses: ['objective', 'subjective', 'analytical'],
    temporal: 'boundary',
  },
  civilization_overlays: {
    id: 'civilization_overlays',
    endpoint: '/v1/simulations/{run_id}/observer/civilization/{layer}/overlays',
    capabilities: {
      objective: 'objective_inspection',
      subjective: 'subjective_debug',
      analytical: 'subjective_debug',
    },
    evidenceClasses: ['objective', 'subjective', 'analytical'],
    temporal: 'boundary',
  },
  civilization_markers: {
    id: 'civilization_markers',
    endpoint: '/v1/simulations/{run_id}/observer/civilization/{layer}/markers',
    capabilities: {
      objective: 'objective_inspection',
      subjective: 'subjective_debug',
      analytical: 'subjective_debug',
    },
    evidenceClasses: ['objective', 'subjective', 'analytical'],
    temporal: 'boundary',
  },
  stored_metrics: {
    id: 'stored_metrics',
    endpoint: '/v1/research/runs/{run_id}/metrics',
    capabilities: { objective: 'objective_inspection' },
    evidenceClasses: ['objective'],
    temporal: 'artifact',
  },
  cultural_artifacts: {
    id: 'cultural_artifacts',
    endpoint: '/v1/simulations/{run_id}/research/cultural/...',
    capabilities: { objective: 'objective_inspection' },
    evidenceClasses: ['objective'],
    temporal: 'artifact',
  },
  semantic_history: {
    id: 'semantic_history',
    endpoint: '/v1/simulations/{run_id}/observer/agents/{agent_id}/semantics/history',
    capabilities: { subjective: 'subjective_debug' },
    evidenceClasses: ['subjective'],
    temporal: 'retained_checkpoint',
  },
}

export const SOURCE_STATUSES = [
  'loading',
  'available',
  'empty',
  'partial',
  'unavailable',
  'forbidden',
  'error',
] as const

export type SourceStatus = (typeof SOURCE_STATUSES)[number]

export type SourceOutcome = Readonly<{
  status: SourceStatus
  reasonCode: string | null
  coverage: number | null
  requestedTick: number | null
  resolvedTick: number | null
  publicationId: string | null
  continuation: string | null
  credentialEntryOffered: boolean
}>

export type SourceResponse = Readonly<{
  source: PanelSourceId
  evidenceClass: EvidenceClass | null
  hasCredential: boolean
  loading?: boolean
  itemCount?: number | null
  continuation?: string | null
  coverage?: number | null
  requestedTick?: number | null
  resolvedTick?: number | null
  publicationId?: string | null
  wireEvidenceClass?: string | null
  reasonCode?: string | null
  httpStatus?: number | null
}>

const WIRE_EVIDENCE_CLASSES = new Set([
  'OBJECTIVE',
  'OBJECTIVE_WORLD',
  'SUBJECTIVE',
  'SUBJECTIVE_TO_SELECTED_AGENT',
  'ANALYTICAL',
  'ANALYTICAL_INFERRED',
])

const UNAVAILABLE_REASONS = new Set([
  'capture_disabled',
  'capture_unavailable',
  'lifecycle_disabled',
  'replay_unavailable',
  'uncaptured_boundary',
  'not_captured',
  'service_disabled',
  'metric_absent',
  'snapshot_unavailable',
  'checkpoint_unavailable',
])

const FORBIDDEN_REASONS = new Set(['forbidden', 'denied', 'unauthorized'])

function capabilityFor(
  source: PanelSourceId,
  evidenceClass: EvidenceClass | null,
): CapabilitySlot | null {
  const entry = PANEL_SOURCES[source]
  if (evidenceClass === null) {
    return null
  }
  return entry.capabilities[evidenceClass] ?? null
}

/**
 * Resolve access without downgrading evidence class.
 *
 * A missing subjective/debug credential yields `forbidden` with a credential
 * entry prompt; callers must not retry the same panel as objective evidence.
 */
export function classifySourceAccess(
  source: PanelSourceId,
  evidenceClass: EvidenceClass | null,
  hasCredential: boolean,
): { allowed: boolean; capability: CapabilitySlot | null; outcome: SourceOutcome | null } {
  const entry = PANEL_SOURCES[source]
  if (evidenceClass !== null && !entry.evidenceClasses.includes(evidenceClass)) {
    return {
      allowed: false,
      capability: null,
      outcome: baseOutcome('error', 'unsupported_evidence_class', false),
    }
  }
  const capability = capabilityFor(source, evidenceClass)
  if (capability !== null && !hasCredential) {
    return {
      allowed: false,
      capability,
      outcome: baseOutcome('forbidden', 'credential_required', true),
    }
  }
  return { allowed: true, capability, outcome: null }
}

function baseOutcome(
  status: SourceStatus,
  reasonCode: string | null,
  credentialEntryOffered = false,
): SourceOutcome {
  return {
    status,
    reasonCode,
    coverage: null,
    requestedTick: null,
    resolvedTick: null,
    publicationId: null,
    continuation: null,
    credentialEntryOffered,
  }
}

export function classifySourceOutcome(response: SourceResponse): SourceOutcome {
  const access = classifySourceAccess(
    response.source,
    response.evidenceClass,
    response.hasCredential,
  )
  if (!access.allowed && access.outcome !== null) {
    return {
      ...access.outcome,
      coverage: response.coverage ?? null,
      requestedTick: response.requestedTick ?? null,
      resolvedTick: response.resolvedTick ?? null,
      publicationId: response.publicationId ?? null,
      continuation: response.continuation ?? null,
    }
  }

  if (response.wireEvidenceClass !== null && response.wireEvidenceClass !== undefined) {
    if (!WIRE_EVIDENCE_CLASSES.has(response.wireEvidenceClass.trim().toUpperCase())) {
      return baseOutcome('error', 'unknown_evidence_class')
    }
  }

  const base: SourceOutcome = {
    status: 'available',
    reasonCode: response.reasonCode ?? null,
    coverage: response.coverage ?? null,
    requestedTick: response.requestedTick ?? null,
    resolvedTick: response.resolvedTick ?? null,
    publicationId: response.publicationId ?? null,
    continuation: response.continuation ?? null,
    credentialEntryOffered: false,
  }

  if (response.loading === true) {
    return { ...base, status: 'loading' }
  }

  if (response.httpStatus === 401 || response.httpStatus === 403) {
    return { ...base, status: 'forbidden', reasonCode: response.reasonCode ?? 'forbidden' }
  }
  if (
    response.httpStatus === 404 ||
    response.httpStatus === 410 ||
    response.httpStatus === 503
  ) {
    return {
      ...base,
      status: 'unavailable',
      reasonCode: response.reasonCode ?? `http_${response.httpStatus}`,
    }
  }
  if (response.httpStatus === 409) {
    return { ...base, status: 'error', reasonCode: 'stale_publication' }
  }
  if (response.httpStatus !== null && response.httpStatus !== undefined) {
    if (response.httpStatus >= 500) {
      return { ...base, status: 'error', reasonCode: `http_${response.httpStatus}` }
    }
    if (response.httpStatus >= 400) {
      return { ...base, status: 'error', reasonCode: response.reasonCode ?? 'request_failed' }
    }
  }

  const reason = response.reasonCode ?? null
  if (reason !== null && FORBIDDEN_REASONS.has(reason)) {
    return { ...base, status: 'forbidden' }
  }
  if (reason !== null && UNAVAILABLE_REASONS.has(reason)) {
    return { ...base, status: 'unavailable' }
  }

  const itemCount = response.itemCount ?? null
  const continuation = response.continuation ?? null
  if (itemCount === 0 && continuation !== null) {
    return { ...base, status: 'partial', reasonCode: 'continuation_only' }
  }
  if (response.coverage !== null && response.coverage !== undefined) {
    if (response.coverage < 1) {
      return { ...base, status: 'partial', reasonCode: reason ?? 'partial_coverage' }
    }
  }
  if (reason === 'partial_coverage') {
    return { ...base, status: 'partial' }
  }
  if (itemCount === 0) {
    return { ...base, status: 'empty', reasonCode: reason ?? 'no_evidence' }
  }
  return base
}

export function sourcesForPanel(
  panel: string,
): readonly PanelSourceId[] {
  switch (panel) {
    case 'population':
    case 'cohorts':
      return ['demographics', 'generation_markers']
    case 'lineage':
      return ['lineage']
    case 'technology':
      return ['lineage', 'civilization_overlays']
    case 'culture':
    case 'language':
      return ['cultural_artifacts', 'semantic_history', 'lineage']
    case 'migration':
      return ['civilization_map', 'civilization_overlays']
    case 'institutions':
      return ['civilization_catalogue', 'civilization_overlays', 'lineage']
    case 'economy':
      return ['stored_metrics', 'civilization_overlays']
    case 'projects':
      return ['civilization_catalogue']
    default:
      return []
  }
}
