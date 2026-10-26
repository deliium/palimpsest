/** Typed, validated read-only clients for generational and civilization research. */

import type { CapabilitySlot } from '../auth/credentials'
import { ApiClientError, apiFetchResponse, type FetchOptions } from './client'
import {
  ensureCivilization,
  ensureCulturalArtifactBinding,
  ensureCulturalCellMetrics,
  ensureCulturalComparison,
  ensureCulturalEvidencePage,
  ensureDemographics,
  ensureGenerationMarkers,
  ensureLabelOverlay,
  ensureLineageFamilies,
  ensureLineageGraph,
  ensureLineageNodes,
  ensureLineageSnapshots,
  ensureNarrativeHops,
  ensureSemanticHistory,
  ensureSymbolicOverlay,
  ensureTranslationOverlay,
  isRecord,
  requireArray,
  requireRecord,
  requireString,
  ResearchSchemaError,
  type CivilizationEnvelope,
  type DemographicsEnvelope,
  type GenerationMarkersEnvelope,
  type LineageFamilyDescriptor,
  type LineageGraph,
  type LineageNodePage,
  type LineageNodeRef,
  type LineageSnapshot,
  type LineageSnapshotPage,
} from './researchSchemas'
import { decodeRowsJson, parseBoundedJson } from '../research/json'

const MAX_ENVELOPE_BYTES = 64 * 1024 * 1024
const MAX_ENVELOPE_DEPTH = 32

type Query = FetchOptions['query']

function pathSegment(value: string): string {
  return encodeURIComponent(value)
}

async function decodeResponse(response: Response, signal?: AbortSignal): Promise<unknown> {
  const text = await response.text()
  if (signal?.aborted) {
    throw new DOMException('Aborted', 'AbortError')
  }
  if (text.length > MAX_ENVELOPE_BYTES) {
    throw new ResearchSchemaError('invalid_research_response')
  }
  return parseBoundedJson(text, {
    maxBytes: MAX_ENVELOPE_BYTES,
    maxDepth: MAX_ENVELOPE_DEPTH,
    signal,
  })
}

async function getJson<T>(
  path: string,
  capability: CapabilitySlot,
  query: Query,
  validate: (value: unknown) => T,
  signal?: AbortSignal,
): Promise<T> {
  const response = await apiFetchResponse(path, {
    capability,
    query,
    signal,
  })
  const value = await decodeResponse(response, signal)
  if (signal?.aborted) {
    throw new DOMException('Aborted', 'AbortError')
  }
  return validate(value)
}

export type CulturalDocument<T> = {
  data: T
  binding: 'runtime_bound' | 'legacy_unverified'
}

async function getCulturalDocument<T>(
  path: string,
  validate: (value: unknown) => T,
  signal?: AbortSignal,
): Promise<CulturalDocument<T>> {
  const response = await apiFetchResponse(path, {
    capability: 'objective_inspection',
    signal,
  })
  const meta = ensureCulturalArtifactBinding(
    response.headers.get('X-Palimpsest-Artifact-Binding'),
  )
  const value = await decodeResponse(response, signal)
  return { data: validate(value), binding: meta.binding }
}

export type DemographicsQuery = {
  tick?: number | null
  throughSequence?: number | null
  section?: 'agents' | 'cohorts' | 'generations'
  agentId?: string | null
  afterAgentId?: string | null
  afterGroupKey?: string | null
  limit?: number
}

export function getDemographics(
  runId: string,
  query: DemographicsQuery = {},
  signal?: AbortSignal,
): Promise<DemographicsEnvelope> {
  return getJson(
    `/v1/simulations/${pathSegment(runId)}/observer/demographics`,
    'objective_inspection',
    {
      tick: query.tick ?? undefined,
      through_sequence: query.throughSequence ?? undefined,
      section: query.section ?? 'agents',
      agent_id: query.agentId ?? undefined,
      after_agent_id: query.afterAgentId ?? undefined,
      after_group_key: query.afterGroupKey ?? undefined,
      limit: query.limit ?? 100,
    },
    ensureDemographics,
    signal,
  )
}

