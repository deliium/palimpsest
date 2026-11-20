import { apiFetch } from './client'

export const CAPABILITY = 'subjective_debug'

export type CompetingTheoriesSummary = {
  run_id: string
  publication_id: string
  snapshot_digest: string
  schema_version: string
  counts: Record<string, number>
  summary: Record<string, number>
  omitted_windows: number
  first_retained_window: number
  publications: string[]
}

export type CompetingTheoriesRow = Record<string, any>

export type CompetingTheoriesSection =
  | 'theories'
  | 'support'
  | 'citations'
  | 'predictions'
  | 'failures'
  | 'transmission'
  | 'coverage'

export type CompetingTheoriesPage = {
  run_id: string
  publication_id: string
  snapshot_digest: string
  section: CompetingTheoriesSection
  rows: CompetingTheoriesRow[]
  next_cursor: string | null
  truncated: boolean
}

export type CompetingTheoriesQuery = {
  publicationId?: string
  cursor?: string
  limit?: number
  window?: number
  theoryId?: string
}

const BASE = '/v1/simulations'

export function buildCompetingTheoriesQuery(
  query: CompetingTheoriesQuery = {},
): string {
  const params = new URLSearchParams()
  if (query.publicationId) params.set('publication_id', query.publicationId)
  if (query.cursor) params.set('cursor', query.cursor)
  if (query.limit !== undefined) params.set('limit', String(query.limit))
  if (query.window !== undefined) params.set('window', String(query.window))
  if (query.theoryId) params.set('theory_id', query.theoryId)
  const text = params.toString()
  return text ? `?${text}` : ''
}

export async function getCompetingTheoriesSummary(
  runId: string,
  publicationId?: string,
): Promise<CompetingTheoriesSummary> {
  const suffix = publicationId
    ? `?publication_id=${encodeURIComponent(publicationId)}`
    : ''
  return apiFetch<CompetingTheoriesSummary>(
    `${BASE}/${encodeURIComponent(runId)}/competing-theories${suffix}`,
    { capability: CAPABILITY },
  )
}

export async function getCompetingTheoriesPage(
  runId: string,
  section: CompetingTheoriesSection,
  query: CompetingTheoriesQuery = {},
): Promise<CompetingTheoriesPage> {
  return apiFetch<CompetingTheoriesPage>(
    `${BASE}/${encodeURIComponent(runId)}/competing-theories/${section}${buildCompetingTheoriesQuery(query)}`,
    { capability: CAPABILITY },
  )
}
