import {
  type CapabilitySlot,
  credentialFor,
} from '../auth/credentials'

export type ApiErrorBody = {
  code?: string
  title?: string
  detail?: string
}

export class ApiClientError extends Error {
  readonly status: number
  readonly code: string

  constructor(status: number, code: string, message?: string) {
    super(message ?? code)
    this.name = 'ApiClientError'
    this.status = status
    this.code = code
  }
}

export type FetchOptions = {
  capability: CapabilitySlot
  query?: Record<string, string | number | undefined | null>
  method?: 'GET' | 'POST'
  body?: unknown
}

function buildUrl(path: string, query?: FetchOptions['query']): string {
  const url = new URL(path, window.location.origin)
  if (query !== undefined) {
    for (const [key, value] of Object.entries(query)) {
      if (value === undefined || value === null || value === '') {
        continue
      }
      url.searchParams.set(key, String(value))
    }
  }
  return url.pathname + url.search
}

export async function apiFetch<T>(
  path: string,
  options: FetchOptions,
): Promise<T> {
  const headers: Record<string, string> = {
    Accept: 'application/json',
  }
  const token = credentialFor(options.capability)
  if (token !== null) {
    headers['x-palimpsest-token'] = token
  }
  const method = options.method ?? 'GET'
  if (method !== 'GET') {
    headers['Content-Type'] = 'application/json'
  }

  const url = buildUrl(path, options.query)
  if (import.meta.env.DEV) {
    console.debug(`research_ui_fetch path=${path} capability=${options.capability}`)
  }

  const init: RequestInit = { method, headers }
  if (options.body !== undefined) {
    init.body = JSON.stringify(options.body)
  }
  const response = await fetch(url, init)

  if (import.meta.env.DEV) {
    console.debug(
      `research_ui_fetch_status path=${path} status=${response.status}`,
    )
  }

  if (!response.ok) {
    let code = `http_${response.status}`
    try {
      const problem = (await response.json()) as ApiErrorBody
      if (typeof problem.code === 'string' && problem.code !== '') {
        code = problem.code
      }
    } catch {
      // ignore non-JSON error bodies
    }
    throw new ApiClientError(response.status, code)
  }

  return (await response.json()) as T
}

export type RunListItem = {
  run_id: string
  lifecycle_state: string
  ticks_committed: number
  progress_cursor: number
  config_schema_version: string | null
  terminal_reason_code: string | null
}

export type RunListOut = {
  items: RunListItem[]
  next_cursor: string | null
  count: number
}

export type ObserverRunOut = {
  run_id: string
  world_id: string
  tick: number
  latest_tick: number | null
  latest_sequence: number | null
  parent_run_id: string | null
  fork_tick: number | null
  intervention_summary: string | null
  branch_id: string | null
  protocol_version: string
}

export type ExperimentalStateOut = {
  run_id: string
  experiment_id: string | null
  membership_source: string | null
  has_assignment: boolean
  availability: string
}

export type BranchLineageOut = {
  child_run_id: string
  parent_run_id: string
  fork_tick: number
  intervention_kind: string
  intervention_summary: string
  branch_id: string
}

export function listInspectRuns(after?: string | null): Promise<RunListOut> {
  return apiFetch<RunListOut>('/v1/research/runs', {
    capability: 'objective_inspection',
    query: { after: after ?? undefined, limit: 50 },
  })
}

export function getObserverRun(runId: string): Promise<ObserverRunOut> {
  return apiFetch<ObserverRunOut>(`/v1/simulations/${runId}/observer/run`, {
    capability: 'objective_inspection',
  })
}

export function getExperimental(runId: string): Promise<ExperimentalStateOut> {
  return apiFetch<ExperimentalStateOut>(
    `/v1/simulations/${runId}/experimental`,
    { capability: 'objective_inspection' },
  )
}

export function getBranchLineage(runId: string): Promise<BranchLineageOut> {
  return apiFetch<BranchLineageOut>(`/v1/simulations/${runId}/branch`, {
    capability: 'objective_inspection',
  })
}

export type ProjectionAvailability = 'available' | 'unavailable' | 'partial'

