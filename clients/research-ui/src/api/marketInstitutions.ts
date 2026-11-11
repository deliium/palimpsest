import { apiFetch } from './client'

export const CAPABILITY = 'subjective_debug'

export type MarketVenue = {
  venue_id: string
  window_index: number
  location_id: string
  exchange_count: number
  proposal_count: number
  withdrawn_count: number
  distinct_party_count: number
  distinct_actor_count: number
  active_window_count: number
  recurrence_milli: number
  status: string
  market_like: boolean
  coverage: string
}

export type MarketGathering = {
  venue_id: string
  window_index: number
  location_id: string
  exchange_count: number
  proposal_count: number
  withdrawn_count: number
  distinct_party_count: number
  status: string
  coverage: string
}

export type MarketExpectation = {
  venue_id: string
  window_index: number
  owner_token: string
  expectation: string
  cadence: string
  interval_ticks: number | null
  phase_tick: number | null
  schedule_window_index: number | null
  confidence_milli: number
  evidence_count: number
  alignment: string
  coverage: string
}

export type MarketRole = {
  venue_id: string
  window_index: number
  actor_token: string
  role_kind: string
  role_basis: string
  recognized: boolean
  exchange_count: number
  counterparty_count: number
  active_window_count: number
  coverage: string
}

export type MarketRecord = {
  venue_id: string
  window_index: number
  record_kind: string
  anchor_token: string
  owner_row_count: number
  coverage: string
}

export type MarketCandidate = {
  market_id: string
  window_index: number
  venue_ids: string[]
  exchange_count: number
  distinct_party_count: number
  coverage: string
}

export type MarketLineage = {
  window_index: number
  market_id: string
  venue_ids: string[]
  party_count: number
  status: string
  previous_market_ids: string[]
  next_market_ids: string[]
  rerouted: boolean
  sustained: boolean
  coverage: string
}

export type MarketInstitutionsSummary = {
  run_id: string
  publication_id: string
  digest: string
  schema_version: string
  window_tick: number
  venue_count: number
  gathering_count: number
  market_like_venue_count: number
  recurring_venue_count: number
  expected_venue_count: number
  market_count: number
  expectation_row_count: number
  role_row_count: number
  record_anchor_count: number
  emerged_count: number
  continued_count: number
  transformed_count: number
  split_count: number
  merge_count: number
  dissolved_count: number
  sustained_market_count: number
  lineage_edge_count: number
  coverage: string
  truncated: boolean
}

export type MarketPage<T> = {
  run_id: string
  publication_id: string
  window_index: number | null
  rows: T[]
  next_cursor: string | null
  coverage: string
}

export type MarketMarketsPage = MarketPage<MarketCandidate> & {
  lineage: MarketLineage[]
}

export type MarketListOptions = {
  cursor?: string | undefined
  limit?: number | undefined
  windowIndex?: number | undefined
}

function base(runId: string): string {
  return `/v1/simulations/${encodeURIComponent(runId)}/market-institutions`
}

function query(
  options: MarketListOptions,
): Record<string, string | number | undefined> {
  return {
    cursor: options.cursor,
    limit: options.limit ?? 200,
    window_index: options.windowIndex,
  }
}

export function fetchMarketInstitutionsSummary(
  runId: string,
): Promise<MarketInstitutionsSummary> {
  return apiFetch<MarketInstitutionsSummary>(base(runId), { capability: CAPABILITY })
}

function fetchPage<T>(
  runId: string,
  suffix: string,
  options: MarketListOptions,
): Promise<MarketPage<T>> {
  return apiFetch<MarketPage<T>>(`${base(runId)}${suffix}`, {
    capability: CAPABILITY,
    query: query(options),
  })
}

export function fetchMarketVenues(
  runId: string,
  options: MarketListOptions = {},
): Promise<MarketPage<MarketVenue>> {
  return fetchPage<MarketVenue>(runId, '/venues', options)
}

export function fetchMarketGatherings(
  runId: string,
  options: MarketListOptions = {},
): Promise<MarketPage<MarketGathering>> {
  return fetchPage<MarketGathering>(runId, '/gatherings', options)
}

export function fetchMarketExpectations(
  runId: string,
  options: MarketListOptions = {},
): Promise<MarketPage<MarketExpectation>> {
  return fetchPage<MarketExpectation>(runId, '/expectations', options)
}

export function fetchMarketRoles(
  runId: string,
  options: MarketListOptions = {},
): Promise<MarketPage<MarketRole>> {
  return fetchPage<MarketRole>(runId, '/roles', options)
}

export function fetchMarketRecords(
  runId: string,
  options: MarketListOptions = {},
): Promise<MarketPage<MarketRecord>> {
  return fetchPage<MarketRecord>(runId, '/records', options)
}

export function fetchMarketCandidates(
  runId: string,
  options: MarketListOptions = {},
): Promise<MarketMarketsPage> {
  return apiFetch<MarketMarketsPage>(`${base(runId)}/markets`, {
    capability: CAPABILITY,
    query: query(options),
  })
}
