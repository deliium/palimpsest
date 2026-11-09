import { apiFetch } from './client'

export const CAPABILITY = 'subjective_debug'

export type InterSocietyRelationsSummary = {
  run_id: string
  publication_id: string
  digest: string
  schema_version: string
  pair_count: number
  window_count: number
  series_point_count: number
  comparison_count: number
  coverage: string
}

export type InterSocietyDomainPanel = {
  domain: string
  event_count: number
  availability: string
  coverage_observed: number
  coverage_expected: number
  values: Record<string, unknown>
}

export type InterSocietyPair = {
  pair_id: string
  society_a: string
  society_b: string
  window_tick: number
  status: string
  overlap_member_count: number
  panels: InterSocietyDomainPanel[]
}

export type InterSocietySeriesPoint = {
  pair_id: string
  window_index: number
  window_start_tick: number
  window_end_tick: number
  panels: InterSocietyDomainPanel[]
}

export type InterSocietyDomainDelta = {
  domain: string
  count_delta: number
  left_availability: string
  right_availability: string
}

export type InterSocietyComparison = {
  left_pair_id: string
  right_pair_id: string
  left_window_tick: number
  right_window_tick: number
  domain_deltas: InterSocietyDomainDelta[]
}

export type Page<T> = {
  items: T[]
  next_cursor?: string | null
}

export type InterSocietyListOptions = {
  cursor?: string
  limit?: number
}

function base(runId: string): string {
  return `/v1/simulations/${encodeURIComponent(runId)}/inter-society-relations`
}

export function fetchInterSocietyRelationsSummary(
  runId: string,
): Promise<InterSocietyRelationsSummary> {
  return apiFetch<InterSocietyRelationsSummary>(base(runId), {
    capability: CAPABILITY,
  })
}

export function fetchInterSocietyPairs(
  runId: string,
  options: InterSocietyListOptions = {},
): Promise<Page<InterSocietyPair>> {
  return apiFetch<Page<InterSocietyPair>>(`${base(runId)}/pairs`, {
    capability: CAPABILITY,
    query: {
      cursor: options.cursor,
      limit: options.limit ?? 200,
    },
  })
}

export function fetchInterSocietyPair(
  runId: string,
  pairId: string,
): Promise<InterSocietyPair> {
  return apiFetch<InterSocietyPair>(
    `${base(runId)}/pairs/${encodeURIComponent(pairId)}`,
    { capability: CAPABILITY },
  )
}

export function fetchInterSocietyPairSeries(
  runId: string,
  pairId: string,
  options: InterSocietyListOptions = {},
): Promise<Page<InterSocietySeriesPoint>> {
  return apiFetch<Page<InterSocietySeriesPoint>>(
    `${base(runId)}/pairs/${encodeURIComponent(pairId)}/series`,
    {
      capability: CAPABILITY,
      query: {
        cursor: options.cursor,
        limit: options.limit ?? 200,
      },
    },
  )
}

export function fetchInterSocietyWindows(
  runId: string,
  options: InterSocietyListOptions = {},
): Promise<Page<InterSocietySeriesPoint>> {
  return apiFetch<Page<InterSocietySeriesPoint>>(`${base(runId)}/windows`, {
    capability: CAPABILITY,
    query: {
      cursor: options.cursor,
      limit: options.limit ?? 200,
    },
  })
}

export function fetchInterSocietyComparisonByPairs(
  runId: string,
  pairA: string,
  pairB: string,
): Promise<InterSocietyComparison> {
  return apiFetch<InterSocietyComparison>(`${base(runId)}/comparison`, {
    capability: CAPABILITY,
    query: { pair_a: pairA, pair_b: pairB },
  })
}

export function fetchInterSocietyComparisonByWindows(
  runId: string,
  pairId: string,
  windowA: number,
  windowB: number,
): Promise<InterSocietyComparison> {
  return apiFetch<InterSocietyComparison>(`${base(runId)}/comparison`, {
    capability: CAPABILITY,
    query: {
      pair_id: pairId,
      window_a: windowA,
      window_b: windowB,
    },
  })
}
