import { apiFetch } from './client'

export const CAPABILITY = 'subjective_debug'

export type ScientificModelsSummary = {
  run_id: string
  publication_id: string
  snapshot_digest: string
  schema_version: string
  policy_version: string
  finalized_through_tick: number
  coverage_status: 'complete' | 'partial' | 'absent'
  counts: Record<string, number>
  publications: string[]
}

export type ScientificModelsRow = Record<string, any>

export type ScientificModelsPage<T extends ScientificModelsRow = ScientificModelsRow> = {
  run_id: string
  publication_id: string
  snapshot_digest: string
  section: ScientificModelsSection
  rows: T[]
  next_cursor: string | null
  truncated: boolean
}

export type ScientificModelsSection =
  | 'models'
  | 'predictions'
  | 'outcomes'
  | 'calibration'
  | 'revisions'
  | 'comparisons'
  | 'coverage'

export type ScientificModelsQuery = {
  publicationId?: string
  cursor?: string
  limit?: number
  modelToken?: string
  targetKind?: string
  status?: string
  issuedFromTick?: number
  issuedThroughTick?: number
}

const BASE = '/v1/simulations'

export function buildScientificModelsQuery(
  query: ScientificModelsQuery = {},
): string {
  const params = new URLSearchParams()
  if (query.publicationId) params.set('publication_id', query.publicationId)
  if (query.cursor) params.set('cursor', query.cursor)
  if (query.limit !== undefined) params.set('limit', String(query.limit))
  if (query.modelToken) params.set('model_token', query.modelToken)
  if (query.targetKind) params.set('target_kind', query.targetKind)
  if (query.status) params.set('status', query.status)
  if (query.issuedFromTick !== undefined) {
    params.set('issued_from_tick', String(query.issuedFromTick))
  }
  if (query.issuedThroughTick !== undefined) {
    params.set('issued_through_tick', String(query.issuedThroughTick))
  }
  const text = params.toString()
  return text ? `?${text}` : ''
}

export async function getScientificModelsSummary(
  runId: string,
  publicationId?: string,
): Promise<ScientificModelsSummary> {
  const suffix = publicationId
    ? `?publication_id=${encodeURIComponent(publicationId)}`
    : ''
  return apiFetch<ScientificModelsSummary>(
    `${BASE}/${encodeURIComponent(runId)}/scientific-models${suffix}`,
    { capability: CAPABILITY },
  )
}

export async function getScientificModelsPage<
  T extends ScientificModelsRow = ScientificModelsRow,
>(
  runId: string,
  section: ScientificModelsSection,
  query: ScientificModelsQuery = {},
): Promise<ScientificModelsPage<T>> {
  return apiFetch<ScientificModelsPage<T>>(
    `${BASE}/${encodeURIComponent(runId)}/scientific-models/${section}${buildScientificModelsQuery(query)}`,
    { capability: CAPABILITY },
  )
}
