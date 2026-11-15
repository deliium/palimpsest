import { apiFetch } from './client'

export const CAPABILITY = 'subjective_debug'

export type SocialMobilitySummary = {
  run_id: string
  publication_id: string
  digest: string
  schema_version: string
  domain_row_count: number
  generation_row_count: number
  lag_row_count: number
  window_count: number
  owner_count: number
  generation_count: number
  genealogy_edge_count: number
  pair_count: number
  resolved_pair_count: number
  unresolved_pair_count: number
  domain_available_count: number
  coverage: string
  evidence_coverage: string
  domain_coverage: string
  generation_coverage: string
  truncated: boolean
}

export type SocialMobilityPage<T> = {
  run_id: string
  publication_id: string
  window_index: number | null
  rows: T[]
  next_cursor: string | null
  coverage: string
}

export type SocialMobilityDomainRow = {
  window_index: number
  window_tick: number
  domain: string
  measure: string
  pair_count: number
  resolved_pair_count: number
  rank_correlation_milli: number
  same_bin_share_milli: number
  upward_share_milli: number
  downward_share_milli: number
  mean_absolute_rank_change_milli: number
  persistence_direction: string
  coverage: string
  availability: string
}

export type SocialMobilityGenerationRow = {
  window_index: number
  window_tick: number
  generation_index: number
  owner_count: number
  pair_count: number
  comparable: boolean
  same_bin_share_milli: number
  upward_share_milli: number
  downward_share_milli: number
  coverage: string
  availability: string
}

export type SocialMobilityLagRow = {
  window_index: number
  window_tick: number
  generation_lag: number
  pair_count: number
  comparable: boolean
  same_bin_share_milli: number
  upward_share_milli: number
  downward_share_milli: number
  coverage: string
  availability: string
}

export type SocialMobilityCoverageRow = {
  window_index: number
  window_tick: number
  generation_count: number
  owner_count: number
  genealogy_edge_count: number
  pair_count: number
  resolved_pair_count: number
  unresolved_pair_count: number
  domain_available_count: number
  truncated: boolean
  coverage: string
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
  `/v1/simulations/${encodeURIComponent(runId)}/social-mobility`

export function getSummary(runId: string): Promise<SocialMobilitySummary> {
  return apiFetch<SocialMobilitySummary>(base(runId), {
    capability: CAPABILITY,
  })
}

export function getDomains(
  runId: string,
  options: PageOptions = {},
): Promise<SocialMobilityPage<SocialMobilityDomainRow>> {
  return apiFetch<SocialMobilityPage<SocialMobilityDomainRow>>(
    `${base(runId)}/domains${query(options)}`,
    { capability: CAPABILITY },
  )
}

export function getEconomy(
  runId: string,
  options: PageOptions = {},
): Promise<SocialMobilityPage<SocialMobilityDomainRow>> {
  return apiFetch<SocialMobilityPage<SocialMobilityDomainRow>>(
    `${base(runId)}/economy${query(options)}`,
    { capability: CAPABILITY },
  )
}

export function getHumanCapital(
  runId: string,
  options: PageOptions = {},
): Promise<SocialMobilityPage<SocialMobilityDomainRow>> {
  return apiFetch<SocialMobilityPage<SocialMobilityDomainRow>>(
    `${base(runId)}/human-capital${query(options)}`,
    { capability: CAPABILITY },
  )
}

export function getStanding(
  runId: string,
  options: PageOptions = {},
): Promise<SocialMobilityPage<SocialMobilityDomainRow>> {
  return apiFetch<SocialMobilityPage<SocialMobilityDomainRow>>(
    `${base(runId)}/standing${query(options)}`,
    { capability: CAPABILITY },
  )
}

export function getGenerations(
  runId: string,
  options: PageOptions = {},
): Promise<
  SocialMobilityPage<SocialMobilityGenerationRow | SocialMobilityLagRow>
> {
  return apiFetch<
    SocialMobilityPage<SocialMobilityGenerationRow | SocialMobilityLagRow>
  >(`${base(runId)}/generations${query(options)}`, {
    capability: CAPABILITY,
  })
}

export function getCoverage(
  runId: string,
  options: PageOptions = {},
): Promise<SocialMobilityPage<SocialMobilityCoverageRow>> {
  return apiFetch<SocialMobilityPage<SocialMobilityCoverageRow>>(
    `${base(runId)}/coverage${query(options)}`,
    { capability: CAPABILITY },
  )
}
