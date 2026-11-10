import { apiFetch } from './client'

export const CAPABILITY = 'subjective_debug'

export type TradeFlowCount = Record<string, number>

export type TradeNetworksSummary = {
  run_id: string
  publication_id: string
  digest: string
  schema_version: string
  window_tick: number
  corridor_count: number
  flow_count: number
  location_count: number
  major_location_count: number
  trade_post_location_count: number
  network_count: number
  cross_society_pair_count: number
  transfer_count: number
  emerged_count: number
  continued_count: number
  transformed_count: number
  split_count: number
  merge_count: number
  dissolved_count: number
  rerouted_count: number
  sustained_network_count: number
  lineage_edge_count: number
  coverage: string
  truncated: boolean
}

export type TradeCorridor = {
  corridor_id: string
  window_index: number
  from_location_id: string
  to_location_id: string
  flow_counts: TradeFlowCount
  transfer_count: number
  coverage: string
}

export type TradeFlow = {
  window_index: number
  flow_class: string
  transfer_count: number
  cross_location_count: number
  imported_count: number
  exported_count: number
  local_count: number
  coverage: string
}

export type TradeLocation = {
  location_id: string
  window_index: number
  inflow_count: number
  outflow_count: number
  local_count: number
  corridor_degree: number
  is_major: boolean
  trade_post_present: boolean
  flow_counts: TradeFlowCount
  coverage: string
}

export type TradeDependence = {
  location_id: string
  window_index: number
  flow_class: string
  imported_count: number
  locally_originated_count: number
  dependence_milli: number | null
  high_dependence: boolean
  coverage: string
}

export type CrossSocietyTrade = {
  pair_id: string
  window_index: number
  society_a: string
  society_b: string
  society_a_location_id: string
  society_b_location_id: string
  overlap_member_count: number
  flow_counts: TradeFlowCount
  transfer_count: number
  society_a_to_b_count: number
  society_b_to_a_count: number
  coverage: string
}

export type TradeNetwork = {
  network_id: string
  window_index: number
  corridor_ids: string[]
  location_ids: string[]
  flow_counts: TradeFlowCount
  transfer_count: number
  status: string
  previous_network_ids: string[]
  next_network_ids: string[]
  rerouted: boolean
  sustained: boolean
  coverage: string
}

export type Page<T> = {
  items: T[]
  next_cursor?: string | null
}

export type TradeListOptions = {
  cursor?: string | undefined
  limit?: number | undefined
  windowIndex?: number | undefined
}

function base(runId: string): string {
  return `/v1/simulations/${encodeURIComponent(runId)}/trade-networks`
}

function query(options: TradeListOptions): Record<string, string | number | undefined> {
  return {
    cursor: options.cursor,
    limit: options.limit ?? 200,
    window_index: options.windowIndex,
  }
}

export function fetchTradeNetworksSummary(
  runId: string,
): Promise<TradeNetworksSummary> {
  return apiFetch<TradeNetworksSummary>(base(runId), { capability: CAPABILITY })
}

export function fetchTradeCorridors(
  runId: string,
  options: TradeListOptions = {},
): Promise<Page<TradeCorridor>> {
  return apiFetch<Page<TradeCorridor>>(`${base(runId)}/corridors`, {
    capability: CAPABILITY,
    query: query(options),
  })
}

export function fetchTradeFlows(
  runId: string,
  options: TradeListOptions = {},
): Promise<Page<TradeFlow>> {
  return apiFetch<Page<TradeFlow>>(`${base(runId)}/flows`, {
    capability: CAPABILITY,
    query: query(options),
  })
}

export function fetchTradeLocations(
  runId: string,
  options: TradeListOptions = {},
): Promise<Page<TradeLocation>> {
  return apiFetch<Page<TradeLocation>>(`${base(runId)}/locations`, {
    capability: CAPABILITY,
    query: query(options),
  })
}

export function fetchTradeDependence(
  runId: string,
  options: TradeListOptions = {},
): Promise<Page<TradeDependence>> {
  return apiFetch<Page<TradeDependence>>(`${base(runId)}/dependence`, {
    capability: CAPABILITY,
    query: query(options),
  })
}

export function fetchCrossSocietyTrades(
  runId: string,
  options: TradeListOptions = {},
): Promise<Page<CrossSocietyTrade>> {
  return apiFetch<Page<CrossSocietyTrade>>(`${base(runId)}/cross-society`, {
    capability: CAPABILITY,
    query: query(options),
  })
}

export function fetchTradeNetworks(
  runId: string,
  options: TradeListOptions = {},
): Promise<Page<TradeNetwork>> {
  return apiFetch<Page<TradeNetwork>>(`${base(runId)}/networks`, {
    capability: CAPABILITY,
    query: query(options),
  })
}