export type GoalsProjection = {
  owner_id: string
  availability: ProjectionAvailability
  head_count: number
  items: Array<{
    goal_id: string
    status: string
    horizon: string
    priority: number
    confidence: number | null
    created_tick: number
  }>
}

export type EmotionalProjection = {
  owner_id: string
  availability: ProjectionAvailability
  head_count: number
  intensities: Array<{ kind: string; intensity: number }>
  note?: string
}

export type SelfModelProjection = {
  owner_id: string
  availability: ProjectionAvailability
  identity_tick: number | null
  identity_operation_count: number
  goal_count: number
  goal_ids: string[]
  note: string
}

export type LedgerProjection = {
  owner_id: string
  availability: ProjectionAvailability
  head_count: number
  items: Array<{
    item_id: string
    kind_code: string
    status: string | null
    strength: number | null
    target_id: string | null
    evidence_count: number
  }>
}

export type GraphSummary = {
  run_id: string
  owner_id: string
  kind: 'memories' | 'beliefs'
  availability: ProjectionAvailability
  count: number
  items: Array<{
    node_id: string
    created_tick: number
    source_kind: string | null
    strength: number | null
    target_id: string | null
    lineage_ref_ids: string[]
  }>
}

export type RelationshipPage = {
  run_id: string
  owner_id: string
  count: number
  items: Array<{
    owner_id: string
    target_id: string
    dimensions: Array<{ dimension: string; value: number }>
  }>
}

function debugGet<T>(path: string): Promise<T> {
  return apiFetch<T>(path, { capability: 'subjective_debug' })
}

export const getGoals = (runId: string, ownerId: string) =>
  debugGet<GoalsProjection>(`/v1/simulations/${runId}/owners/${ownerId}/goals`)

export const getEmotionalState = (runId: string, ownerId: string) =>
  debugGet<EmotionalProjection>(
    `/v1/simulations/${runId}/owners/${ownerId}/emotional-state`,
  )

export const getSelfModel = (runId: string, ownerId: string) =>
  debugGet<SelfModelProjection>(
    `/v1/simulations/${runId}/owners/${ownerId}/self-model`,
  )

export const getTheoryOfMind = (runId: string, ownerId: string) =>
  debugGet<LedgerProjection>(
    `/v1/simulations/${runId}/owners/${ownerId}/theory-of-mind`,
  )

export const getMemorySummary = (runId: string, ownerId: string) =>
  debugGet<GraphSummary>(
    `/v1/simulations/${runId}/owners/${ownerId}/memories/summary`,
  )

export const getBeliefSummary = (runId: string, ownerId: string) =>
  debugGet<GraphSummary>(
    `/v1/simulations/${runId}/owners/${ownerId}/beliefs/summary`,
  )

export const getObserverRelationships = (runId: string, ownerId: string) =>
  debugGet<RelationshipPage>(
    `/v1/simulations/${runId}/observer/agents/${ownerId}/relationships`,
  )

export type ObserverEventOut = {
  type: string
  domain_kind: string
  event_id: string
  tick: number
  sequence: number
  actor_id: string | null
  target_id: string | null
}

export type ObserverEventPage = {
  run_id: string
  count: number
  events: ObserverEventOut[]
  limit: number
}

export type MetricCatalogItem = {
  metric_set_id: string
  metric_family: string
  evidence_manifest_hash: string
  schema_version: string
  content_hash_prefix: string
}

export type MetricCatalog = {
  run_id: string
  items: MetricCatalogItem[]
  count: number
  availability: string
}

export type MetricDocument = {
  run_id: string
  metric_set_id: string
  metric_family: string
  evidence_manifest_hash: string
  schema_version: string
  content_hash: string
  payload_b64: string
  availability: string
}

export type EventSummary = {
  tick: number
  sequence: number
  kind: string
}

export type EventPage = {
  run_id: string
  count: number
  events: EventSummary[]
  availability: string
}

export type AgentVisible = {
  run_id: string
  tick: number
  agent_id: string
  entity_id: string
  availability: string
  occurrence_count: number
  communication_count: number
}

export type CausalTraceNode = {
  stage_code: string
  status: string
  reason_code: string | null
  confidence: number | null
  uncertainty_band: string | null
  command_kind: string | null
  observer_focus: Array<{
    run_id: string
    tick: number
    sequence: number | null
    event_id: string | null
  }>
  secondary: boolean
}

