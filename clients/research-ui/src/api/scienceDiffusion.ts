import { apiFetch } from './client'

export const CAPABILITY = 'subjective_debug'

export type ScienceDiffusionSummary = {
  run_id: string
  publication_id: string
  snapshot_digest: string
  schema_version: string
  policy_version: string
  input_revision: string
  boundary_tick: number
  counts: Record<string, number>
  publications: string[]
}

export type ScienceDiffusionRow = Record<string, any>

export type ScienceDiffusionSection =
  | 'coverage'
  | 'versions'
  | 'transmissions'
  | 'changes'
  | 'genealogy'

export type ScienceDiffusionPage = {
  run_id: string
  publication_id: string
  snapshot_digest: string
  section: ScienceDiffusionSection
  rows: ScienceDiffusionRow[]
  next_cursor: string | null
  truncated: boolean
}

export type ScienceDiffusionQuery = {
  publicationId?: string
  cursor?: string
  limit?: number
}

const BASE = '/v1/simulations'

export function buildScienceDiffusionQuery(
  query: ScienceDiffusionQuery = {},
): string {
  const params = new URLSearchParams()
  if (query.publicationId) params.set('publication_id', query.publicationId)
  if (query.cursor) params.set('cursor', query.cursor)
  if (query.limit !== undefined) params.set('limit', String(query.limit))
  const text = params.toString()
  return text ? `?${text}` : ''
}

export async function getScienceDiffusionSummary(
  runId: string,
  publicationId?: string,
): Promise<ScienceDiffusionSummary> {
  const suffix = publicationId
    ? `?publication_id=${encodeURIComponent(publicationId)}`
    : ''
  return apiFetch<ScienceDiffusionSummary>(
    `${BASE}/${encodeURIComponent(runId)}/science-diffusion${suffix}`,
    { capability: CAPABILITY },
  )
}

export async function getScienceDiffusionPage(
  runId: string,
  section: ScienceDiffusionSection,
  query: ScienceDiffusionQuery = {},
): Promise<ScienceDiffusionPage> {
  return apiFetch<ScienceDiffusionPage>(
    `${BASE}/${encodeURIComponent(runId)}/science-diffusion/${section}${buildScienceDiffusionQuery(query)}`,
    { capability: CAPABILITY },
  )
}
