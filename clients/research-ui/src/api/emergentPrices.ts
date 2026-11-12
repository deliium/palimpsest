import { apiFetch } from './client'

export const CAPABILITY = 'subjective_debug'

export type PriceUnit = {
  unit_token: string
  unit_source: string
  owner_count: number
  expectation_count: number
  distribution_count: number
  median_confidence_milli: number
  unit_alignment: string
  coverage: string
}

export type PriceExpectation = {
  expectation_id: string
  window_index: number
  owner_token: string
  item_kind: string
  unit_kind: string
  unit_source: string
  expected_ratio_milli: number
  confidence_milli: number
  level: string
  valuation_reservation: number
  observation_count: number
  quote_count: number
  distribution_source: string
  alignment: string
  coverage: string
}

export type PriceQuote = {
  quote_id: string
  window_index: number
  venue_id: string
  actor_token: string
  counterparty_token: string
  item_kind: string
  unit_kind: string
  direction: string
  ratio_milli: number
  confidence_milli: number
  source: string
  source_tick: number
  coverage: string
}

export type PriceDistribution = {
  distribution_id: string
  window_index: number
  venue_id: string
  market_token: string
  item_kind: string
  unit_kind: string
  unit_source: string
  sample_source: string
  sample_count: number
  min_ratio_milli: number
  p25_ratio_milli: number
  median_ratio_milli: number
  p75_ratio_milli: number
  max_ratio_milli: number
  iqr_milli: number
  dispersion_milli: number
  bin_shares_milli: number[]
  status: string
  coverage: string
}

export type PriceMarket = {
  market_token: string
  window_index: number
  venue_count: number
  distribution_count: number
  sample_count: number
  item_kind_count: number
  unit_count: number
  coverage: string
}

export type PriceRelation = {
  relation_id: string
  window_index: number
  group_kind: string
  group_a_token: string
  group_b_token: string
  item_kind: string
  unit_kind: string
  unit_source: string
  sample_source: string
  overlap_milli: number
  median_gap_milli: number
  relation: string
  sample_a: number
  sample_b: number
  coverage: string
}

export type EmergentPricesSummary = {
  run_id: string
  publication_id: string
  digest: string
  schema_version: string
  window_tick: number
  window_count: number
  unit_count: number
  expectation_count: number
  quote_count: number
  distribution_count: number
  market_count: number
  relation_count: number
  exchange_count: number
  quote_event_count: number
  evidence_coverage: string
  expectation_coverage: string
  quote_coverage: string
  distribution_coverage: string
  market_coverage: string
  relation_coverage: string
  coverage: string
  truncated: boolean
}

export type PricePage<T> = {
  run_id: string
  publication_id: string
  window_index: number | null
  rows: T[]
  next_cursor: string | null
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
  `/v1/simulations/${encodeURIComponent(runId)}/emergent-prices`

export function getSummary(runId: string): Promise<EmergentPricesSummary> {
  return apiFetch<EmergentPricesSummary>(base(runId), { capability: CAPABILITY })
}

export function getUnits(
  runId: string,
  options: PageOptions = {},
): Promise<PricePage<PriceUnit>> {
  return apiFetch<PricePage<PriceUnit>>(
    `${base(runId)}/units${query(options)}`,
    { capability: CAPABILITY },
  )
}

export function getExpectations(
  runId: string,
  options: PageOptions = {},
): Promise<PricePage<PriceExpectation>> {
  return apiFetch<PricePage<PriceExpectation>>(
    `${base(runId)}/expectations${query(options)}`,
    { capability: CAPABILITY },
  )
}

export function getQuotes(
  runId: string,
  options: PageOptions = {},
): Promise<PricePage<PriceQuote>> {
  return apiFetch<PricePage<PriceQuote>>(
    `${base(runId)}/quotes${query(options)}`,
    { capability: CAPABILITY },
  )
}

export function getDistributions(
  runId: string,
  options: PageOptions = {},
): Promise<PricePage<PriceDistribution>> {
  return apiFetch<PricePage<PriceDistribution>>(
    `${base(runId)}/distributions${query(options)}`,
    { capability: CAPABILITY },
  )
}

export function getMarkets(
  runId: string,
  options: PageOptions = {},
): Promise<PricePage<PriceMarket>> {
  return apiFetch<PricePage<PriceMarket>>(
    `${base(runId)}/markets${query(options)}`,
    { capability: CAPABILITY },
  )
}

export function getRelations(
  runId: string,
  options: PageOptions = {},
): Promise<PricePage<PriceRelation>> {
  return apiFetch<PricePage<PriceRelation>>(
    `${base(runId)}/relations${query(options)}`,
    { capability: CAPABILITY },
  )
}