export type GenerationMarkersQuery = {
  tick: number
  fromTick?: number | null
  toTick?: number | null
  afterGenerationIndex?: number | null
  limit?: number
}

export function getGenerationMarkers(
  runId: string,
  query: GenerationMarkersQuery,
  signal?: AbortSignal,
): Promise<GenerationMarkersEnvelope> {
  return getJson(
    `/v1/simulations/${pathSegment(runId)}/observer/generation-markers`,
    'objective_inspection',
    {
      tick: query.tick,
      from_tick: query.fromTick ?? undefined,
      to_tick: query.toTick ?? undefined,
      after_generation_index: query.afterGenerationIndex ?? undefined,
      limit: query.limit ?? 100,
    },
    ensureGenerationMarkers,
    signal,
  )
}

export function getLineageFamilies(
  runId: string,
  includeRestricted = false,
  signal?: AbortSignal,
): Promise<LineageFamilyDescriptor[]> {
  return getJson(
    `/v1/simulations/${pathSegment(runId)}/lineage/families`,
    includeRestricted ? 'subjective_debug' : 'objective_inspection',
    { include_restricted: includeRestricted ? 'true' : undefined },
    ensureLineageFamilies,
    signal,
  )
}

export type LineageScopeInput = {
  family: string
  evidenceClass: 'objective' | 'subjective' | 'analytical'
  ownerId?: string | null
}

function lineageCapability(
  evidenceClass: LineageScopeInput['evidenceClass'],
): CapabilitySlot {
  return evidenceClass === 'objective' ? 'objective_inspection' : 'subjective_debug'
}

function lineageQuery(scope: LineageScopeInput): Record<string, string | undefined> {
  return {
    evidence_class: scope.evidenceClass,
    owner_id:
      scope.evidenceClass === 'analytical'
        ? undefined
        : (scope.ownerId ?? undefined),
  }
}

export type LineagePageQuery = {
  after?: string | null
  limit?: number
  boundaryTick?: number | null
}

export function getLineageSnapshots(
  runId: string,
  scope: LineageScopeInput,
  query: LineagePageQuery = {},
  signal?: AbortSignal,
): Promise<LineageSnapshotPage> {
  return getJson(
    `/v1/simulations/${pathSegment(runId)}/lineage/${pathSegment(scope.family)}/snapshots`,
    lineageCapability(scope.evidenceClass),
    {
      ...lineageQuery(scope),
      after: query.after ?? undefined,
      limit: query.limit ?? 100,
    },
    ensureLineageSnapshots,
    signal,
  )
}

export type LineageNodeQuery = LineagePageQuery & {
  nativeKind?: string | null
  nativeId?: string | null
}

export function getLineageNodes(
  runId: string,
  scope: LineageScopeInput,
  query: LineageNodeQuery,
  signal?: AbortSignal,
): Promise<LineageNodePage> {
  return getJson(
    `/v1/simulations/${pathSegment(runId)}/lineage/${pathSegment(scope.family)}/nodes`,
    lineageCapability(scope.evidenceClass),
    {
      ...lineageQuery(scope),
      native_kind: query.nativeKind ?? undefined,
      native_id: query.nativeId ?? undefined,
      boundary_tick: query.boundaryTick ?? undefined,
      after: query.after ?? undefined,
      limit: query.limit ?? 100,
    },
    ensureLineageNodes,
    signal,
  )
}

export type LineageTraverseQuery = LineagePageQuery & {
  rootKey: string
  direction?: string
  maxDepth?: number
  maxNodes?: number
  maxEdges?: number
  livingOnly?: boolean
}