export type CausalTrace = {
  address: {
    run_id: string
    tick: number
    event_id: string | null
    sequence: number | null
    agent_id: string | null
  }
  availability: string
  nodes: CausalTraceNode[]
  invocation_id: string | null
  ambiguity: boolean
  reason_code: string | null
  command_kind: string | null
  supporting_nodes: CausalTraceNode[]
}

export type DebuggerInvocationPage = {
  run_id: string
  agent_id: string
  tick: number | null
  items: Array<{
    invocation_id: string
    agent_id: string
    tick: number
    command_kind: string | null
    content_hash_prefix: string
  }>
  count: number
  availability: string
}

export function getObserverEvents(
  runId: string,
  query?: {
    agentId?: string | null
    eventType?: string | null
    limit?: number
  },
): Promise<ObserverEventPage> {
  return apiFetch<ObserverEventPage>(`/v1/simulations/${runId}/observer/events`, {
    capability: 'objective_inspection',
    query: {
      agent_id: query?.agentId ?? undefined,
      event_type: query?.eventType ?? undefined,
      limit: query?.limit ?? 200,
    },
  })
}

export function getMetricCatalog(runId: string): Promise<MetricCatalog> {
  return apiFetch<MetricCatalog>(`/v1/simulations/${runId}/metrics`, {
    capability: 'objective_inspection',
  })
}

export function getMetricDocument(
  runId: string,
  metricSetId: string,
  metricFamily: string,
): Promise<MetricDocument> {
  return apiFetch<MetricDocument>(
    `/v1/simulations/${runId}/metrics/${encodeURIComponent(metricSetId)}/${encodeURIComponent(metricFamily)}`,
    { capability: 'objective_inspection' },
  )
}

export function getInspectionEvents(
  runId: string,
  limit = 50,
): Promise<EventPage> {
  return apiFetch<EventPage>(`/v1/simulations/${runId}/events`, {
    capability: 'objective_inspection',
    query: { limit },
  })
}

export function getAgentObservation(
  runId: string,
  agentId: string,
): Promise<AgentVisible> {
  return apiFetch<AgentVisible>(
    `/v1/simulations/${runId}/agents/${encodeURIComponent(agentId)}/observation`,
    { capability: 'agent_visible' },
  )
}

export function getCausalTraceByEvent(
  runId: string,
  eventId: string,
): Promise<CausalTrace> {
  return apiFetch<CausalTrace>(
    `/v1/simulations/${runId}/debugger/events/${encodeURIComponent(eventId)}/causal-trace`,
    { capability: 'subjective_debug' },
  )
}

export function getCausalTraceByCursor(
  runId: string,
  tick: number,
  sequence: number,
): Promise<CausalTrace> {
  return apiFetch<CausalTrace>(
    `/v1/simulations/${runId}/debugger/causal-trace`,
    {
      capability: 'subjective_debug',
      query: { tick, sequence },
    },
  )
}

export function listDebuggerInvocations(
  runId: string,
  agentId: string,
  tick?: number | null,
): Promise<DebuggerInvocationPage> {
  return apiFetch<DebuggerInvocationPage>(
    `/v1/simulations/${runId}/debugger/agents/${encodeURIComponent(agentId)}/invocations`,
    {
      capability: 'subjective_debug',
      query: { tick: tick ?? undefined },
    },
  )
}

export const getGroupFormation = (runId: string, ownerId: string) =>
  debugGet<LedgerProjection>(
    `/v1/simulations/${runId}/owners/${ownerId}/group-formation`,
  )

export const getSocialNorms = (runId: string, ownerId: string) =>
  debugGet<LedgerProjection>(
    `/v1/simulations/${runId}/owners/${ownerId}/social-norms`,
  )

export const getSocialConventions = (runId: string, ownerId: string) =>
  debugGet<LedgerProjection>(
    `/v1/simulations/${runId}/owners/${ownerId}/social-conventions`,
  )

export const getCulturalNarratives = (runId: string, ownerId: string) =>
  debugGet<LedgerProjection>(
    `/v1/simulations/${runId}/owners/${ownerId}/cultural-narratives`,
  )
