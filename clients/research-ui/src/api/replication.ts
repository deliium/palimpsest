import { apiFetch } from './client'

export const CAPABILITY = 'subjective_debug'

export type ReplicationSummary = {
  run_id: string
  publication_id: string
  internal_digest: string
  policy_version: string
  summary: {
    design_count: number
    attempt_count: number
    execution_count: number
    report_count: number
    comparison_count: number
    interpretation_count: number
    collaboration_count: number
    participant_count: number
    first_tick: number | null
    last_tick: number | null
    coverage: string
    availability: string
    reason_codes: string[]
  }
}

export type ReplicationExecutionRow = {
  record_type: 'execution'
  row_kind: 'execution'
  layer: 'objective'
  row_token: string
  window_index: number
  fact: {
    execution_token: string
    result_root_token: string
    participant_token: string
    execution_tick: number
    operator: string
    process_token: string
    operand_a_token: string | null
    operand_b_token: string | null
    outcome: string
  }
}

export type ReplicationReportRow = {
  record_type: 'report'
  row_kind: 'report'
  layer: 'owner_scoped'
  row_token: string
  window_index: number
  associated_execution_token: string | null
  fact: {
    origin_report_token: string
    participant_token: string
    design_token: string
    source_trial_token: string
    result_root_token: string
    measurement: {
      outcome: string | null
      resolution: string
      uncertainty_kind: 'unreported' | 'declared_set'
      possible_outcomes: string[]
      basis: string
    }
    declared_measurement_basis: string
    condition_snapshot: { slot: string; token: string }[]
  }
}

export type ReplicationResultRow = ReplicationExecutionRow | ReplicationReportRow

export type ReplicationRow = Record<string, any>

export type ReplicationPage<T extends ReplicationRow = ReplicationRow> = {
  run_id: string
  publication_id: string
  internal_digest: string
  policy_version: string
  coverage: string | null
  availability: string | null
  rows: T[]
  next_cursor: string | null
  truncated: boolean
}

export type ReplicationSection =
  | 'designs'
  | 'attempts'
  | 'results'
  | 'comparisons'
  | 'interpretations'
  | 'collaborations'
  | 'coverage'

export type ReplicationQuery = {
  publicationId?: string
  cursor?: string
  limit?: number
  windowIndex?: number
  designToken?: string
  collaborationToken?: string
}

const BASE = '/v1/simulations'

export function buildReplicationQuery(query: ReplicationQuery = {}): string {
  const params = new URLSearchParams()
  if (query.publicationId) params.set('publication_id', query.publicationId)
  if (query.cursor) params.set('cursor', query.cursor)
  if (query.limit !== undefined) params.set('limit', String(query.limit))
  if (query.windowIndex !== undefined) params.set('window_index', String(query.windowIndex))
  if (query.designToken) params.set('design_token', query.designToken)
  if (query.collaborationToken) params.set('collaboration_token', query.collaborationToken)
  const text = params.toString()
  return text ? `?${text}` : ''
}

export function validateReplicationQuery(
  section: ReplicationSection,
  query: ReplicationQuery,
): void {
  if (
    (section === 'results' || section === 'coverage') &&
    (query.designToken || query.collaborationToken)
  ) {
    throw new Error('scientific_replication_filter_invalid')
  }
  if (section === 'designs' && query.collaborationToken) {
    throw new Error('scientific_replication_filter_invalid')
  }
}

export async function getReplicationSummary(
  runId: string,
  publicationId?: string,
): Promise<ReplicationSummary> {
  const suffix = publicationId
    ? `?publication_id=${encodeURIComponent(publicationId)}`
    : ''
  const url = `${BASE}/${encodeURIComponent(runId)}/scientific-replication${suffix}`
  return apiFetch<ReplicationSummary>(url, {
    capability: CAPABILITY,
  })
}

export async function getReplicationPage<T extends ReplicationRow = ReplicationRow>(
  runId: string,
  section: ReplicationSection,
  query: ReplicationQuery = {},
): Promise<ReplicationPage<T>> {
  validateReplicationQuery(section, query)
  return apiFetch<ReplicationPage<T>>(
    `${BASE}/${encodeURIComponent(runId)}/scientific-replication/${section}${buildReplicationQuery(query)}`,
    { capability: CAPABILITY },
  )
}