export function getLineageTraverse(
  runId: string,
  scope: LineageScopeInput,
  query: LineageTraverseQuery,
  signal?: AbortSignal,
): Promise<LineageGraph> {
  return getJson(
    `/v1/simulations/${pathSegment(runId)}/lineage/${pathSegment(scope.family)}/traverse`,
    lineageCapability(scope.evidenceClass),
    {
      ...lineageQuery(scope),
      root_key: query.rootKey,
      direction: query.direction ?? 'both',
      boundary_tick: query.boundaryTick ?? undefined,
      max_depth: query.maxDepth ?? 4,
      max_nodes: query.maxNodes ?? 200,
      max_edges: query.maxEdges ?? 500,
      living_only: query.livingOnly ? 'true' : undefined,
      after: query.after ?? undefined,
      limit: query.limit ?? 100,
    },
    ensureLineageGraph,
    signal,
  )
}

export type LineageParticipantQuery = LineagePageQuery & {
  agentId: string
  role?: 'teacher' | 'learner' | 'both'
}

export function getLineageMentorshipParticipants(
  runId: string,
  scope: LineageScopeInput,
  query: LineageParticipantQuery,
  signal?: AbortSignal,
): Promise<Record<string, unknown>> {
  return getJson(
    `/v1/simulations/${pathSegment(runId)}/lineage/mentorship/participants`,
    lineageCapability(scope.evidenceClass),
    {
      ...lineageQuery(scope),
      agent_id: query.agentId,
      role: query.role ?? 'both',
      boundary_tick: query.boundaryTick ?? undefined,
      after: query.after ?? undefined,
      limit: query.limit ?? 100,
    },
    (value) => {
      const body = requireRecord(value)
      requireString(body.snapshot && requireRecord(body.snapshot).publication_id)
      requireArray(body.items).forEach(requireRecord)
      return body
    },
    signal,
  )
}

export type CivilizationMapQuery = {
  section?: string
  tick?: number | null
  throughSequence?: number | null
  entityId?: string | null
  limit?: number
  cursor?: string | null
}

export function getCivilizationMap(
  runId: string,
  query: CivilizationMapQuery = {},
  signal?: AbortSignal,
): Promise<CivilizationEnvelope> {
  return getJson(
    `/v1/simulations/${pathSegment(runId)}/observer/civilization/map`,
    'objective_inspection',
    {
      section: query.section ?? 'locations',
      tick: query.tick ?? undefined,
      through_sequence: query.throughSequence ?? undefined,
      entity_id: query.entityId ?? undefined,
      limit: query.limit ?? 100,
      cursor: query.cursor ?? undefined,
    },
    (value) => ensureCivilization(value, 'observer-civilization-map-v1'),
    signal,
  )
}

export type CivilizationCatalogueQuery = {
  evidenceClass: 'OBJECTIVE' | 'SUBJECTIVE' | 'ANALYTICAL'
  ownerId?: string | null
  layer?: string | null
  limit?: number
  cursor?: string | null
}

function civilizationCapability(
  evidenceClass: CivilizationCatalogueQuery['evidenceClass'],
): CapabilitySlot {
  return evidenceClass === 'OBJECTIVE' ? 'objective_inspection' : 'subjective_debug'
}

export function getCivilizationCatalogue(
  runId: string,
  query: CivilizationCatalogueQuery,
  signal?: AbortSignal,
): Promise<CivilizationEnvelope> {
  return getJson(
    `/v1/simulations/${pathSegment(runId)}/observer/civilization/catalogue`,
    civilizationCapability(query.evidenceClass),
    {
      evidence_class: query.evidenceClass,
      owner_id:
        query.evidenceClass === 'OBJECTIVE' ? undefined : (query.ownerId ?? undefined),
      layer: query.layer ?? undefined,
      limit: query.limit ?? 100,
      cursor: query.cursor ?? undefined,
    },
    (value) => ensureCivilization(value, 'observer-civilization-catalogue-v1'),
    signal,
  )
}

