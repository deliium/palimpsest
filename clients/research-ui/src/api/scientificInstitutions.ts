import { apiFetch } from './client'

export const CAPABILITY = 'subjective_debug'

export type ScientificInstitutionsSummary = {
  run_id: string
  publication_id: string
  snapshot_digest: string
  schema_version: string
  policy_version: string
  input_revision: string
  boundary_tick: number
  counts: Record<string, number>
  summary: Record<string, number>
  publications: string[]
}

export type ScientificInstitutionsRow = Record<string, any>

export type ScientificInstitutionsSection =
  | 'windows'
  | 'practice'
  | 'signals'
  | 'lineage'

export type ScientificInstitutionsPage = {
  run_id: string
  publication_id: string
  snapshot_digest: string
  section: ScientificInstitutionsSection
  rows: ScientificInstitutionsRow[]
  next_cursor: string | null
  truncated: boolean
}

export type ScientificInstitutionsQuery = {
  publicationId?: string
  cursor?: string
  limit?: number
}

const BASE = '/v1/simulations'

export function buildScientificInstitutionsQuery(
  query: ScientificInstitutionsQuery = {},
): string {
  const params = new URLSearchParams()
  if (query.publicationId) params.set('publication_id', query.publicationId)
  if (query.cursor) params.set('cursor', query.cursor)
  if (query.limit !== undefined) params.set('limit', String(query.limit))
  const text = params.toString()
  return text ? `?${text}` : ''
}

export async function getScientificInstitutionsSummary(
  runId: string,
  publicationId?: string,
): Promise<ScientificInstitutionsSummary> {
  const suffix = publicationId
    ? `?publication_id=${encodeURIComponent(publicationId)}`
    : ''
  return apiFetch<ScientificInstitutionsSummary>(
    `${BASE}/${encodeURIComponent(runId)}/scientific-institutions${suffix}`,
    { capability: CAPABILITY },
  )
}

export async function getScientificInstitutionsPage(
  runId: string,
  section: ScientificInstitutionsSection,
  query: ScientificInstitutionsQuery = {},
): Promise<ScientificInstitutionsPage> {
  return apiFetch<ScientificInstitutionsPage>(
    `${BASE}/${encodeURIComponent(runId)}/scientific-institutions/${section}${buildScientificInstitutionsQuery(query)}`,
    { capability: CAPABILITY },
  )
}
