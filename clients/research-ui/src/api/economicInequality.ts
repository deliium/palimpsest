import { apiFetch } from './client'

export const CAPABILITY = 'subjective_debug'

export type EconomicInequalitySummary = {
  run_id: string
  publication_id: string
  digest: string
  schema_version: string
  dimension_row_count: number
  cohort_row_count: number
  society_row_count: number
  window_count: number
  owner_count: number
  observed_owner_count: number
  overlap_member_count: number
  coverage: string
  evidence_coverage: string
  dimension_coverage: string
  comparison_coverage: string
  truncated: boolean
}

export type EconomicInequalityPage<T> = {
  run_id: string
  publication_id: string
  window_index: number | null
  rows: T[]
  next_cursor: string | null
  coverage: string
}

export type EconomicDimension = {
  dimension: string
  measure: string
  window_index: number
  window_tick: number
  owner_count: number
  observed_owner_count: number
  minimum: number | null
  p25: number | null
  median: number | null
  p75: number | null
  maximum: number | null
  iqr: number | null
  dispersion: number | null
  bin_shares_milli: number[]
  gini_milli: number | null
  theil_t_milli: number | null
  atkinson_eps_1_milli: number | null
  top_share_milli: number | null
  availability: string
  coverage: string
}

export type EconomicCohort = {
  cohort_token: string
  generation_index: number
  window_index: number
  owner_count: number
  comparable: boolean
  gini_milli: number | null
  median_milli: number | null
  iqr_milli: number | null
  trend: string
  availability: string
}

export type EconomicSociety = {
  society_token: string
  window_index: number
  owner_count: number
  comparable: boolean
  gini_milli: number | null
  median_milli: number | null
  iqr_milli: number | null
  trend: string
  availability: string
}

type PageOptions = {
  limit?: number | undefined
  cursor?: string | null | undefined
  windowIndex?: number | undefined
}

function query(options: PageOptions): string {
  const params = new URLSearchParams()
  if (options.limit !== undefined) params.set('limit', String(options.limit))
  if (options.cursor) params.set('cursor', options.cursor)
  if (options.windowIndex !== undefined) {
    params.set('window_index', String(options.windowIndex))
  }
  const text = params.toString()
  return text ? `?${text}` : ''
}

const base = (runId: string): string =>
  `/v1/simulations/${encodeURIComponent(runId)}/economic-inequality`

export function getSummary(runId: string): Promise<EconomicInequalitySummary> {
  return apiFetch<EconomicInequalitySummary>(base(runId), {
    capability: CAPABILITY,
  })
}

export function getDimensions(
  runId: string,
  options: PageOptions = {},
): Promise<EconomicInequalityPage<EconomicDimension>> {
  return apiFetch<EconomicInequalityPage<EconomicDimension>>(
    `${base(runId)}/dimensions${query(options)}`,
    { capability: CAPABILITY },
  )
}

export function getCohorts(
  runId: string,
  options: PageOptions = {},
): Promise<EconomicInequalityPage<EconomicCohort>> {
  return apiFetch<EconomicInequalityPage<EconomicCohort>>(
    `${base(runId)}/cohorts${query(options)}`,
    { capability: CAPABILITY },
  )
}

export function getSocieties(
  runId: string,
  options: PageOptions = {},
): Promise<EconomicInequalityPage<EconomicSociety>> {
  return apiFetch<EconomicInequalityPage<EconomicSociety>>(
    `${base(runId)}/societies${query(options)}`,
    { capability: CAPABILITY },
  )
}