export type CivilizationOverlayQuery = {
  tick: number
  layer: string
  evidenceClass: 'OBJECTIVE' | 'SUBJECTIVE' | 'ANALYTICAL'
  ownerId?: string | null
  locationId?: string | null
  regionId?: string | null
  entityId?: string | null
  limit?: number
  cursor?: string | null
  publicationId?: string | null
}

export function getCivilizationOverlays(
  runId: string,
  query: CivilizationOverlayQuery,
  signal?: AbortSignal,
): Promise<CivilizationEnvelope> {
  return getJson(
    `/v1/simulations/${pathSegment(runId)}/observer/civilization/overlays`,
    civilizationCapability(query.evidenceClass),
    {
      tick: query.tick,
      layer: query.layer,
      evidence_class: query.evidenceClass,
      owner_id:
        query.evidenceClass === 'OBJECTIVE' ? undefined : (query.ownerId ?? undefined),
      location_id: query.locationId ?? undefined,
      region_id: query.regionId ?? undefined,
      entity_id: query.entityId ?? undefined,
      limit: query.limit ?? 100,
      cursor: query.cursor ?? undefined,
      publication_id: query.publicationId ?? undefined,
    },
    (value) => ensureCivilization(value, 'observer-civilization-overlay-v1'),
    signal,
  )
}

export type CivilizationMarkersQuery = {
  evidenceClass: 'OBJECTIVE' | 'SUBJECTIVE' | 'ANALYTICAL'
  fromTick: number
  toTick: number
  layer?: string | null
  ownerId?: string | null
  publicationId?: string | null
  limit?: number
  cursor?: string | null
}

export function getCivilizationMarkers(
  runId: string,
  query: CivilizationMarkersQuery,
  signal?: AbortSignal,
): Promise<CivilizationEnvelope> {
  return getJson(
    `/v1/simulations/${pathSegment(runId)}/observer/civilization/markers`,
    civilizationCapability(query.evidenceClass),
    {
      evidence_class: query.evidenceClass,
      from_tick: query.fromTick,
      to_tick: query.toTick,
      layer: query.layer ?? undefined,
      owner_id:
        query.evidenceClass === 'OBJECTIVE' ? undefined : (query.ownerId ?? undefined),
      publication_id: query.publicationId ?? undefined,
      limit: query.limit ?? 100,
      cursor: query.cursor ?? undefined,
    },
    (value) => ensureCivilization(value, 'observer-civilization-markers-v1'),
    signal,
  )
}

export function readCulturalComparison(
  matrixId: string,
  signal?: AbortSignal,
): Promise<CulturalDocument<Record<string, unknown>>> {
  return getCulturalDocument(
    `/v1/research/matrices/${pathSegment(matrixId)}/cultural-comparison`,
    ensureCulturalComparison,
    signal,
  )
}

export function readCulturalCellMetrics(
  matrixId: string,
  cellId: string,
  signal?: AbortSignal,
): Promise<CulturalDocument<Record<string, unknown>>> {
  return getCulturalDocument(
    `/v1/research/matrices/${pathSegment(matrixId)}/cells/${pathSegment(cellId)}/cultural-metrics`,
    (value) => ensureCulturalCellMetrics(value, (raw) => decodeRowsJson(raw)),
    signal,
  )
}

export type CulturalEvidenceQuery = {
  section: 'boundaries' | 'traits' | 'transmission' | 'groups' | 'archives'
  fromTick?: number | null
  toTick?: number | null
  ownerId?: string | null
  dimension?: string | null
  limit?: number
  cursor?: string | null
}

export function getCulturalEvidence(
  matrixId: string,
  cellId: string,
  query: CulturalEvidenceQuery,
  signal?: AbortSignal,
): Promise<Record<string, unknown>> {
  return getJson(
    `/v1/research/matrices/${pathSegment(matrixId)}/cells/${pathSegment(cellId)}/cultural-evidence`,
    'subjective_debug',
    {
      section: query.section,
      from_tick: query.fromTick ?? undefined,
      to_tick: query.toTick ?? undefined,
      owner_id: query.ownerId ?? undefined,
      dimension: query.dimension ?? undefined,
      limit: query.limit ?? 100,
      cursor: query.cursor ?? undefined,
    },
    ensureCulturalEvidencePage,
    signal,
  )
}

export type SemanticHistoryQuery = {
  source: 'label' | 'composition'
  tick?: number | null
  fromTick?: number | null
  toTick?: number | null
  after?: string | null
  limit?: number
}

export function getSemanticHistory(
  runId: string,
  agentId: string,
  query: SemanticHistoryQuery,
  signal?: AbortSignal,
): Promise<Record<string, unknown>> {
  return getJson(
    `/v1/simulations/${pathSegment(runId)}/observer/agents/${pathSegment(agentId)}/semantic-history`,
    'subjective_debug',
    {
      source: query.source,
      tick: query.tick ?? undefined,
      from_tick: query.fromTick ?? undefined,
      to_tick: query.toTick ?? undefined,
      after: query.after ?? undefined,
      limit: query.limit ?? 100,
    },
    ensureSemanticHistory,
    signal,
  )
}

export function getLabels(
  runId: string,
  agentId: string,
  tick?: number | null,
  signal?: AbortSignal,
): Promise<Record<string, unknown>> {
  return getJson(
    `/v1/simulations/${pathSegment(runId)}/observer/agents/${pathSegment(agentId)}/labels`,
    'subjective_debug',
    { tick: tick ?? undefined },
    ensureLabelOverlay,
    signal,
  )
}

export function getSymbolicLanguage(
  runId: string,
  agentId: string,
  tick?: number | null,
  signal?: AbortSignal,
): Promise<Record<string, unknown>> {
  return getJson(
    `/v1/simulations/${pathSegment(runId)}/observer/agents/${pathSegment(agentId)}/symbolic-language`,
    'subjective_debug',
    { tick: tick ?? undefined },
    ensureSymbolicOverlay,
    signal,
  )
}

export function getTranslation(
  runId: string,
  agentId: string,
  tick?: number | null,
  signal?: AbortSignal,
): Promise<Record<string, unknown>> {
  return getJson(
    `/v1/simulations/${pathSegment(runId)}/observer/agents/${pathSegment(agentId)}/translation`,
    'subjective_debug',
    { tick: tick ?? undefined },
    ensureTranslationOverlay,
    signal,
  )
}

export function getNarrativeHops(
  runId: string,
  agentId: string,
  signal?: AbortSignal,
): Promise<Record<string, unknown>> {
  return getJson(
    `/v1/simulations/${pathSegment(runId)}/observer/agents/${pathSegment(agentId)}/narrative-hops`,
    'subjective_debug',
    {},
    ensureNarrativeHops,
    signal,
  )
}

export type LineageResolutionInput = {
  runId: string
  family: string
  evidenceClass: LineageScopeInput['evidenceClass']
  ownerId?: string | null
  publicationId?: string | null
  nativeKind: string
  nativeId: string
  identityOwner?: string | null
  nodeKey?: string | null
  maxSnapshotPages?: number
}

export class ResearchResolutionError extends Error {
  readonly code: string

  constructor(code: string) {
    super(code)
    this.name = 'ResearchResolutionError'
    this.code = code
  }
}

async function resolvePublication(
  input: LineageResolutionInput,
  signal?: AbortSignal,
): Promise<LineageSnapshot> {
  const target = input.publicationId
  if (target === null || target === undefined) {
    const page = await getLineageSnapshots(
      input.runId,
      input,
      { limit: 1 },
      signal,
    )
    const first = page.items[0]
    if (first === undefined) {
      throw new ResearchResolutionError('snapshot_unavailable')
    }
    return first
  }
  let after: string | null = null
  const maxPages = input.maxSnapshotPages ?? 20
  for (let pageIndex = 0; pageIndex < maxPages; pageIndex += 1) {
    const page: LineageSnapshotPage = await getLineageSnapshots(
      input.runId,
      input,
      { after, limit: 200 },
      signal,
    )
    const found = page.items.find((item) => item.publication_id === target)
    if (found !== undefined) {
      return found
    }
    if (page.next_cursor === null) {
      break
    }
    after = page.next_cursor
  }
  throw new ResearchResolutionError('publication_not_found')
}

/**
 * Resolve a qualified lineage focus through snapshot discovery.
 * Never sends publication_id or identity_owner as lineage query keys.
 */
export async function resolveLineageNode(
  input: LineageResolutionInput,
  signal?: AbortSignal,
): Promise<{ snapshot: LineageSnapshot; node: LineageNodeRef; graph: LineageGraph | null }> {
  const snapshot = await resolvePublication(input, signal)
  if (input.nodeKey !== null && input.nodeKey !== undefined) {
    const graph = await getLineageTraverse(
      input.runId,
      input,
      { rootKey: input.nodeKey, boundaryTick: snapshot.boundary_tick },
      signal,
    )
    if (
      graph.snapshot.publication_id !== snapshot.publication_id ||
      graph.snapshot.digest !== snapshot.digest
    ) {
      throw new ResearchResolutionError('research_snapshot_changed')
    }
    if (
      graph.root.key !== input.nodeKey ||
      graph.root.native_kind !== input.nativeKind ||
      graph.root.native_id !== input.nativeId ||
      (input.identityOwner !== undefined &&
        input.identityOwner !== null &&
        graph.root.identity_owner !== input.identityOwner)
    ) {
      throw new ResearchResolutionError('unsupported_research_schema')
    }
    return { snapshot, node: graph.root, graph }
  }
  const page = await getLineageNodes(
    input.runId,
    input,
    {
      nativeKind: input.nativeKind,
      nativeId: input.nativeId,
      boundaryTick: snapshot.boundary_tick,
      limit: 200,
    },
    signal,
  )
  if (
    page.snapshot.publication_id !== snapshot.publication_id ||
    page.snapshot.digest !== snapshot.digest
  ) {
    throw new ResearchResolutionError('research_snapshot_changed')
  }
  const matches = page.items.filter((item) => {
    const ref = item.ref
    return (
      ref.family === input.family &&
      ref.evidence_class === input.evidenceClass &&
      ref.native_kind === input.nativeKind &&
      ref.native_id === input.nativeId &&
      (input.identityOwner === undefined ||
        input.identityOwner === null ||
        ref.identity_owner === input.identityOwner)
    )
  })
  const node = matches[0]?.ref
  if (node === undefined) {
    throw new ResearchResolutionError('lineage_node_not_found')
  }
  if (matches.length > 1) {
    throw new ResearchResolutionError('ambiguous_lineage_node')
  }
  if (input.nodeKey != null && node.key !== input.nodeKey) {
    throw new ResearchResolutionError('research_snapshot_changed')
  }
  return { snapshot, node, graph: null }
}

export function decodeMetricPayloadBase64(payload: string): unknown {
  const binary = atob(payload)
  const bytes = new Uint8Array(binary.length)
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index)
  }
  const text = new TextDecoder('utf-8', { fatal: true }).decode(bytes)
  return parseBoundedJson(text, {
    maxBytes: 16 * 1024 * 1024,
    maxDepth: 32,
  })
}

export { ApiClientError, isRecord }

export function metricDocumentKey(input: {
  metric_set_id: string
  metric_family: string
  schema_version: string
}): string {
  return `${input.metric_set_id}\u0000${input.metric_family}\u0000${input.schema_version}`
}
